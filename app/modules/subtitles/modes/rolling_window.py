import re

from app.modules.subtitles.modes.base import BaseSubtitleModel
from app.modules.subtitles.policies.punctuation import PunctuationPolicy
from app.shared.config_contract import require_float, require_int


class RollingWindowModel(BaseSubtitleModel):
    """Emit fixed-size FIFO word windows with intentionally overlapping cues."""

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
        self.window_size = require_int(
            config, "window_size", "cue_policy.window_size"
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
        if self.window_size < 2:
            raise ValueError("cue_policy.window_size debe ser un entero >= 2.")

    def optimize(self, blocks, timing=None):
        if timing is not None and timing.is_usable():
            return self._optimize_with_timing(timing)
        return self._optimize_without_timing(blocks)

    def _optimize_with_timing(self, timing):
        optimized = []
        index = 1
        for segment in timing.segments:
            for group in self._split_words_by_gap(segment.words):
                for window in self._windows(group):
                    optimized.append(
                        self._format_block(
                            index,
                            self._seconds_to_time(window[0].start),
                            self._seconds_to_time(window[-1].end),
                            self._format_words(window),
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
            ranges = self._distribute_word_ranges(start_ms, end_ms, words)
            for start_index in range(max(0, len(words) - self.window_size + 1)):
                end_index = start_index + self.window_size - 1
                optimized.append(
                    self._format_block(
                        index,
                        self._ms_to_time(ranges[start_index][0]),
                        self._ms_to_time(ranges[end_index][1]),
                        self._format_words(words[start_index:end_index + 1]),
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

    def _windows(self, words):
        return tuple(
            tuple(words[index:index + self.window_size])
            for index in range(max(0, len(words) - self.window_size + 1))
        )

    def _format_words(self, words):
        return self.punctuation.apply(
            " ".join(word.text if hasattr(word, "text") else str(word) for word in words)
        ).strip()

    @staticmethod
    def _format_block(index, start, end, text):
        return f"{index}\n{start} --> {end}\n{text}"

    def _parse_block(self, block):
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
        words = " ".join(lines[2:]).split()
        return (
            self._time_to_ms(match.group(1)),
            self._time_to_ms(match.group(2)),
            words,
        )

    @staticmethod
    def _distribute_word_ranges(start_ms, end_ms, words):
        if not words:
            return ()
        duration = end_ms - start_ms
        return tuple(
            (
                start_ms + round(duration * index / len(words)),
                start_ms + round(duration * (index + 1) / len(words)),
            )
            for index in range(len(words))
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
