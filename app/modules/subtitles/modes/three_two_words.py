import re

from app.modules.subtitles.modes.base import BaseSubtitleModel
from app.modules.subtitles.policies.punctuation import PunctuationPolicy
from app.modules.subtitles.policies.timing import (
    stretch_zero_duration_cues,
    text_joiner,
)
from app.shared.config_contract import require_float, require_int


class ThreeTwoWordsModel(BaseSubtitleModel):
    """Build one-line cues with a 3/2 rhythm or fixed word chunks."""

    _PATTERN = (3, 2)

    # Punctuation that forces a visual cue boundary.
    # The boundary is detected on the original word, before PunctuationPolicy
    # removes or preserves the sign for rendering.
    _BOUNDARY_MARKS = ".,;:!?…"
    _CLOSING_WRAPPERS = "\"'”’»)]}"

    # Characters stripped only for detecting words that end in "-mente".
    # This does not modify the rendered subtitle text.
    _MENTE_TRAILING_CHARS = ".,;:!?…¿¡-—\"'“”‘’«»()[]{}"

    def __init__(self, config):
        self.punctuation = PunctuationPolicy(config)

        self.max_chars_per_line = require_int(
            config,
            "max_chars_per_line",
            "cue_policy.max_chars_per_line",
        )
        self.min_duration = require_float(
            config,
            "min_duration",
            "cue_policy.min_duration",
        )
        self.max_duration = require_float(
            config,
            "max_duration",
            "cue_policy.max_duration",
        )
        self.significant_gap_threshold = require_float(
            config,
            "significant_gap_threshold",
            "cue_policy.significant_gap_threshold",
        )
        self.fixed_chunk_size = (
            require_int(
                config,
                "fixed_chunk_size",
                "cue_policy.fixed_chunk_size",
            )
            if "fixed_chunk_size" in config
            else None
        )

        if self.max_chars_per_line <= 0:
            raise ValueError(
                "cue_policy.max_chars_per_line debe ser superior a cero."
            )
        if self.min_duration <= 0 or self.max_duration <= 0:
            raise ValueError(
                "Las duraciones de cue_policy deben ser superiores a cero."
            )
        if self.max_duration < self.min_duration:
            raise ValueError(
                "cue_policy.max_duration no puede ser menor que "
                "cue_policy.min_duration."
            )
        if self.significant_gap_threshold <= 0:
            raise ValueError(
                "cue_policy.significant_gap_threshold debe ser superior a cero."
            )
        if self.fixed_chunk_size is not None and self.fixed_chunk_size <= 0:
            raise ValueError(
                "cue_policy.fixed_chunk_size debe ser superior a cero."
            )

    def optimize(self, blocks, timing=None):
        if timing is not None and timing.is_usable():
            return self._optimize_with_timing(timing)

        return self._optimize_without_timing(blocks)

    def _optimize_with_timing(self, timing):
        timed_cues = []

        for segment in timing.segments:
            for word_group in self._split_words_by_gap(segment.words):
                for cue_words in self._partition_words(word_group):
                    timed_cues.append(
                        (
                            cue_words[0].start,
                            cue_words[-1].end,
                            cue_words,
                            self._format_words(cue_words),
                        )
                    )

        return [
            self._format_block(
                index=index,
                start=self._seconds_to_time(start),
                end=self._seconds_to_time(end),
                text=text,
            )
            for index, (start, end, text) in enumerate(
                stretch_zero_duration_cues(
                    timed_cues,
                    self.significant_gap_threshold,
                    # Joined words go in front on a single line.
                    text_joiner(self._format_line_words),
                ),
                start=1,
            )
        ]

    def _optimize_without_timing(self, blocks):
        optimized = []
        index = 1

        for block in blocks:
            parsed = self._parse_block(block)
            if parsed is None:
                continue

            start_ms, end_ms, words = parsed
            chunks = self._partition_words(words)
            time_ranges = self._distribute_time_by_text_length(
                start_ms,
                end_ms,
                chunks,
            )

            for chunk, (chunk_start, chunk_end) in zip(chunks, time_ranges):
                optimized.append(
                    self._format_block(
                        index=index,
                        start=self._ms_to_time(chunk_start),
                        end=self._ms_to_time(chunk_end),
                        text=self._format_words(chunk),
                    )
                )
                index += 1

        return optimized

    def _partition_words(self, words):
        """
        Partition words while preserving two hard linguistic boundaries:

        1. A word ending in punctuation closes the current cue. The following
           word must start a new cue.
        2. Any word ending in "-mente" is always rendered as a cue by itself.

        These rules are evaluated on the original word text, before
        PunctuationPolicy changes the visible punctuation.
        """
        words = tuple(words)
        if not words:
            return []

        chunks = []
        regular_group = []

        for word in words:
            if self._is_mente_word(word):
                if regular_group:
                    chunks.extend(
                        self._partition_regular_group(tuple(regular_group))
                    )
                    regular_group = []

                self._validate_single_word(word)
                chunks.append((word,))
                continue

            regular_group.append(word)

            if self._ends_with_boundary_punctuation(word):
                chunks.extend(
                    self._partition_regular_group(tuple(regular_group))
                )
                regular_group = []

        if regular_group:
            chunks.extend(
                self._partition_regular_group(tuple(regular_group))
            )

        return chunks

    def _partition_regular_group(self, words):
        """
        Apply either a fixed configured chunk size or the original 3/2 pattern,
        always honoring the max-char limit inside one regular linguistic group.

        Hard boundaries are resolved before entering this method, so orphan
        correction can never merge across punctuation or an isolated -mente
        word.
        """
        words = tuple(words)
        if not words:
            return []

        chunks = []
        cursor = 0
        pattern_index = 0

        while cursor < len(words):
            target_size = (
                self.fixed_chunk_size
                if self.fixed_chunk_size is not None
                else self._PATTERN[pattern_index % len(self._PATTERN)]
            )
            chunk = []

            for word in words[cursor:cursor + target_size]:
                candidate = " ".join(
                    [self._word_text(item) for item in (*chunk, word)]
                )
                if len(candidate) > self.max_chars_per_line:
                    break

                chunk.append(word)

            if not chunk:
                self._validate_single_word(words[cursor])

            chunks.append(tuple(chunk))
            cursor += len(chunk)
            pattern_index += 1

        if self.fixed_chunk_size is not None:
            return chunks
        return self._avoid_final_orphan(chunks)

    def _validate_single_word(self, word):
        text = self._word_text(word)

        if len(text) > self.max_chars_per_line:
            raise ValueError(
                "Una palabra supera cue_policy.max_chars_per_line: "
                f"{text}"
            )

    def _is_mente_word(self, word):
        text = self._word_text(word).strip().lower()

        if not text:
            return False

        normalized = text.rstrip(
            self._MENTE_TRAILING_CHARS
        )

        return normalized.endswith("mente")

    def _ends_with_boundary_punctuation(self, word):
        text = self._word_text(word).strip()

        if not text:
            return False

        # Allow punctuation followed by closing quotes/brackets, e.g.
        # `conciencia."` or `correcto?)`.
        while text and text[-1] in self._CLOSING_WRAPPERS:
            text = text[:-1].rstrip()

        if not text:
            return False

        return text[-1] in self._BOUNDARY_MARKS

    def _avoid_final_orphan(self, chunks):
        if len(chunks) < 2 or len(chunks[-1]) != 1:
            return chunks

        result = list(chunks)
        previous = result[-2]
        orphan = result[-1]

        combined = previous + orphan
        if self._fits(combined):
            result[-2] = combined
            result.pop()
            return result

        if len(previous) > 1:
            moved = previous[-1:]
            candidate_previous = previous[:-1]
            candidate_last = moved + orphan

            if (
                self._fits(candidate_previous)
                and self._fits(candidate_last)
            ):
                result[-2] = candidate_previous
                result[-1] = candidate_last

        return result

    def _split_words_by_gap(self, words):
        groups = []
        current = []

        for word in words:
            if (
                current
                and word.start - current[-1].end
                >= self.significant_gap_threshold
            ):
                groups.append(tuple(current))
                current = []

            current.append(word)

        if current:
            groups.append(tuple(current))

        return groups

    def _distribute_time_by_text_length(
        self,
        start_ms,
        end_ms,
        chunks,
    ):
        if not chunks:
            return []

        if len(chunks) == 1:
            return [(start_ms, end_ms)]

        duration_ms = end_ms - start_ms

        weights = [
            max(
                1,
                len(
                    " ".join(
                        self._word_text(word)
                        for word in chunk
                    )
                ),
            )
            for chunk in chunks
        ]

        total_weight = sum(weights)

        min_ms = int(self.min_duration * 1000)
        max_ms = int(self.max_duration * 1000)

        durations = [
            min(
                max_ms,
                max(
                    min_ms,
                    int(duration_ms * weight / total_weight),
                ),
            )
            for weight in weights
        ]

        total_duration = sum(durations)

        if total_duration:
            durations = [
                int(value * duration_ms / total_duration)
                for value in durations
            ]

        durations[-1] += duration_ms - sum(durations)

        ranges = []
        current_start = start_ms

        for duration in durations:
            current_end = min(
                end_ms,
                current_start + duration,
            )
            ranges.append(
                (
                    current_start,
                    current_end,
                )
            )
            current_start = current_end

        ranges[-1] = (
            ranges[-1][0],
            end_ms,
        )

        return ranges

    def _parse_block(self, block):
        lines = str(block).strip().splitlines()

        if len(lines) < 3:
            return None

        match = re.match(
            r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*"
            r"(\d{2}:\d{2}:\d{2},\d{3})",
            lines[1].strip(),
        )

        if not match:
            return None

        start_ms = self._time_to_ms(
            match.group(1)
        )
        end_ms = self._time_to_ms(
            match.group(2)
        )

        if end_ms <= start_ms:
            return None

        words = tuple(
            " ".join(lines[2:]).split()
        )

        if not words:
            return None

        return start_ms, end_ms, words

    def _fits(self, words):
        text = " ".join(
            self._word_text(word)
            for word in words
        )

        return (
            len(text)
            <= self.max_chars_per_line
        )

    def _format_words(self, words):
        return self._format_line_words(words)

    def _format_line_words(self, words):
        text = " ".join(
            self._word_text(word)
            for word in words
        )

        return self.punctuation.apply(text)

    @staticmethod
    def _word_text(word):
        return (
            word.text
            if hasattr(word, "text")
            else str(word)
        )

    @staticmethod
    def _format_block(
        index,
        start,
        end,
        text,
    ):
        return (
            f"{index}\n"
            f"{start} --> {end}\n"
            f"{text}"
        )

    @staticmethod
    def _time_to_ms(value):
        hours, minutes, rest = value.split(":")
        seconds, milliseconds = rest.split(",")

        return (
            int(hours) * 3_600_000
            + int(minutes) * 60_000
            + int(seconds) * 1_000
            + int(milliseconds)
        )

    @staticmethod
    def _ms_to_time(total_ms):
        total_ms = max(
            0,
            int(total_ms),
        )

        hours, total_ms = divmod(
            total_ms,
            3_600_000,
        )
        minutes, total_ms = divmod(
            total_ms,
            60_000,
        )
        seconds, milliseconds = divmod(
            total_ms,
            1_000,
        )

        return (
            f"{hours:02}:"
            f"{minutes:02}:"
            f"{seconds:02},"
            f"{milliseconds:03}"
        )

    def _seconds_to_time(self, seconds):
        return self._ms_to_time(
            round(
                float(seconds)
                * 1_000
            )
        )
