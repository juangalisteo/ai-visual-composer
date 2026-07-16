from dataclasses import dataclass
from pathlib import Path
import re

from app.shared.media_probe import MediaProbe


@dataclass(frozen=True)
class VideoTimeline:
    audio_duration: float
    image_duration: float
    subtitle_path: Path


class TimelineBuilder:

    def build(
        self,
        audio_path,
        subtitle_path,
        image_count,
        subtitle_offset
    ):
        audio_duration = (
            MediaProbe.get_duration(
                audio_path
            )
        )

        image_duration = (
            audio_duration
            / image_count
        )

        subtitle_path = Path(
            subtitle_path
        )

        if subtitle_offset != 0:
            subtitle_path = (
                self._shift_srt(
                    input_path=subtitle_path,
                    offset_seconds=subtitle_offset
                )
            )

        return VideoTimeline(
            audio_duration=audio_duration,
            image_duration=image_duration,
            subtitle_path=subtitle_path
        )

    def _shift_srt(
        self,
        input_path,
        offset_seconds
    ):
        output_path = (
            input_path.parent
            / "subtitulos_video.srt"
        )

        text = input_path.read_text(
            encoding="utf-8"
        )

        pattern = re.compile(
            r"(\d{2}):"
            r"(\d{2}):"
            r"(\d{2}),"
            r"(\d{3})"
        )

        def shift(match):

            hours = int(
                match.group(1)
            )

            minutes = int(
                match.group(2)
            )

            seconds = int(
                match.group(3)
            )

            milliseconds = int(
                match.group(4)
            )

            total_ms = (
                hours * 3600000
                + minutes * 60000
                + seconds * 1000
                + milliseconds
                + int(
                    offset_seconds
                    * 1000
                )
            )

            total_ms = max(
                total_ms,
                0
            )

            new_hours = (
                total_ms
                // 3600000
            )

            total_ms %= 3600000

            new_minutes = (
                total_ms
                // 60000
            )

            total_ms %= 60000

            new_seconds = (
                total_ms
                // 1000
            )

            new_milliseconds = (
                total_ms
                % 1000
            )

            return (
                f"{new_hours:02}:"
                f"{new_minutes:02}:"
                f"{new_seconds:02},"
                f"{new_milliseconds:03}"
            )

        shifted = pattern.sub(
            shift,
            text
        )

        output_path.write_text(
            shifted,
            encoding="utf-8"
        )

        return output_path