"""Kokoro implementation of the neutral TTS backend boundary.

Kokoro needs its own Python environment (torch and its dependencies), so it
runs in a separate process (``external_tts_process``): the worker
``workers/kokoro_worker.py`` loads the model and the voice from the declared
files, reads each segment of whole sentences and exits, freeing the GPU.
Every path and parameter comes from the voice document (model files, voice
file, ``lang_code`` and ``speed``); this class only knows the worker and which
options Kokoro accepts.
"""

from collections.abc import Mapping
from pathlib import Path

from app.modules.audio.external_tts_process import (
    ExternalTtsProcess,
    join_segment_wavs,
    parse_external_tts_runtime,
    parse_segmentation,
    reject_unknown_options,
    require_options_mapping,
    resolve_project_path,
    split_speech_segments,
)
from app.modules.audio.tts_contracts import (
    TtsAudioArtifact,
    TtsBackendDiagnostic,
    TtsBackendError,
    TtsBackendErrorKind,
    TtsSynthesisRequest,
    TtsSynthesisResult,
    TtsVoiceConfigurationError,
)


_BACKEND_KEY = "kokoro"
_ENGINE_LABEL = "Kokoro"
_WORKER_PATH = Path(__file__).resolve().parent / "workers" / "kokoro_worker.py"
_STAGED_AUDIO_NAME = "kokoro_audio.wav"
_OPTION_FIELDS = frozenset({"runtime", "model", "voice", "segmentation", "synthesis"})
_MODEL_FIELDS = frozenset({"repo_id", "config_path", "weights_path"})
_VOICE_FIELDS = frozenset({"path", "lang_code"})
_SYNTHESIS_FIELDS = frozenset({"speed"})


class KokoroBackend:
    """Synthesize one request with one Kokoro voice file.

    Consecutive sentences are read in one call up to the declared
    ``segmentation.max_characters``; the parent joins the segments with the
    declared pauses. A voice that declares ``seed`` gets the same audio for
    the same text in every run.
    """

    backend_key = _BACKEND_KEY

    def __init__(
        self,
        project_root: Path | str,
        *,
        process: ExternalTtsProcess | None = None,
        worker_path: Path | None = None,
    ):
        if not isinstance(project_root, (str, Path)) or not str(project_root).strip():
            raise TypeError("project_root must be a non-empty path.")
        self._project_root = Path(project_root).resolve(strict=False)
        self._process = process or ExternalTtsProcess()
        self._worker_path = Path(worker_path) if worker_path else _WORKER_PATH

    def synthesize(self, request: TtsSynthesisRequest) -> TtsSynthesisResult:
        """Create a validated 16-bit mono WAV only inside request.workspace."""
        if not isinstance(request, TtsSynthesisRequest):
            raise _backend_error(
                TtsBackendErrorKind.CONFIGURATION,
                "La solicitud técnica de Kokoro no es válida.",
            )
        if request.voice.backend_key != self.backend_key:
            raise _backend_error(
                TtsBackendErrorKind.CONFIGURATION,
                "La solicitud pertenece a otro backend TTS.",
            )

        engine_request = self._engine_request(request)
        runtime = parse_external_tts_runtime(
            request.voice.backend_options,
            self._project_root,
        )
        segments = split_speech_segments(
            request.text,
            sentence_pause_seconds=request.voice.prosody.sentence_pause_seconds,
            paragraph_pause_seconds=request.voice.prosody.paragraph_pause_seconds,
            max_characters=parse_segmentation(request.voice.backend_options),
        )
        if not segments:
            raise TtsVoiceConfigurationError(
                "el texto no tiene ninguna frase que leer."
            )

        workspace = request.workspace.path
        segment_paths, sample_rate_hz = self._process.run(
            engine_label=_ENGINE_LABEL,
            runtime=runtime,
            worker_path=self._worker_path,
            workspace=workspace,
            segments=segments,
            seed=request.voice.seed,
            engine_request=engine_request,
        )
        audio_path = workspace / _STAGED_AUDIO_NAME
        pauses = join_segment_wavs(
            segment_paths=segment_paths,
            segments=segments,
            output_path=audio_path,
            workspace=workspace,
            sample_rate_hz=sample_rate_hz,
        )
        return TtsSynthesisResult(
            staged_audio=TtsAudioArtifact(
                path=audio_path,
                container="wav",
                codec="pcm_s16le",
                sample_rate_hz=sample_rate_hz,
                channels=1,
            ),
            word_timings=None,
            pauses=pauses,
        )

    def _engine_request(self, request: TtsSynthesisRequest) -> dict[str, object]:
        """Validate Kokoro's own options and build its part of the request."""
        voice = request.voice
        if voice.backend_voice_id is not None:
            raise TtsVoiceConfigurationError(
                "Kokoro lee la voz de backend_options.voice.path: quita "
                "backend_voice_id."
            )
        if voice.prosody.speaking_rate != 1.0 or voice.prosody.volume_gain_db != 0.0:
            raise TtsVoiceConfigurationError(
                "Kokoro no admite cambiar prosody.speaking_rate ni "
                "prosody.volume_gain_db: deja 1.0 y 0.0 (la velocidad se "
                "declara en backend_options.synthesis.speed)."
            )
        options = voice.backend_options
        reject_unknown_options(options, _OPTION_FIELDS, "backend_options")

        model = require_options_mapping(options, "model", "backend_options")
        reject_unknown_options(model, _MODEL_FIELDS, "backend_options.model")
        repo_id = _require_text(model.get("repo_id"), "backend_options.model.repo_id")
        config_path = self._existing_file(model, "config_path", "backend_options.model")
        weights_path = self._existing_file(model, "weights_path", "backend_options.model")

        voice_options = require_options_mapping(options, "voice", "backend_options")
        reject_unknown_options(voice_options, _VOICE_FIELDS, "backend_options.voice")
        voice_path = self._existing_file(voice_options, "path", "backend_options.voice")
        lang_code = _require_text(
            voice_options.get("lang_code"),
            "backend_options.voice.lang_code",
        )

        synthesis = require_options_mapping(options, "synthesis", "backend_options")
        reject_unknown_options(synthesis, _SYNTHESIS_FIELDS, "backend_options.synthesis")
        speed = _require_positive_number(
            synthesis.get("speed"),
            "backend_options.synthesis.speed",
        )
        return {
            "repo_id": repo_id,
            "config_path": str(config_path),
            "weights_path": str(weights_path),
            "voice_path": str(voice_path),
            "lang_code": lang_code,
            "speed": speed,
        }

    def _existing_file(
        self,
        block: Mapping[str, object],
        name: str,
        block_label: str,
    ) -> Path:
        return resolve_project_path(
            block.get(name),
            self._project_root,
            f"{block_label}.{name}",
            must_be="file",
        )


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TtsVoiceConfigurationError(
            f"{label} debe ser un texto no vacío; se recibió {value!r}."
        )
    return value.strip()


def _require_positive_number(value: object, label: str) -> float:
    # Non-finite numbers never get here: the voice contract rejects them.
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise TtsVoiceConfigurationError(
            f"{label} debe ser un número mayor que 0; se recibió {value!r}."
        )
    return float(value)


def _backend_error(kind: TtsBackendErrorKind, detail: str) -> TtsBackendError:
    return TtsBackendError(TtsBackendDiagnostic(kind=kind, detail=detail))
