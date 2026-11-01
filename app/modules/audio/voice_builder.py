"""Stable VoiceBuilder facade over the neutral TTS backend boundary."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from app.managers.project_manager import ProjectManager
from app.modules.audio.tts_contracts import (
    TtsAudioArtifact,
    TtsBackendError,
    TtsSynthesisRequest,
    TtsSynthesisResult,
    TtsSynthesisWorkspace,
    TtsVoiceConfigurationError,
)
from app.modules.audio.tts_backend_runtime import build_default_tts_backend_registry
from app.modules.audio.voice_timing_adapter import VoiceTimingAdapter
from app.shared.config_manager import ConfigManager
from app.shared.operational_error import OperationalError, create_operational_error
from app.shared.progress_logger import ProgressLogger


class VoiceBuilder:
    """Publish project voice audio without exposing a concrete TTS backend."""

    def __init__(
        self,
        config_manager=None,
        backend_registry=None,
        timing_adapter=None,
        workspace_parent=None,
    ):
        self._config_manager = (
            config_manager if config_manager is not None else ConfigManager()
        )
        self._backend_registry = (
            backend_registry
            if backend_registry is not None
            else build_default_tts_backend_registry()
        )
        self._timing_adapter = (
            timing_adapter if timing_adapter is not None else VoiceTimingAdapter()
        )
        self._workspace_parent = (
            Path(workspace_parent) if workspace_parent is not None else None
        )
        # Silences the backend wrote into the last published voice
        # (``TtsPause``, seconds of the published audio); empty otherwise.
        self.last_pauses = ()

    def build(
        self,
        text,
        output_path=None,
    ):
        """Generate and publish one voice artifact at the established path."""
        ProgressLogger.start("GENERANDO VOCES")
        start = time.perf_counter()
        self.last_pauses = ()

        if not str(text).strip():
            raise ValueError(
                "No se puede generar voz a partir de un texto vacío."
            )

        if output_path is None:
            output_path = ProjectManager().audio_path()
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        workspace_path = None
        voice = None
        try:
            configuration = self._config_manager.get_tts_voice_configuration()
            voice = configuration.voice
            backend = self._backend_registry.resolve(voice.backend_key)
            workspace_path = self._create_workspace()
            request = TtsSynthesisRequest(
                text=text,
                voice=voice,
                workspace=TtsSynthesisWorkspace(
                    workspace_id=workspace_path.name,
                    path=workspace_path,
                ),
            )
            result = backend.synthesize(request)
            self._validate_result(result, request.workspace)

            # Validate neutral timing without persisting provider-specific
            # metadata. Subtitle timing now resolves from Whisper or None.
            self._timing_adapter.adapt(result.word_timings)
            self._publish_audio(result.staged_audio, output_path)
            self.last_pauses = result.pauses
        except OperationalError:
            raise
        except Exception as error:
            raise self._operational_error(
                error=error,
                output_path=output_path,
                voice=voice,
            ) from error
        finally:
            if workspace_path is not None:
                self._cleanup_workspace(workspace_path)

        elapsed = time.perf_counter() - start
        ProgressLogger.finish("Finalizado", elapsed)
        return output_path

    def _create_workspace(self) -> Path:
        if self._workspace_parent is not None:
            self._workspace_parent.mkdir(parents=True, exist_ok=True)
        return Path(
            tempfile.mkdtemp(
                prefix="ai_visual_composer_tts_",
                dir=self._workspace_parent,
            )
        )

    @staticmethod
    def _validate_result(
        result: object,
        workspace: TtsSynthesisWorkspace,
    ) -> None:
        if not isinstance(result, TtsSynthesisResult):
            raise TypeError("TTS backend must return a TtsSynthesisResult.")

        workspace_path = workspace.path.resolve()
        staged_audio_path = result.staged_audio.path.resolve()
        try:
            staged_audio_path.relative_to(workspace_path)
        except ValueError as error:
            raise ValueError(
                "TTS backend audio must remain inside the private workspace."
            ) from error

        if not staged_audio_path.is_file():
            raise FileNotFoundError(
                "La generación de voz terminó, pero no se encontró el "
                f"archivo de staging: {staged_audio_path}"
            )
        if staged_audio_path.stat().st_size <= 0:
            raise ValueError("El archivo de voz de staging está vacío.")

    @classmethod
    def _publish_audio(
        cls,
        staged_audio: TtsAudioArtifact,
        output_path: Path,
    ) -> None:
        """Publish a neutral staging artifact at the current public path.

        The established public contract is ``voz.mp3``. Native MP3 artifacts
        retain the historical byte-for-byte publication. Lossless WAV staging
        is encoded only at this public boundary, where current consumers need
        an MP3 artifact; it is never down-converted inside a backend workspace.
        """
        staged_audio_path = staged_audio.path
        if cls._can_copy_to_public_path(staged_audio, output_path):
            shutil.copyfile(staged_audio_path, output_path)
        elif output_path.suffix.casefold() == ".mp3":
            cls._transcode_to_mp3(staged_audio_path, output_path)
        else:
            # Preserve the historic generic behavior for an explicitly chosen
            # non-MP3 public path.
            shutil.copyfile(staged_audio_path, output_path)
        if not output_path.is_file():
            raise FileNotFoundError(
                "La generación de voz terminó sin crear el archivo esperado: "
                f"{output_path}"
            )
        if output_path.stat().st_size <= 0:
            raise ValueError("La generación de voz creó un archivo vacío.")

    @staticmethod
    def _can_copy_to_public_path(
        staged_audio: TtsAudioArtifact,
        output_path: Path,
    ) -> bool:
        return (
            output_path.suffix.casefold() == ".mp3"
            and staged_audio.container.casefold() == "mp3"
            and staged_audio.codec.casefold() == "mp3"
        )

    @staticmethod
    def _transcode_to_mp3(staged_audio_path: Path, output_path: Path) -> None:
        command = [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-i",
            str(staged_audio_path),
            "-map",
            "0:a:0",
            "-c:a",
            "libmp3lame",
            "-q:a",
            "0",
            str(output_path),
        ]
        subprocess.run(command, capture_output=True, text=True, check=True)

    @staticmethod
    def _cleanup_workspace(workspace_path: Path) -> None:
        try:
            shutil.rmtree(workspace_path)
        except OSError:
            # Staging cleanup must never hide the backend or publication result.
            pass

    @staticmethod
    def _operational_error(*, error, output_path: Path, voice):
        technical_metadata = {"phase": "voice_generation"}
        if voice is not None:
            technical_metadata["voice_id"] = voice.voice_id
            technical_metadata["backend_key"] = voice.backend_key
        if isinstance(error, TtsBackendError):
            technical_metadata["backend_error_kind"] = error.diagnostic.kind.value
        if isinstance(error, TtsVoiceConfigurationError):
            return create_operational_error(
                family="CONFIG",
                user_message=f"La configuración de la voz no es válida: {error}",
                recommended_action=(
                    "Corrige el documento de la voz en config/voice_configs/."
                ),
                operation="Generar voz",
                resource=str(output_path),
                technical_metadata=technical_metadata,
            )

        return create_operational_error(
            family="AUDIO",
            user_message="No se pudo generar la voz.",
            recommended_action=(
                "Comprueba la configuración de voz y la disponibilidad del "
                "backend de síntesis."
            ),
            operation="Generar voz",
            resource=str(output_path),
            technical_metadata=technical_metadata,
        )
