from dataclasses import dataclass
from pathlib import Path

from app.modules.subtitles.io.subtitle_builder import SubtitleBuilder
from app.modules.subtitles.io.whisper_diagnostics import (
    WhisperDiagnosticsParser,
    WhisperTranscriptionDiagnostics,
)
from app.modules.subtitles.io.whisper_diagnostics_writer import (
    WhisperDiagnosticsWriter,
)
from app.modules.subtitles.policies.timing import (
    SubtitleTimingResolver,
    whisper_timing_path,
)
from app.modules.video.ffmpeg.runner import Runner
from app.shared.operational_error import create_operational_error


@dataclass(frozen=True)
class PreparedExternalMediaSubtitles:
    audio_path: Path
    subtitle_path: Path
    timing: object
    diagnostics: WhisperTranscriptionDiagnostics | None = None


class ExternalMediaSubtitlePreparationService:
    """Prepare canonical Whisper subtitles from an external media source."""

    SUPPORTED_EXTENSIONS = (".mp4", ".mp3")

    def __init__(
        self,
        runner=None,
        subtitle_builder=None,
        timing_resolver=None,
        diagnostics_parser=None,
        diagnostics_writer=None,
    ):
        self.runner = runner or Runner()
        self.subtitle_builder = subtitle_builder or SubtitleBuilder()
        self.timing_resolver = timing_resolver or SubtitleTimingResolver()
        self.diagnostics_parser = (
            diagnostics_parser
            or WhisperDiagnosticsParser()
        )
        self.diagnostics_writer = (
            diagnostics_writer
            or WhisperDiagnosticsWriter()
        )

    def prepare(
        self,
        video_path=None,
        working_directory=None,
        media_path=None,
        diagnostics_output_path=None,
    ):
        if media_path is not None and video_path is not None:
            raise ValueError(
                "La preparación externa recibe un único medio fuente."
            )
        source_path = Path(media_path or video_path)
        working_directory = Path(working_directory)
        if not source_path.is_file():
            raise FileNotFoundError(
                f"No existe el medio de subtítulos: {source_path}"
            )

        extension = source_path.suffix.lower()
        if extension not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(
                "El medio de subtítulos debe ser MP4 o MP3: "
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
                    "No se generó el audio de trabajo para Whisper."
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
        diagnostics = self._resolve_diagnostics(subtitle_path)
        self._write_diagnostics(
            diagnostics,
            diagnostics_output_path,
        )
        return PreparedExternalMediaSubtitles(
            audio_path=audio_path,
            subtitle_path=subtitle_path,
            timing=timing,
            diagnostics=diagnostics,
        )

    def _resolve_diagnostics(self, subtitle_path):
        transcription_config = getattr(
            self.subtitle_builder,
            "transcription_config",
            None,
        )
        if transcription_config is None:
            return None
        try:
            return self.diagnostics_parser.parse(
                whisper_timing_path(subtitle_path),
                transcription_config,
            )
        except (OSError, TypeError, ValueError):
            return None

    def _write_diagnostics(self, diagnostics, output_path):
        if diagnostics is None or output_path is None:
            return
        try:
            self.diagnostics_writer.write(
                diagnostics,
                output_path,
            )
        except OSError as error:
            raise create_operational_error(
                family="FILESYSTEM",
                user_message=(
                    "No se pudo guardar el diagnóstico Whisper solicitado."
                ),
                recommended_action=(
                    "Comprueba la ruta elegida para el diagnóstico."
                ),
                operation="Guardar diagnóstico Whisper",
                resource=str(output_path),
                technical_metadata={
                    "phase": "whisper_diagnostics",
                },
            ) from error
