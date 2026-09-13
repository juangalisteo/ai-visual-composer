from dataclasses import dataclass
from pathlib import Path

from app.modules.subtitles.subtitle_builder import SubtitleBuilder
from app.modules.subtitles.timing import SubtitleTimingResolver
from app.modules.video.ffmpeg.runner import Runner


@dataclass(frozen=True)
class PreparedExternalMediaSubtitles:
    audio_path: Path
    subtitle_path: Path
    timing: object


class ExternalMediaSubtitlePreparationService:
    """Prepare canonical Whisper subtitles from an external media source."""

    def __init__(
        self,
        runner=None,
        subtitle_builder=None,
        timing_resolver=None,
    ):
        self.runner = runner or Runner()
        self.subtitle_builder = subtitle_builder or SubtitleBuilder()
        self.timing_resolver = timing_resolver or SubtitleTimingResolver()

    def prepare(
        self,
        video_path=None,
        working_directory=None,
        media_path=None,
    ):
        if media_path is not None and video_path is not None:
            raise ValueError(
                "La preparacion externa recibe un unico medio fuente."
            )
        source_path = Path(media_path or video_path)
        working_directory = Path(working_directory)
        if not source_path.is_file():
            raise FileNotFoundError(
                f"No existe el medio de subtitulos: {source_path}"
            )

        extension = source_path.suffix.lower()
        if extension not in {".mp4", ".mp3"}:
            raise ValueError(
                "El medio de subtitulos debe ser MP4 o MP3: "
                f"{source_path}"
            )

        working_directory.mkdir(parents=True, exist_ok=True)
        subtitle_path = working_directory / "whisper.srt"
        if extension == ".mp4":
            audio_path = working_directory / "source_audio.wav"
            self.runner.run([
                "ffmpeg",
                "-y",
                "-i",
                str(source_path),
                "-map",
                "0:a:0",
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                str(audio_path),
            ])
            if not audio_path.is_file() or audio_path.stat().st_size <= 0:
                raise RuntimeError(
                    "No se genero el audio de trabajo para Whisper."
                )
        else:
            audio_path = source_path

        self.subtitle_builder.build(
            audio_path=audio_path,
            output_path=subtitle_path,
        )
        timing = self.timing_resolver.resolve(
            subtitle_path=subtitle_path,
            audio_path=audio_path,
        )
        if timing is None or not timing.is_usable():
            raise RuntimeError(
                "Whisper no produjo word timestamps utilizables."
            )
        return PreparedExternalMediaSubtitles(
            audio_path=audio_path,
            subtitle_path=subtitle_path,
            timing=timing,
        )
