"""Neutral declarative voice-configuration parsing.

This module validates data already loaded from JSON. It neither selects a
backend nor performs synthesis.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from app.modules.audio.tts_contracts import ResolvedTtsVoice, TtsProsody


_VOICE_CONFIGURATION_KIND = "tts_voice"
_VOICE_CONFIGURATION_FIELDS = frozenset(
    {
        "kind",
        "voice_id",
        "display_name",
        "backend_key",
        "backend_voice_id",
        "language",
        "prosody",
        "backend_options",
    }
)


@dataclass(frozen=True)
class TtsVoiceConfiguration:
    """One declarative, presentation-separated technical voice document."""

    voice: ResolvedTtsVoice
    display_name: str
    kind: str = _VOICE_CONFIGURATION_KIND

    def __post_init__(self):
        if self.kind != _VOICE_CONFIGURATION_KIND:
            raise ValueError(f"kind must be {_VOICE_CONFIGURATION_KIND}.")
        if not isinstance(self.voice, ResolvedTtsVoice):
            raise TypeError("voice must be a ResolvedTtsVoice.")
        if not isinstance(self.display_name, str) or not self.display_name.strip():
            raise ValueError("display_name must be text.")
        object.__setattr__(self, "display_name", self.display_name.strip())


def load_tts_voice_configuration(document: Mapping[str, object]) -> TtsVoiceConfiguration:
    """Parse one neutral voice document without consulting its filename or labels."""
    if not isinstance(document, Mapping):
        raise TypeError("voice configuration must be a mapping.")
    _reject_unknown_fields(document)

    prosody_document = _required_mapping(document, "prosody")
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
        ),
        backend_options=backend_options,
    )
    return TtsVoiceConfiguration(
        kind=_required_text(document, "kind"),
        voice=voice,
        display_name=_required_text(document, "display_name"),
    )


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
