import re

from app.modules.subtitles.modes.base import BaseSubtitleModel
from app.modules.subtitles.policies.punctuation import PunctuationPolicy
from app.modules.subtitles.policies.timing import (
    stretch_zero_duration_cues,
    text_joiner,
)
from app.shared.config_contract import require_float, require_int


class RollingWindowModel(BaseSubtitleModel):
    """Emit fixed-size FIFO word windows shown one at a time.

    Each window ends where the next one of its group starts; the last
    window keeps the end of its final word. A group shorter than the
    window is shown whole in a single cue.

    A window that does not fit in ``max_chars_per_line`` drops its last
    words (a longer word stays alone), and windows go on until one reaches
    the end of the group, so every word is shown.
    """

    def __init__(self, config):
        self.punctuation = PunctuationPolicy(config)
        self.significant_gap_threshold = require_float(
            config,
            "significant_gap_threshold",
            "cue_policy.significant_gap_threshold",
        )
        self.window_size = require_int(
            config, "window_size", "cue_policy.window_size"
        )
        self.max_chars_per_line = require_int(
            config, "max_chars_per_line", "cue_policy.max_chars_per_line"
        )

        if self.significant_gap_threshold <= 0:
            raise ValueError(
                "cue_policy.significant_gap_threshold debe ser superior a cero."
            )
        if self.window_size < 2:
            raise ValueError("cue_policy.window_size debe ser un entero >= 2.")
        if self.max_chars_per_line <= 0:
            raise ValueError(
                "cue_policy.max_chars_per_line debe ser superior a cero."
            )

    def optimize(self, blocks, timing=None):
        if timing is not None and timing.is_usable():
            return self._optimize_with_timing(timing)
        return self._optimize_without_timing(blocks)

    def _optimize_with_timing(self, timing):
        timed_cues = []
        for segment in timing.segments:
            for group in self._split_words_by_gap(segment.words):
                windows = self._windows(group)
                for position, window in enumerate(windows):
                    end = (
                        windows[position + 1][0].start
                        if position + 1 < len(windows)
                        else window[-1].end
                    )
                    timed_cues.append(
                        (window[0].start, end, window, self._format_words(window))
                    )
        return [
            self._format_block(
                index,
                self._seconds_to_time(start),
                self._seconds_to_time(end),
                text,
            )
            for index, (start, end, text) in enumerate(
                stretch_zero_duration_cues(
                    timed_cues,
                    self.significant_gap_threshold,
                    text_joiner(self._format_words),
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
            ranges = self._distribute_word_ranges(start_ms, end_ms, words)
            bounds = self._window_bounds(words)
            for position, (start_index, end_index) in enumerate(bounds):
                cue_end = (
                    ranges[start_index + 1][0]
                    if position + 1 < len(bounds)
                    else ranges[end_index - 1][1]
                )
                optimized.append(
                    self._format_block(
                        index,
                        self._ms_to_time(ranges[start_index][0]),
                        self._ms_to_time(cue_end),
                        self._format_words(words[start_index:end_index]),
                    )
                )
                index += 1
        return optimized

    def _split_words_by_gap(self, words):
        groups = []
        current = []
        for word in words:
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
            tuple(words[start:end]) for start, end in self._window_bounds(words)
        )

    def _window_bounds(self, words):
        """Return ``(start, end)`` word slices: one window per first word.

        Each window takes up to ``window_size`` words while its text fits
        in ``max_chars_per_line``; the last one reaches the final word.
        """
        texts = [word.text if hasattr(word, "text") else str(word) for word in words]
        bounds = []
        for start in range(len(texts)):
            end = start + 1
            while (
                end < len(texts)
                and end - start < self.window_size
                and len(" ".join(texts[start:end + 1])) <= self.max_chars_per_line
            ):
                end += 1
            bounds.append((start, end))
            if end == len(texts):
                break
        return tuple(bounds)

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
