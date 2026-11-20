from dataclasses import dataclass
from pathlib import Path
import re

from app.shared.media_probe import MediaProbe


@dataclass(frozen=True)
class VideoTimeline:
    audio_duration: float
    # Average duration of each image (the audio over the number of images).
    image_duration: float
    subtitle_path: Path | None
    # Duration of each image, in order; they add up to audio_duration.
    # Empty: every image lasts image_duration.
    scene_durations: tuple[float, ...] = ()


# Largest difference, in seconds, between the audio and the storyboard
# durations added up that still counts as the same audio (they are rounded
# to milliseconds in the storyboard).
_DURATION_TOLERANCE = 0.05


def scene_spans(timeline, scene_count):
    """``(start, duration)`` of each of ``scene_count`` images, in seconds.

    The images follow one another from 0. They take the timeline's
    ``scene_durations`` when it has one per image; otherwise each one lasts
    its ``image_duration``.
    """
    durations = tuple(
        getattr(
            timeline,
            "scene_durations",
            ()
        )
    )

    if len(durations) != scene_count:
        durations = (timeline.image_duration,) * scene_count

    spans = []
    start = 0.0

    for duration in durations:
        spans.append(
            (start, duration)
        )
        start += duration

    return tuple(spans)


class TimelineBuilder:

    def build(
        self,
        audio_path,
        subtitle_path,
        image_count,
        subtitle_offset,
        render_subtitles=True,
        scene_durations=(),
    ):
        """Time the images over the audio.

        ``scene_durations`` holds the storyboard duration of each image (None
        when unknown). When every image has one and they add up to the audio
        duration, each image lasts its own; the last one ends with the audio.
        Otherwise, as without a storyboard, the audio is shared out equally.
        """
        audio_duration = (
            MediaProbe.get_duration(
                audio_path
            )
        )

        image_duration = (
            audio_duration
            / image_count
        )

        if render_subtitles and subtitle_path is None:
            raise ValueError(
                "La renderización con subtítulos requiere subtitle_path."
            )

        subtitle_path = (
            Path(subtitle_path)
            if subtitle_path is not None
            else None
        )

        if render_subtitles and subtitle_offset != 0:
            subtitle_path = (
                self._shift_srt(
                    input_path=subtitle_path,
                    offset_seconds=subtitle_offset
                )
            )

        return VideoTimeline(
            audio_duration=audio_duration,
            image_duration=image_duration,
            subtitle_path=subtitle_path,
            scene_durations=self._scene_durations(
                scene_durations=tuple(scene_durations),
                image_count=image_count,
                audio_duration=audio_duration
            )
        )

    @staticmethod
    def _scene_durations(
        scene_durations,
        image_count,
        audio_duration
    ):
        if (
            len(scene_durations) != image_count
            or any(
                duration is None
                for duration in scene_durations
            )
            or abs(
                sum(scene_durations)
                - audio_duration
            ) > _DURATION_TOLERANCE
        ):
            return ()

        return (
            *scene_durations[:-1],
            audio_duration - sum(scene_durations[:-1])
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
