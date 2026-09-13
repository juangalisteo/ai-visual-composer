import re

from app.modules.subtitles.micro_cue_policy import MicroCuePolicy
from app.modules.subtitles.models.base_subtitle_model import BaseSubtitleModel
from app.modules.subtitles.punctuation import PunctuationPolicy
from app.shared.config_contract import (
    require_bool,
    require_float,
    require_mapping,
    require_text,
)


class WordByWordModel(BaseSubtitleModel):

    def __init__(self, config):
        self.min_duration = require_float(
            config,
            "min_duration",
            "cue_policy.min_duration"
        )
        self.max_duration = require_float(
            config,
            "max_duration",
            "cue_policy.max_duration"
        )
        self.punctuation = PunctuationPolicy(config)
        self.significant_gap_threshold = require_float(
            config,
            "significant_gap_threshold",
            "cue_policy.significant_gap_threshold"
        )
        self.render_fps = require_float(
            config,
            "render_fps",
            "cue_policy.render_fps"
        )
        micro_cues = require_mapping(
            config,
            "micro_cues",
            "cue_policy.micro_cues"
        )
        self.micro_cues = {
            "enabled": require_bool(
                micro_cues,
                "enabled",
                "cue_policy.micro_cues.enabled"
            ),
            "min_frames": require_float(
                micro_cues,
                "min_frames",
                "cue_policy.micro_cues.min_frames"
            ),
            "min_display_seconds": require_float(
                micro_cues,
                "min_display_seconds",
                "cue_policy.micro_cues.min_display_seconds"
            ),
            "merge_preference": require_text(
                micro_cues,
                "merge_preference",
                "cue_policy.micro_cues.merge_preference"
            ),
        }

        if self.min_duration <= 0 or self.max_duration <= 0:
            raise ValueError(
                "Las duraciones de cue_policy deben ser "
                "superiores a cero."
            )
        if self.max_duration < self.min_duration:
            raise ValueError(
                "cue_policy.max_duration no puede ser menor "
                "que cue_policy.min_duration."
            )
        if self.significant_gap_threshold <= 0:
            raise ValueError(
                "cue_policy.significant_gap_threshold debe ser "
                "superior a cero."
            )
        if self.render_fps <= 0:
            raise ValueError(
                "cue_policy.render_fps debe ser superior a cero."
            )
        self.last_micro_cue_stats = None

    def optimize(self, blocks, timing=None):
        if timing is not None and timing.is_usable():
            return self._optimize_with_timing(
                timing
            )

        optimized_blocks = []
        new_index = 1

        for block in blocks:
            parsed = self._parse_block(block)

            if not parsed:
                continue

            start_ms, end_ms, text = parsed
            duration_ms = end_ms - start_ms

            if duration_ms <= 0:
                continue

            words = self._split_words(text)

            if not words:
                continue

            time_ranges = self._distribute_time(
                start_ms=start_ms,
                end_ms=end_ms,
                words=words
            )

            for word, (word_start, word_end) in zip(words, time_ranges):
                optimized_blocks.append(
                    f"{new_index}\n"
                    f"{self._ms_to_time(word_start)} --> {self._ms_to_time(word_end)}\n"
                    f"{word}"
                )

                new_index += 1

        return optimized_blocks

    def _optimize_with_timing(self, timing):
        optimized_blocks = []
        new_index = 1
        policy = self._micro_cue_policy()
        result = policy.apply(
            timing.words,
            formatter=self._format_word
        )
        self.last_micro_cue_stats = result.stats

        for cue in result.cues:
            optimized_blocks.append(
                f"{new_index}\n"
                f"{self._seconds_to_time(cue.start)} --> "
                f"{self._seconds_to_time(cue.end)}\n"
                f"{cue.text}"
            )

            new_index += 1

        return optimized_blocks

    def _micro_cue_policy(self):
        return MicroCuePolicy(
            enabled=self.micro_cues["enabled"],
            fps=self.render_fps,
            min_frames=self.micro_cues["min_frames"],
            min_display_seconds=self.micro_cues[
                "min_display_seconds"
            ],
            significant_gap_threshold=self.significant_gap_threshold,
            merge_preference=self.micro_cues["merge_preference"]
        )

    def _split_words(self, text):
        text = self._clean_text(text)

        text = self.punctuation.apply(text)

        words = text.split()

        return words

    def _format_word(self, text):
        text = self._clean_text(
            text
        )

        text = self.punctuation.apply(text)

        return text


    def _distribute_time(self, start_ms, end_ms, words):
        duration_ms = end_ms - start_ms

        if len(words) == 1:
            return [(start_ms, end_ms)]

        min_ms = int(self.min_duration * 1000)
        max_ms = int(self.max_duration * 1000)

        base_duration = int(duration_ms / len(words))

        base_duration = max(min_ms, base_duration)
        base_duration = min(max_ms, base_duration)

        durations = [base_duration for _ in words]

        total_duration = sum(durations)

        if total_duration != duration_ms:
            factor = duration_ms / total_duration
            durations = [int(d * factor) for d in durations]

        diff = duration_ms - sum(durations)

        if durations:
            durations[-1] += diff

        ranges = []
        current_start = start_ms

        for duration in durations:
            current_end = current_start + duration

            if current_end > end_ms:
                current_end = end_ms

            ranges.append((current_start, current_end))
            current_start = current_end

        if ranges:
            ranges[-1] = (ranges[-1][0], end_ms)

        return ranges

    def _parse_block(self, block):
        lines = block.strip().splitlines()

        if len(lines) < 3:
            return None

        timestamp = lines[1].strip()
        text = self._clean_text(" ".join(lines[2:]))

        match = re.match(
            r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})",
            timestamp
        )

        if not match:
            return None

        start_ms = self._time_to_ms(match.group(1))
        end_ms = self._time_to_ms(match.group(2))

        return start_ms, end_ms, text

    def _clean_text(self, text):
        return " ".join(text.split()).strip()

    def _time_to_ms(self, time_text):
        hours, minutes, rest = time_text.split(":")
        seconds, milliseconds = rest.split(",")

        return (
            int(hours) * 3600000
            + int(minutes) * 60000
            + int(seconds) * 1000
            + int(milliseconds)
        )

    def _ms_to_time(self, total_ms):
        total_ms = max(0, int(total_ms))

        hours = total_ms // 3600000
        total_ms %= 3600000

        minutes = total_ms // 60000
        total_ms %= 60000

        seconds = total_ms // 1000
        milliseconds = total_ms % 1000

        return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

    def _seconds_to_time(self, seconds):
        return self._ms_to_time(
            round(
                float(seconds)
                * 1000
            )
        )
