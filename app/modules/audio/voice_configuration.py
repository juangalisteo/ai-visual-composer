"""Neutral declarative voice-configuration parsing.

This module validates data already loaded from JSON. It neither selects a
backend nor performs synthesis.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from app.core.script_length import SpeechPacing
from app.modules.audio.tts_contracts import (
    ResolvedTtsVoice,
    TtsProsody,
    TtsVoiceConfigurationError,
)


_VOICE_CONFIGURATION_KIND = "tts_voice"
_PROSODY_FIELDS = (
    "speaking_rate",
    "volume_gain_db",
    "sentence_pause_seconds",
    "paragraph_pause_seconds",
)
_OPTIONAL_PROSODY_FIELDS = frozenset(
    {"sentence_pause_seconds", "paragraph_pause_seconds"}
)
# Measured reading rate; needed only to size a script generated from a topic.
_PACING_FIELDS = (
    "letters_per_second",
    "words_per_second",
)
_VOICE_CONFIGURATION_FIELDS = frozenset(
    {
        "kind",
        "voice_id",
        "display_name",
        "backend_key",
        "backend_voice_id",
        "language",
        "prosody",
        "pacing",
        "backend_options",
    }
)


@dataclass(frozen=True)
class TtsVoiceConfiguration:
    """One declarative, presentation-separated technical voice document."""

    voice: ResolvedTtsVoice
    display_name: str
    kind: str = _VOICE_CONFIGURATION_KIND
    # None when the document does not declare its reading rate.
    pacing: SpeechPacing | None = None

    def __post_init__(self):
        if self.kind != _VOICE_CONFIGURATION_KIND:
            raise ValueError(f"kind must be {_VOICE_CONFIGURATION_KIND}.")
        if not isinstance(self.voice, ResolvedTtsVoice):
            raise TypeError("voice must be a ResolvedTtsVoice.")
        if self.pacing is not None and not isinstance(self.pacing, SpeechPacing):
            raise TypeError("pacing must be a SpeechPacing or None.")
        if not isinstance(self.display_name, str) or not self.display_name.strip():
            raise ValueError("display_name must be text.")
        object.__setattr__(self, "display_name", self.display_name.strip())


def load_tts_voice_configuration(document: Mapping[str, object]) -> TtsVoiceConfiguration:
    """Parse one neutral voice document without consulting its filename or labels."""
    if not isinstance(document, Mapping):
        raise TypeError("voice configuration must be a mapping.")
    _reject_unknown_fields(document)

    prosody_document = _required_mapping(document, "prosody")
    _reject_unknown_prosody_fields(prosody_document)
    backend_options = document.get("backend_options")
    if not isinstance(backend_options, Mapping):
        raise TypeError("backend_options must be a mapping.")

    voice = ResolvedTtsVoice(
        voice_id=_required_text(document, "voice_id"),
        backend_key=_required_text(document, "backend_key"),
        language=_required_text(document, "language"),
        backend_voice_id=_optional_text(document, "backend_voice_id"),
        prosody=TtsProsody(
            speaking_rate=_required_value(prosody_document, "speaking_rate"),
            volume_gain_db=_required_value(prosody_document, "volume_gain_db"),
            **{
                name: prosody_document[name]
                for name in _OPTIONAL_PROSODY_FIELDS
                if name in prosody_document
            },
        ),
        backend_options=backend_options,
    )
    return TtsVoiceConfiguration(
        kind=_required_text(document, "kind"),
        voice=voice,
        display_name=_required_text(document, "display_name"),
        pacing=_optional_pacing(document),
    )


def _optional_pacing(document: Mapping[str, object]) -> SpeechPacing | None:
    """Parse the optional measured reading rate with Spanish messages."""
    if "pacing" not in document:
        return None
    pacing = document["pacing"]
    if not isinstance(pacing, Mapping):
        raise TtsVoiceConfigurationError(
            "pacing debe ser un objeto con "
            + " y ".join(_PACING_FIELDS)
            + "."
        )
    unknown_fields = sorted(
        str(field_name) for field_name in pacing if field_name not in _PACING_FIELDS
    )
    if unknown_fields:
        raise TtsVoiceConfigurationError(
            "pacing no admite las claves: "
            + ", ".join(unknown_fields)
            + ". Claves válidas: "
            + ", ".join(_PACING_FIELDS)
            + "."
        )
    missing_fields = [name for name in _PACING_FIELDS if name not in pacing]
    if missing_fields:
        raise TtsVoiceConfigurationError(
            "pacing debe declarar " + " y ".join(missing_fields) + "."
        )
    try:
        return SpeechPacing(
            letters_per_second=pacing["letters_per_second"],
            words_per_second=pacing["words_per_second"],
        )
    except (TypeError, ValueError) as error:
        raise TtsVoiceConfigurationError(f"pacing.{error}") from error


def _required_mapping(
    document: Mapping[str, object],
    name: str,
) -> Mapping[str, object]:
    value = document.get(name)
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping.")
    return MappingProxyType(dict(value))


def _required_value(document: Mapping[str, object], name: str) -> object:
    if name not in document:
        raise ValueError(f"{name} is required.")
    return document[name]


def _required_text(document: Mapping[str, object], name: str) -> str:
    value = _required_value(document, name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be text.")
    return value.strip()


def _optional_text(document: Mapping[str, object], name: str) -> str | None:
    value = document.get(name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{name} must be text or null.")
    if not value.strip():
        raise ValueError(f"{name} must not be empty when present.")
    return value.strip()


def _reject_unknown_prosody_fields(prosody: Mapping[str, object]) -> None:
    unknown_fields = sorted(
        str(field_name)
        for field_name in prosody
        if field_name not in _PROSODY_FIELDS
    )
    if unknown_fields:
        raise TtsVoiceConfigurationError(
            "prosody no admite las claves: "
            + ", ".join(unknown_fields)
            + ". Claves válidas: "
            + ", ".join(_PROSODY_FIELDS)
            + "."
        )


def _reject_unknown_fields(document: Mapping[str, object]) -> None:
    unknown_fields = []
    for field_name in document:
        if not isinstance(field_name, str):
            raise TypeError("voice configuration field names must be text.")
        if field_name not in _VOICE_CONFIGURATION_FIELDS:
            unknown_fields.append(field_name)
    if unknown_fields:
        raise ValueError(
            "unknown tts_voice fields: "
            + ", ".join(sorted(unknown_fields))
        )
