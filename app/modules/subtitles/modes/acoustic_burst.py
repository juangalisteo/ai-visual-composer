import re

from app.modules.subtitles.modes.base import BaseSubtitleModel
from app.modules.subtitles.policies.punctuation import PunctuationPolicy
from app.shared.config_contract import require_float, require_int


class AcousticBurstModel(BaseSubtitleModel):
    """Build cues from acoustic pauses, with a visual safety limit."""

    def __init__(self, config):
        self.punctuation = PunctuationPolicy(config)
        self.min_duration = require_float(
            config, "min_duration", "cue_policy.min_duration"
        )
        self.max_duration = require_float(
            config, "max_duration", "cue_policy.max_duration"
        )
        self.significant_gap_threshold = require_float(
            config,
            "significant_gap_threshold",
            "cue_policy.significant_gap_threshold",
        )
        self.hard_max_chars = require_int(
            config, "hard_max_chars", "cue_policy.hard_max_chars"
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
        if self.hard_max_chars <= 0:
            raise ValueError(
                "cue_policy.hard_max_chars debe ser superior a cero."
            )

    def optimize(self, blocks, timing=None):
        if timing is not None and timing.is_usable():
            return self._optimize_with_timing(timing)
        return self._optimize_without_timing(blocks)

    def _optimize_with_timing(self, timing):
        optimized = []
        index = 1

        for segment in timing.segments:
            for cue_words in self._partition_timed_words(segment.words):
                optimized.append(
                    self._format_block(
                        index,
                        self._seconds_to_time(cue_words[0].start),
                        self._seconds_to_time(cue_words[-1].end),
                        self._format_words(cue_words),
                    )
                )
                index += 1
        return optimized

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
                start_ms, end_ms, chunks
            )
            for chunk, (chunk_start, chunk_end) in zip(chunks, time_ranges):
                optimized.append(
                    self._format_block(
                        index,
                        self._ms_to_time(chunk_start),
                        self._ms_to_time(chunk_end),
                        self._format_words(chunk),
                    )
                )
                index += 1
        return optimized

    def _partition_timed_words(self, words):
        chunks = []
        current = []

        for word in words:
            if word.end <= word.start:
                continue
            if current and (
                word.start - current[-1].end >= self.significant_gap_threshold
                or not self._fits((*current, word))
            ):
                chunks.append(tuple(current))
                current = []
            current.append(word)

        if current:
            chunks.append(tuple(current))
        return chunks

    def _partition_words(self, words):
        chunks = []
        current = []

        for word in words:
            if current and not self._fits((*current, word)):
                chunks.append(tuple(current))
                current = []
            current.append(word)

        if current:
            chunks.append(tuple(current))
        return chunks

    def _fits(self, words):
        return len(self._format_words(words)) <= self.hard_max_chars

    def _format_words(self, words):
        return self.punctuation.apply(
            " ".join(self._word_text(word) for word in words)
        ).strip()

    @staticmethod
    def _word_text(word):
        return word.text if hasattr(word, "text") else str(word)

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
        words = " ".join(lines[2:]).split()
        return (
            self._time_to_ms(match.group(1)),
            self._time_to_ms(match.group(2)),
            words,
        )

    def _distribute_time_by_text_length(self, start_ms, end_ms, chunks):
        if not chunks:
            return []
        duration = end_ms - start_ms
        lengths = [max(1, len(self._format_words(chunk))) for chunk in chunks]
        total_length = sum(lengths)
        ranges = []
        cursor = start_ms
        for index, length in enumerate(lengths):
            end = (
                end_ms
                if index == len(lengths) - 1
                else cursor + round(duration * length / total_length)
            )
            ranges.append((cursor, end))
            cursor = end
        return ranges

    @staticmethod
    def _format_block(index, start, end, text):
        return f"{index}\n{start} --> {end}\n{text}"

    @staticmethod
    def _time_to_ms(time_text):
        hours, minutes, rest = time_text.split(":")
        seconds, milliseconds = rest.split(",")
        return (
            int(hours) * 3_600_000
            + int(minutes) * 60_000
            + int(seconds) * 1_000
            + int(milliseconds)
        )

    @staticmethod
    def _ms_to_time(total_ms):
        total_ms = max(0, int(total_ms))
        hours, total_ms = divmod(total_ms, 3_600_000)
        minutes, total_ms = divmod(total_ms, 60_000)
        seconds, milliseconds = divmod(total_ms, 1_000)
        return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

    def _seconds_to_time(self, seconds):
        return self._ms_to_time(round(float(seconds) * 1_000))
