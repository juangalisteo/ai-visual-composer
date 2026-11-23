"""Piper ONNX implementation of the neutral TTS backend boundary.

This module intentionally contains no registry/provider composition.  A future
composition phase may expose ``PiperBackend`` under its technical key; this
class only turns one already-resolved neutral request into a private WAV
staging artifact.
"""

from collections.abc import Callable, Mapping
import json
import math
from pathlib import Path
import re
import wave

from app.modules.audio.tts_contracts import (
    TtsAudioArtifact,
    TtsBackendDiagnostic,
    TtsBackendError,
    TtsBackendErrorKind,
    TtsPause,
    TtsSynthesisRequest,
    TtsSynthesisResult,
)


_BACKEND_KEY = "piper_onnx"
_AUTHORIZED_RESOURCE_RELATIVE_ROOT = Path("models") / "audio" / "piper"
_STAGED_AUDIO_NAME = "piper_audio.wav"
_SYNTHESIS_FIELDS = frozenset(
    {
        "length_scale",
        "noise_scale",
        "noise_w_scale",
        "normalize_audio",
        "volume",
    }
)
_PARAGRAPH_BREAK = re.compile(r"\n[^\S\n]*\n\s*")
# An ellipsis plus any trailing marks or closing quotes, followed by a space.
_ELLIPSIS_BREAK = re.compile(r"(?:…|\.\.\.)[.?!…]*[\"'”’»)\]]*(?=\s)")


PiperVoiceFactory = Callable[[Path, Path], object]
SynthesisConfigFactory = Callable[..., object]
SeedSetter = Callable[[int], None]


class PiperBackend:
    """Synthesize one declaratively resolved mono-speaker Piper request.

    The backend has no model cache: each ``synthesize`` call loads exactly the
    model declared by that request.  This makes resource ownership and
    validation local to one workspace and avoids persistent ONNX state.

    A voice that declares ``seed`` fixes the noise Piper samples, so the same
    text gives the same audio in every run; without it, nothing is fixed.
    """

    backend_key = _BACKEND_KEY

    def __init__(
        self,
        project_root: Path | str,
        *,
        piper_voice_factory: PiperVoiceFactory | None = None,
        synthesis_config_factory: SynthesisConfigFactory | None = None,
        seed_setter: SeedSetter | None = None,
    ):
        self._project_root = _require_project_root(project_root)
        self._piper_voice_factory = piper_voice_factory or _default_piper_voice_factory
        self._synthesis_config_factory = (
            synthesis_config_factory or _default_synthesis_config_factory
        )
        self._seed_setter = seed_setter or _default_seed_setter

    def synthesize(self, request: TtsSynthesisRequest) -> TtsSynthesisResult:
        """Create a validated native-rate WAV only inside request.workspace."""
        try:
            self._validate_request(request)
        except Exception as error:
            raise _backend_error(
                TtsBackendErrorKind.CONFIGURATION,
                "La solicitud técnica de Piper no es válida.",
            ) from error

        try:
            model_path, sidecar_path, sidecar = self._resolve_model(request)
            self._validate_language(request.voice.language, sidecar)
        except TtsBackendError:
            raise
        except Exception as error:
            raise _backend_error(
                TtsBackendErrorKind.CONFIGURATION,
                "La configuración técnica de Piper no es válida.",
            ) from error

        try:
            voice = self._load_voice(model_path, sidecar_path, request.voice.seed)
        except TtsBackendError:
            raise
        except Exception as error:
            raise _backend_error(
                TtsBackendErrorKind.RESOURCE_UNAVAILABLE,
                "No se pudo cargar el recurso local de Piper.",
            ) from error

        try:
            sample_rate_hz = _sample_rate_from_voice(voice)
            synthesis_config = self._build_synthesis_config(request, sidecar)
        except TtsBackendError:
            raise
        except Exception as error:
            raise _backend_error(
                TtsBackendErrorKind.CONFIGURATION,
                "La configuración de síntesis Piper no es válida.",
            ) from error

        audio_path = request.workspace.path / _STAGED_AUDIO_NAME
        pauses = _synthesize_wav(
            voice=voice,
            text=request.text,
            audio_path=audio_path,
            synthesis_config=synthesis_config,
            sample_rate_hz=sample_rate_hz,
            sentence_pause_seconds=request.voice.prosody.sentence_pause_seconds,
            paragraph_pause_seconds=request.voice.prosody.paragraph_pause_seconds,
        )

        try:
            _validate_staged_wav(
                audio_path=audio_path,
                workspace_path=request.workspace.path,
                sample_rate_hz=sample_rate_hz,
            )
        except Exception as error:
            raise _backend_error(
                TtsBackendErrorKind.AUDIO_INVALID,
                "Piper no produjo un WAV de staging válido.",
            ) from error

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

    def _validate_request(self, request: object) -> None:
        if not isinstance(request, TtsSynthesisRequest):
            raise TypeError("request must be a TtsSynthesisRequest.")
        if request.voice.backend_key != self.backend_key:
            raise ValueError("La solicitud pertenece a otro backend TTS.")
        if request.voice.backend_voice_id is not None:
            raise ValueError("Piper mono-speaker no admite backend_voice_id.")

    def _resolve_model(
        self,
        request: TtsSynthesisRequest,
    ) -> tuple[Path, Path, Mapping[str, object]]:
        options = request.voice.backend_options
        _reject_unknown_keys(options, {"model", "synthesis"}, "backend_options")

        model_document = _required_mapping(options, "model")
        _reject_unknown_keys(model_document, {"onnx_path"}, "model")
        onnx_path = _required_text(model_document, "onnx_path")
        if "synthesis" in options:
            _validate_synthesis_document(options["synthesis"])

        declared_path = Path(onnx_path)
        if declared_path.is_absolute():
            raise ValueError("Piper onnx_path must be relative to the project root.")

        authorized_root = (
            self._project_root / _AUTHORIZED_RESOURCE_RELATIVE_ROOT
        ).resolve(strict=False)
        candidate = (self._project_root / declared_path).resolve(strict=False)
        try:
            candidate.relative_to(authorized_root)
        except ValueError as error:
            raise ValueError("Piper onnx_path escapes the authorized resource root.") from error

        if candidate.suffix.casefold() != ".onnx":
            raise ValueError("Piper onnx_path must reference an .onnx file.")
        _validate_resource_file(candidate, "Piper ONNX model")

        sidecar = Path(f"{candidate}.json")
        _validate_resource_file(sidecar, "Piper ONNX sidecar")
        try:
            document = json.loads(sidecar.read_text(encoding="utf-8"))
        except Exception as error:
            raise _backend_error(
                TtsBackendErrorKind.RESOURCE_UNAVAILABLE,
                "El sidecar JSON de Piper no se puede leer.",
            ) from error
        if not isinstance(document, Mapping):
            raise _backend_error(
                TtsBackendErrorKind.RESOURCE_UNAVAILABLE,
                "El sidecar JSON de Piper debe ser un objeto.",
            )
        return candidate, sidecar, document

    def _load_voice(
        self,
        model_path: Path,
        sidecar_path: Path,
        seed: int | None,
    ) -> object:
        try:
            if seed is not None:
                # Before loading: onnxruntime seeds the noise of the model
                # when it creates its session.
                self._seed_setter(seed)
            return self._piper_voice_factory(model_path, sidecar_path)
        except TtsBackendError:
            raise
        except Exception as error:
            raise _backend_error(
                TtsBackendErrorKind.RESOURCE_UNAVAILABLE,
                "No se pudo cargar el modelo ONNX de Piper.",
            ) from error

    def _build_synthesis_config(
        self,
        request: TtsSynthesisRequest,
        sidecar: Mapping[str, object],
    ) -> object:
        synthesis = _optional_mapping(request.voice.backend_options, "synthesis")
        if synthesis is None:
            synthesis = {}

        length_scale = synthesis.get("length_scale")
        if length_scale is None and "length_scale" not in synthesis:
            if request.voice.prosody.speaking_rate == 1.0:
                resolved_length_scale = None
            else:
                model_length_scale = _sidecar_model_length_scale(sidecar)
                resolved_length_scale = model_length_scale / request.voice.prosody.speaking_rate
        else:
            resolved_length_scale = length_scale

        if "volume" in synthesis:
            resolved_volume = synthesis["volume"]
        else:
            gain_db = request.voice.prosody.volume_gain_db
            resolved_volume = 1.0 if gain_db == 0.0 else 10 ** (gain_db / 20)
            _require_finite_nonnegative(resolved_volume, "resolved Piper volume")

        return self._synthesis_config_factory(
            speaker_id=None,
            length_scale=resolved_length_scale,
            noise_scale=synthesis.get("noise_scale"),
            noise_w_scale=synthesis.get("noise_w_scale"),
            normalize_audio=synthesis.get("normalize_audio", True),
            volume=resolved_volume,
        )

    @staticmethod
    def _validate_language(language: str, sidecar: Mapping[str, object]) -> None:
        espeak = _required_mapping(sidecar, "espeak")
        model_language = _required_text(espeak, "voice")
        if _primary_language_tag(language) != _primary_language_tag(model_language):
            raise ValueError("Configured language is incompatible with the Piper model.")


def _require_project_root(value: Path | str) -> Path:
    if not isinstance(value, (str, Path)):
        raise TypeError("project_root must be a path.")
    if isinstance(value, str) and not value.strip():
        raise ValueError("project_root must not be empty.")
    return Path(value).resolve(strict=False)


def _default_piper_voice_factory(model_path: Path, sidecar_path: Path) -> object:
    """Load one CPU-only Piper voice lazily after resource validation."""
    from piper import PiperVoice

    return PiperVoice.load(
        model_path,
        config_path=sidecar_path,
        use_cuda=False,
    )


def _default_seed_setter(seed: int) -> None:
    """Fix onnxruntime's seed for the sessions this process creates next.

    The seed is process-wide: sessions created later in the same process
    (another voice without ``seed``) also start from it.
    """
    import onnxruntime

    onnxruntime.set_seed(seed)


def _default_synthesis_config_factory(**kwargs: object) -> object:
    """Construct the exact piper-tts 1.8.0 synthesis data object lazily."""
    from piper import SynthesisConfig

    return SynthesisConfig(**kwargs)


def _validate_synthesis_document(value: object) -> None:
    synthesis = _required_mapping({"synthesis": value}, "synthesis")
    _reject_unknown_keys(synthesis, _SYNTHESIS_FIELDS, "synthesis")
    if "length_scale" in synthesis:
        _require_finite_positive(synthesis["length_scale"], "length_scale")
    for field_name in ("noise_scale", "noise_w_scale", "volume"):
        if field_name in synthesis:
            _require_finite_nonnegative(synthesis[field_name], field_name)
    if "normalize_audio" in synthesis and not isinstance(
        synthesis["normalize_audio"], bool
    ):
        raise TypeError("normalize_audio must be a bool.")


def _validate_resource_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise _backend_error(
            TtsBackendErrorKind.RESOURCE_UNAVAILABLE,
            f"{label} does not exist as a regular file.",
        ) from FileNotFoundError(str(path))
    if path.stat().st_size <= 0:
        raise _backend_error(
            TtsBackendErrorKind.RESOURCE_UNAVAILABLE,
            f"{label} is empty.",
        ) from ValueError(str(path))


def _sample_rate_from_voice(voice: object) -> int:
    sample_rate = getattr(getattr(voice, "config", None), "sample_rate", None)
    if isinstance(sample_rate, bool) or not isinstance(sample_rate, int) or sample_rate <= 0:
        raise ValueError("Piper voice must expose a positive integer sample rate.")
    return sample_rate


def _split_paragraphs(text: str) -> tuple[str, ...]:
    """Split text at one or more blank lines; single line breaks stay inside."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return tuple(
        paragraph.strip()
        for paragraph in _PARAGRAPH_BREAK.split(normalized)
        if paragraph.strip()
    )


def _split_after_ellipses(paragraph: str) -> tuple[str, ...]:
    """Cut after ``…`` or ``...``, which espeak-ng does not end as a sentence.

    Piper already yields one audio chunk per ``.``, ``?`` or ``!`` sentence, so
    only the ellipsis needs an explicit cut before synthesis.
    """
    pieces = []
    start = 0
    for match in _ELLIPSIS_BREAK.finditer(paragraph):
        pieces.append(paragraph[start : match.end()])
        start = match.end()
    pieces.append(paragraph[start:])
    return tuple(piece.strip() for piece in pieces if piece.strip())


def _synthesize_wav(
    *,
    voice: object,
    text: str,
    audio_path: Path,
    synthesis_config: object,
    sample_rate_hz: int,
    sentence_pause_seconds: float,
    paragraph_pause_seconds: float,
) -> tuple[TtsPause, ...]:
    """Write one WAV without allowing ``wave.close`` to hide synth failure.

    Returns the silences written between chunks.
    """
    try:
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        wav_file = wave.open(str(audio_path), "wb")
    except Exception as error:
        raise _backend_error(
            TtsBackendErrorKind.AUDIO_INVALID,
            "No se pudo preparar el WAV de staging de Piper.",
        ) from error

    try:
        pauses = _write_paced_chunks(
            voice=voice,
            text=text,
            wav_file=wav_file,
            synthesis_config=synthesis_config,
            sentence_pause_frames=_pause_frames(sentence_pause_seconds, sample_rate_hz),
            paragraph_pause_frames=_pause_frames(paragraph_pause_seconds, sample_rate_hz),
        )
    except Exception as error:
        try:
            wav_file.close()
        except Exception:
            pass
        raise _backend_error(
            TtsBackendErrorKind.SYNTHESIS,
            "La síntesis local con Piper falló.",
        ) from error

    try:
        wav_file.close()
    except Exception as error:
        raise _backend_error(
            TtsBackendErrorKind.AUDIO_INVALID,
            "Piper no finalizó un WAV de staging válido.",
        ) from error
    return pauses


def _write_paced_chunks(
    *,
    voice: object,
    text: str,
    wav_file: wave.Wave_write,
    synthesis_config: object,
    sentence_pause_frames: int,
    paragraph_pause_frames: int,
) -> tuple[TtsPause, ...]:
    """Write Piper sentence chunks with declared silence between them.

    A paragraph break replaces the sentence pause; nothing is added before the
    first chunk or after the last one. Returns where each written silence
    starts and ends, in seconds of the written audio.
    """
    pending_pause_frames = 0
    wrote_audio = False
    written_frames = 0
    frame_rate = None
    pauses = []
    for paragraph_index, paragraph in enumerate(_split_paragraphs(text)):
        if paragraph_index > 0 and wrote_audio:
            pending_pause_frames = paragraph_pause_frames
        for piece in _split_after_ellipses(paragraph):
            for chunk in voice.synthesize(piece, syn_config=synthesis_config):
                frame_bytes = chunk.sample_width * chunk.sample_channels
                if not wrote_audio:
                    wav_file.setframerate(chunk.sample_rate)
                    wav_file.setsampwidth(chunk.sample_width)
                    wav_file.setnchannels(chunk.sample_channels)
                    frame_rate = chunk.sample_rate
                    wrote_audio = True
                if pending_pause_frames:
                    wav_file.writeframes(bytes(pending_pause_frames * frame_bytes))
                    pauses.append(
                        TtsPause(
                            start_seconds=written_frames / frame_rate,
                            end_seconds=(written_frames + pending_pause_frames)
                            / frame_rate,
                        )
                    )
                    written_frames += pending_pause_frames
                wav_file.writeframes(chunk.audio_int16_bytes)
                written_frames += len(chunk.audio_int16_bytes) // frame_bytes
                pending_pause_frames = sentence_pause_frames
    return tuple(pauses)


def _pause_frames(seconds: float, sample_rate_hz: int) -> int:
    return round(seconds * sample_rate_hz)


def _validate_staged_wav(
    *,
    audio_path: Path,
    workspace_path: Path,
    sample_rate_hz: int,
) -> None:
    workspace = workspace_path.resolve(strict=False)
    resolved_audio_path = audio_path.resolve(strict=False)
    try:
        resolved_audio_path.relative_to(workspace)
    except ValueError as error:
        raise ValueError("Piper staging audio escaped its workspace.") from error
    if not resolved_audio_path.is_file():
        raise FileNotFoundError("Piper did not create the staging WAV.")
    if resolved_audio_path.stat().st_size <= 0:
        raise ValueError("Piper created an empty staging WAV.")

    with wave.open(str(resolved_audio_path), "rb") as wav_file:
        if wav_file.getcomptype() != "NONE":
            raise ValueError("Piper staging WAV must use PCM samples.")
        if wav_file.getsampwidth() != 2:
            raise ValueError("Piper staging WAV must use signed 16-bit PCM.")
        if wav_file.getnchannels() != 1:
            raise ValueError("Piper staging WAV must be mono.")
        if wav_file.getframerate() != sample_rate_hz:
            raise ValueError("Piper staging WAV sample rate differs from the model.")
        if wav_file.getnframes() <= 0:
            raise ValueError("Piper staging WAV contains no audio frames.")


def _sidecar_model_length_scale(sidecar: Mapping[str, object]) -> float:
    inference = _required_mapping(sidecar, "inference")
    return _require_finite_positive(
        _required_value(inference, "length_scale"),
        "model inference.length_scale",
    )


def _primary_language_tag(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("language must be non-empty text.")
    primary = value.strip().replace("_", "-").split("-", 1)[0].casefold()
    if not primary.isalpha():
        raise ValueError("language must start with an alphabetic primary subtag.")
    return primary


def _required_mapping(document: Mapping[str, object], name: str) -> Mapping[str, object]:
    value = _required_value(document, name)
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be an object.")
    return value


def _optional_mapping(
    document: Mapping[str, object], name: str
) -> Mapping[str, object] | None:
    if name not in document:
        return None
    return _required_mapping(document, name)


def _required_value(document: Mapping[str, object], name: str) -> object:
    if name not in document:
        raise ValueError(f"{name} is required.")
    return document[name]


def _required_text(document: Mapping[str, object], name: str) -> str:
    value = _required_value(document, name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text.")
    return value.strip()


def _reject_unknown_keys(
    document: Mapping[str, object], allowed: set[str] | frozenset[str], name: str
) -> None:
    unknown = set(document) - set(allowed)
    if unknown:
        raise ValueError(f"Unknown {name} fields: {', '.join(sorted(unknown))}.")


def _require_finite_positive(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number.")
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and greater than zero.")
    return float(value)


def _require_finite_nonnegative(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number.")
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and non-negative.")
    return float(value)


def _backend_error(
    kind: TtsBackendErrorKind,
    detail: str,
) -> TtsBackendError:
    return TtsBackendError(TtsBackendDiagnostic(kind=kind, detail=detail))
