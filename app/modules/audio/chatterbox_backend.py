"""Chatterbox Multilingual implementation of the neutral TTS backend boundary.

Chatterbox needs its own Python environment (torch and its dependencies), so
it runs in a separate process (``external_tts_process``): the worker
``workers/chatterbox_worker.py`` loads the model from the declared checkpoint
folder, reads each segment of whole sentences and exits, freeing the GPU. Every path and
parameter comes from the voice document; this class only knows the worker
and which options Chatterbox accepts.
"""

from collections.abc import Mapping
from pathlib import Path

from app.modules.audio.external_tts_process import (
    ExternalTtsProcess,
    join_segment_wavs,
    parse_external_tts_runtime,
    parse_segmentation,
    reject_unknown_options,
    require_non_negative_number,
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


_BACKEND_KEY = "chatterbox_multilingual"
_ENGINE_LABEL = "Chatterbox"
_WORKER_PATH = Path(__file__).resolve().parent / "workers" / "chatterbox_worker.py"
_STAGED_AUDIO_NAME = "chatterbox_audio.wav"
# Files ChatterboxMultilingualTTS.from_local reads from the checkpoint folder.
_CHECKPOINT_FILES = (
    "ve.pt",
    "t3_mtl23ls_v2.safetensors",
    "s3gen.pt",
    "grapheme_mtl_merged_expanded_v1.json",
    "conds.pt",
)
_OPTION_FIELDS = frozenset({"runtime", "model", "segmentation", "synthesis"})
_MODEL_FIELDS = frozenset({"checkpoint_dir"})
# Optional arguments of ChatterboxMultilingualTTS.generate.
_SYNTHESIS_FIELDS = frozenset(
    {
        "exaggeration",
        "cfg_weight",
        "temperature",
        "repetition_penalty",
        "min_p",
        "top_p",
    }
)


class ChatterboxBackend:
    """Synthesize one request with Chatterbox Multilingual's built-in voice.

    Consecutive sentences are read in one ``generate`` call up to the
    declared ``segmentation.max_characters`` (one call reads at most ~40 s);
    the parent joins the segments with the declared pauses. A voice that declares
    ``seed`` gets the same audio for the same text in every run.
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
                "La solicitud técnica de Chatterbox no es válida.",
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
        """Validate Chatterbox's own options and build its part of the request."""
        voice = request.voice
        if voice.backend_voice_id is not None:
            raise TtsVoiceConfigurationError(
                "Chatterbox usa su voz de serie: quita backend_voice_id."
            )
        if voice.prosody.speaking_rate != 1.0 or voice.prosody.volume_gain_db != 0.0:
            raise TtsVoiceConfigurationError(
                "Chatterbox no admite cambiar prosody.speaking_rate ni "
                "prosody.volume_gain_db: deja 1.0 y 0.0."
            )
        options = voice.backend_options
        reject_unknown_options(options, _OPTION_FIELDS, "backend_options")
        model = require_options_mapping(options, "model", "backend_options")
        reject_unknown_options(model, _MODEL_FIELDS, "backend_options.model")
        checkpoint_dir = resolve_project_path(
            model.get("checkpoint_dir"),
            self._project_root,
            "backend_options.model.checkpoint_dir",
            must_be="dir",
        )
        for file_name in _CHECKPOINT_FILES:
            resolve_project_path(
                (Path(str(model["checkpoint_dir"]).strip()) / file_name).as_posix(),
                self._project_root,
                "backend_options.model.checkpoint_dir",
                must_be="file",
            )

        synthesis = options.get("synthesis", {})
        if not isinstance(synthesis, Mapping):
            raise TtsVoiceConfigurationError(
                "backend_options.synthesis debe ser un objeto; se recibió "
                f"{synthesis!r}."
            )
        reject_unknown_options(synthesis, _SYNTHESIS_FIELDS, "backend_options.synthesis")
        return {
            "checkpoint_dir": str(checkpoint_dir),
            "language_id": _language_id(voice.language),
            "synthesis": {
                name: require_non_negative_number(
                    value,
                    f"backend_options.synthesis.{name}",
                )
                for name, value in synthesis.items()
            },
        }


def _language_id(language: str) -> str:
    """Primary subtag of the voice's BCP 47 language (``es-ES`` → ``es``)."""
    primary = language.replace("_", "-").split("-", 1)[0].casefold()
    if not primary.isalpha():
        raise TtsVoiceConfigurationError(
            f"language debe ser una etiqueta de idioma como «es-ES»; se recibió "
            f"{language!r}."
        )
    return primary


def _backend_error(kind: TtsBackendErrorKind, detail: str) -> TtsBackendError:
    return TtsBackendError(TtsBackendDiagnostic(kind=kind, detail=detail))
