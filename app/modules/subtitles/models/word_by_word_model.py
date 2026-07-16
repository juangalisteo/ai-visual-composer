import re

from app.modules.subtitles.models.base_subtitle_model import BaseSubtitleModel


class WordByWordModel(BaseSubtitleModel):

    def __init__(self, config):
        self.min_duration = float(config.get("min_duration", 0.18))
        self.max_duration = float(config.get("max_duration", 0.65))
        self.uppercase = bool(config.get("uppercase", False))
        self.remove_extra_commas = bool(config.get("remove_extra_commas", True))

    def optimize(self, blocks):
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

    def _split_words(self, text):
        text = self._clean_text(text)

        if self.remove_extra_commas:
            text = text.replace(",", "")

        words = text.split()

        if self.uppercase:
            words = [word.upper() for word in words]

        return words

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
