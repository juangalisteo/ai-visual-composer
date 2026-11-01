"""Pure, immutable contracts for the neutral TTS boundary.

These types intentionally do not load voice configuration, synthesize audio,
access the filesystem, or select a backend. Runtime adoption belongs to later
phases; this module only represents validated data exchanged across that future
boundary.
"""

from dataclasses import dataclass, field
from enum import Enum
import math
from pathlib import Path
from types import MappingProxyType
from typing import Mapping


class TtsArtifactOwnership(str, Enum):
    """Explicit lifecycle owner for a TTS artifact state."""

    VOICE_BUILDER_WORKSPACE = "voice_builder_workspace"
    VOICE_BUILDER_STAGING = "voice_builder_staging"
    CALLER_OWNED = "caller_owned"


class TtsBackendErrorKind(str, Enum):
    """Technical backend failure categories without provider semantics."""

    CONFIGURATION = "configuration"
    RESOURCE_UNAVAILABLE = "resource_unavailable"
    SYNTHESIS = "synthesis"
    AUDIO_INVALID = "audio_invalid"
    TIMING_UNAVAILABLE = "timing_unavailable"


@dataclass(frozen=True)
class TtsBackendDiagnostic:
    """Safe technical classification carried inside the TTS boundary."""

    kind: TtsBackendErrorKind
    detail: str
    retryable: bool = False

    def __post_init__(self):
        object.__setattr__(self, "kind", TtsBackendErrorKind(self.kind))
        object.__setattr__(self, "detail", _required_text(self.detail, "detail"))
        _require_bool(self.retryable, "retryable")


class TtsBackendError(RuntimeError):
    """Neutral technical failure that a future TTS backend may raise."""

    def __init__(self, diagnostic: TtsBackendDiagnostic):
        if not isinstance(diagnostic, TtsBackendDiagnostic):
            raise TypeError("diagnostic must be a TtsBackendDiagnostic.")
        self.diagnostic = diagnostic
        super().__init__(diagnostic.detail)


class TtsVoiceConfigurationError(ValueError):
    """Invalid voice-document value whose Spanish message reaches the user."""


@dataclass(frozen=True)
class TtsProsody:
    """Backend-neutral semantic prosody expressed in stable units.

    The pauses are extra silence, in seconds, written after a sentence end and
    between paragraphs (one or more blank lines); 0 adds no extra silence.
    """

    speaking_rate: float = 1.0
    volume_gain_db: float = 0.0
    sentence_pause_seconds: float = 0.0
    paragraph_pause_seconds: float = 0.0

    def __post_init__(self):
        _require_finite_number(self.speaking_rate, "speaking_rate")
        if self.speaking_rate <= 0:
            raise ValueError("speaking_rate must be greater than zero.")
        _require_finite_number(self.volume_gain_db, "volume_gain_db")
        _require_pause_seconds(self.sentence_pause_seconds, "sentence_pause_seconds")
        _require_pause_seconds(self.paragraph_pause_seconds, "paragraph_pause_seconds")


@dataclass(frozen=True)
class ResolvedTtsVoice:
    """Technical voice settings already resolved for one TTS request."""

    voice_id: str
    backend_key: str
    backend_voice_id: str | None
    language: str
    prosody: TtsProsody = field(default_factory=TtsProsody)
    backend_options: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "voice_id", _required_text(self.voice_id, "voice_id"))
        object.__setattr__(self, "backend_key", _required_text(self.backend_key, "backend_key"))
        object.__setattr__(self, "language", _required_text(self.language, "language"))
        if self.backend_voice_id is not None:
            object.__setattr__(
                self,
                "backend_voice_id",
                _required_text(self.backend_voice_id, "backend_voice_id"),
            )
        if not isinstance(self.prosody, TtsProsody):
            raise TypeError("prosody must be a TtsProsody.")
        object.__setattr__(
            self,
            "backend_options",
            _freeze_options(self.backend_options),
        )


@dataclass(frozen=True)
class TtsSynthesisWorkspace:
    """VoiceBuilder-owned private staging location for one request."""

    workspace_id: str
    path: Path
    ownership: TtsArtifactOwnership = (
        TtsArtifactOwnership.VOICE_BUILDER_WORKSPACE
    )

    def __post_init__(self):
        object.__setattr__(
            self,
            "workspace_id",
            _required_text(self.workspace_id, "workspace_id"),
        )
        path = _coerce_non_current_path(self.path, "path")
        ownership = TtsArtifactOwnership(self.ownership)
        if ownership is not TtsArtifactOwnership.VOICE_BUILDER_WORKSPACE:
            raise ValueError("TTS workspaces must be VoiceBuilder-owned.")
        object.__setattr__(self, "path", path)
        object.__setattr__(self, "ownership", ownership)


@dataclass(frozen=True)
class TtsSynthesisRequest:
    """Pure input handed to a resolved technical TTS backend."""

    text: str
    voice: ResolvedTtsVoice
    workspace: TtsSynthesisWorkspace
    require_word_timings: bool = True

    def __post_init__(self):
        object.__setattr__(self, "text", _required_text(self.text, "text"))
        if not isinstance(self.voice, ResolvedTtsVoice):
            raise TypeError("voice must be a ResolvedTtsVoice.")
        if not isinstance(self.workspace, TtsSynthesisWorkspace):
            raise TypeError("workspace must be a TtsSynthesisWorkspace.")
        _require_bool(self.require_word_timings, "require_word_timings")


@dataclass(frozen=True)
class TtsAudioArtifact:
    """Validated staging audio returned by a backend to VoiceBuilder."""

    path: Path
    container: str
    codec: str
    sample_rate_hz: int
    channels: int
    ownership: TtsArtifactOwnership = TtsArtifactOwnership.VOICE_BUILDER_STAGING

    def __post_init__(self):
        object.__setattr__(self, "path", _coerce_non_current_path(self.path, "path"))
        object.__setattr__(self, "container", _required_text(self.container, "container"))
        object.__setattr__(self, "codec", _required_text(self.codec, "codec"))
        _require_positive_int(self.sample_rate_hz, "sample_rate_hz")
        _require_positive_int(self.channels, "channels")
        ownership = TtsArtifactOwnership(self.ownership)
        if ownership is not TtsArtifactOwnership.VOICE_BUILDER_STAGING:
            raise ValueError("Backend audio results must be VoiceBuilder staging artifacts.")
        object.__setattr__(self, "ownership", ownership)


@dataclass(frozen=True)
class TtsWordTiming:
    """One backend-neutral word interval expressed in seconds."""

    text: str
    start_seconds: float
    end_seconds: float

    def __post_init__(self):
        object.__setattr__(self, "text", _required_text(self.text, "text"))
        _require_finite_number(self.start_seconds, "start_seconds")
        _require_finite_number(self.end_seconds, "end_seconds")
        if self.start_seconds < 0 or self.end_seconds < 0:
            raise ValueError("word timing values must not be negative.")
        if self.end_seconds < self.start_seconds:
            raise ValueError("end_seconds must not precede start_seconds.")


@dataclass(frozen=True)
class TtsPause:
    """One silence the backend inserted, in seconds of the staged audio."""

    start_seconds: float
    end_seconds: float

    def __post_init__(self):
        _require_finite_number(self.start_seconds, "start_seconds")
        _require_finite_number(self.end_seconds, "end_seconds")
        if self.start_seconds < 0:
            raise ValueError("pause start_seconds must not be negative.")
        if self.end_seconds <= self.start_seconds:
            raise ValueError("pause end_seconds must follow start_seconds.")


@dataclass(frozen=True)
class TtsSynthesisResult:
    """Backend result before VoiceBuilder validates and publishes artifacts.

    ``pauses`` are the silences the backend wrote into the audio itself, in
    order; a backend that inserts none leaves them empty.
    """

    staged_audio: TtsAudioArtifact
    word_timings: tuple[TtsWordTiming, ...] | None
    diagnostic: TtsBackendDiagnostic | None = None
    pauses: tuple[TtsPause, ...] = ()

    def __post_init__(self):
        if not isinstance(self.staged_audio, TtsAudioArtifact):
            raise TypeError("staged_audio must be a TtsAudioArtifact.")
        if self.staged_audio.ownership is not TtsArtifactOwnership.VOICE_BUILDER_STAGING:
            raise ValueError("staged_audio must remain VoiceBuilder staging.")

        if self.word_timings is not None:
            timings = tuple(self.word_timings)
            if not timings:
                raise ValueError("word_timings must be None or contain word timings.")
            previous_end = None
            for timing in timings:
                if not isinstance(timing, TtsWordTiming):
                    raise TypeError("word_timings must contain TtsWordTiming values.")
                if previous_end is not None and timing.start_seconds < previous_end:
                    raise ValueError("word timings must be ordered and non-overlapping.")
                previous_end = timing.end_seconds
            object.__setattr__(self, "word_timings", timings)

        if self.diagnostic is not None and not isinstance(
            self.diagnostic,
            TtsBackendDiagnostic,
        ):
            raise TypeError("diagnostic must be a TtsBackendDiagnostic or None.")

        pauses = tuple(self.pauses)
        previous_end = None
        for pause in pauses:
            if not isinstance(pause, TtsPause):
                raise TypeError("pauses must contain TtsPause values.")
            if previous_end is not None and pause.start_seconds < previous_end:
                raise ValueError("pauses must be ordered and non-overlapping.")
            previous_end = pause.end_seconds
        object.__setattr__(self, "pauses", pauses)


def _required_text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be text.")
    text = value.strip()
    if not text:
        raise ValueError(f"{name} must not be empty.")
    return text


def _coerce_non_current_path(value: object, name: str) -> Path:
    if not isinstance(value, (str, Path)):
        raise TypeError(f"{name} must be a path.")
    if isinstance(value, str) and not value.strip():
        raise ValueError(f"{name} must not be empty.")
    path = Path(value)
    if path == Path("."):
        raise ValueError(f"{name} must not be the current directory.")
    return path


def _require_bool(value: object, name: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a bool.")


def _require_finite_number(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number.")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite.")


def _require_pause_seconds(value: object, name: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise TtsVoiceConfigurationError(
            f"prosody.{name} debe ser un número de segundos mayor o igual que 0 "
            f"(0 = sin pausa extra); se recibió {value!r}."
        )


def _require_positive_int(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer.")
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero.")


def _freeze_options(options: Mapping[str, object]) -> Mapping[str, object]:
    if not isinstance(options, Mapping):
        raise TypeError("backend_options must be a mapping.")
    return MappingProxyType(
        {
            _required_text(key, "backend_options key"): _freeze_option_value(value)
            for key, value in options.items()
        }
    )


def _freeze_option_value(value: object) -> object:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        _require_finite_number(value, "backend_options value")
        return value
    if isinstance(value, Mapping):
        return _freeze_options(value)
    if isinstance(value, (tuple, list)):
        return tuple(_freeze_option_value(item) for item in value)
    raise TypeError("backend_options values must be JSON-like data.")
