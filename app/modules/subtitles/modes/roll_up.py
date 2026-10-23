import re

from app.modules.subtitles.modes.base import BaseSubtitleModel
from app.modules.subtitles.policies.punctuation import PunctuationPolicy
from app.shared.config_contract import require_float, require_int


class RollUpModel(BaseSubtitleModel):
    """Emit sequential, fixed-width lines for a rolling vertical buffer."""

    def __init__(self, config):
        self.punctuation = PunctuationPolicy(config)
        self.max_chars_per_line = require_int(
            config, "max_chars_per_line", "cue_policy.max_chars_per_line"
        )
        self.visible_lines = require_int(
            config, "visible_lines", "cue_policy.visible_lines"
        )
        self.significant_gap_threshold = require_float(
            config,
            "significant_gap_threshold",
            "cue_policy.significant_gap_threshold",
        )

        if self.max_chars_per_line <= 0:
            raise ValueError("cue_policy.max_chars_per_line debe ser superior a cero.")
        if self.visible_lines not in (2, 3, 4):
            raise ValueError("cue_policy.visible_lines debe ser 2, 3 o 4.")
        if self.significant_gap_threshold <= 0:
            raise ValueError(
                "cue_policy.significant_gap_threshold debe ser superior a cero."
            )

    def optimize(self, blocks, timing=None):
        if timing is not None and timing.is_usable():
            return self._optimize_with_timing(timing)
        return self._optimize_without_timing(blocks)

    def _optimize_with_timing(self, timing):
        optimized = []
        index = 1
        for segment in timing.segments:
            for group in self._split_words_by_gap(segment.words):
                for line_words in self._fixed_width_lines(group):
                    optimized.append(
                        self._format_block(
                            index,
                            self._seconds_to_time(line_words[0].start),
                            self._seconds_to_time(line_words[-1].end),
                            self._format_words(line_words),
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
            line_words = self._fixed_width_lines(words)
            ranges = self._distribute_ranges(start_ms, end_ms, line_words)
            for words_for_line, (line_start, line_end) in zip(line_words, ranges):
                optimized.append(
                    self._format_block(
                        index,
                        self._ms_to_time(line_start),
                        self._ms_to_time(line_end),
                        self._format_words(words_for_line),
                    )
                )
                index += 1
        return optimized

    def _split_words_by_gap(self, words):
        groups = []
        current = []
        for word in words:
            if word.end <= word.start:
                continue
            if (
                current
                and word.start - current[-1].end >= self.significant_gap_threshold
            ):
                groups.append(tuple(current))
                current = []
            current.append(word)
        if current:
            groups.append(tuple(current))
        return groups

    def _fixed_width_lines(self, words):
        lines = []
        current = []
        for word in words:
            text = self._word_text(word)
            if len(text) > self.max_chars_per_line:
                raise ValueError(
                    "Una palabra supera cue_policy.max_chars_per_line: "
                    f"{text}"
                )
            candidate = (*current, word)
            if current and len(self._join_words(candidate)) > self.max_chars_per_line:
                lines.append(tuple(current))
                current = [word]
            else:
                current.append(word)
        if current:
            lines.append(tuple(current))
        return tuple(lines)

    def _distribute_ranges(self, start_ms, end_ms, lines):
        if not lines:
            return ()
        duration = end_ms - start_ms
        lengths = [max(1, len(self._join_words(words))) for words in lines]
        total = sum(lengths)
        cursor = start_ms
        ranges = []
        for index, length in enumerate(lengths):
            line_end = (
                end_ms
                if index == len(lengths) - 1
                else cursor + round(duration * length / total)
            )
            ranges.append((cursor, line_end))
            cursor = line_end
        return tuple(ranges)

    def _format_words(self, words):
        return self.punctuation.apply(self._join_words(words)).strip()

    @staticmethod
    def _word_text(word):
        return word.text if hasattr(word, "text") else str(word)

    def _join_words(self, words):
        return " ".join(self._word_text(word) for word in words)

    @staticmethod
    def _format_block(index, start, end, text):
        return f"{index}\n{start} --> {end}\n{text}"

    @staticmethod
    def _parse_block(block):
        lines = str(block).strip().splitlines()
        if len(lines) < 3:
            return None
        match = re.match(
            r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*"
            r"(\d{2}:\d{2}:\d{2},\d{3})",
            lines[1].strip(),
        )
        if match is None:
            return None
        return (
            RollUpModel._time_to_ms(match.group(1)),
            RollUpModel._time_to_ms(match.group(2)),
            " ".join(lines[2:]).split(),
        )

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
