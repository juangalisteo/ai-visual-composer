from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import re

from app.shared.profile_identity import (
    ProfileComponent,
    ProfileKey,
    coerce_profile_component,
    coerce_profile_platform,
    coerce_profile_family,
)


class SubtitleStyle(str, Enum):
    """Legacy selection values; modern profiles declare cue_policy.mode."""

    SINGLE_LINE = "single_line"
    WORD_BY_WORD = "word_by_word"


def coerce_subtitle_style(value):
    if isinstance(value, SubtitleStyle):
        return value

    normalized = str(value).strip().lower()
    try:
        return SubtitleStyle(normalized)
    except ValueError:
        pass
    if not re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", normalized):
        raise ValueError(
            f"Estilo de subtitulos no soportado: {value}"
        )
    return normalized


@dataclass(frozen=True)
class SubtitleProfileKey:
    component: ProfileComponent
    platform: str
    profile_id: str
    family: str
    parent_profile_id: str | None = None

    _LEGACY_PROFILE_SUFFIXES = {
        "single_line": "linea_unica",
        "word_by_word": "palabra_por_palabra",
    }

    def __post_init__(self):
        component = coerce_profile_component(
            self.component
        )
        platform = coerce_profile_platform(
            self.platform
        )
        family = coerce_profile_family(self.family)
        profile_id = str(
            self.profile_id
        ).strip().lower()
        if not re.fullmatch(
            r"[a-z0-9]+(?:_[a-z0-9]+)*",
            profile_id,
        ):
            raise ValueError(
                "profile_id de subtitulos invalido: "
                f"{self.profile_id}"
            )

        object.__setattr__(self, "component", component)
        object.__setattr__(self, "platform", platform)
        object.__setattr__(self, "profile_id", profile_id)
        object.__setattr__(self, "family", family)
        object.__setattr__(self, "parent_profile_id", self.parent_profile_id)

    @classmethod
    def for_profile(
        cls,
        profile_key,
        style,
        profile_id=None,
    ):
        if not isinstance(profile_key, ProfileKey):
            raise TypeError(
                "La identidad principal debe ser un ProfileKey."
        )
        style = coerce_subtitle_style(style)
        if profile_id is None:
            profile_id = cls._legacy_profile_id(
                profile_key.component,
                profile_key.platform,
                style,
            )
        return cls(
            component=profile_key.component,
            platform=profile_key.platform,
            profile_id=profile_id,
            family=profile_key.family,
            parent_profile_id=profile_key.profile_id,
        )

    @classmethod
    def _legacy_profile_id(cls, component, platform, style):
        """Adapt callers that omit a concrete subtitle profile ID."""
        component = coerce_profile_component(component)
        platform = coerce_profile_platform(platform)
        style = coerce_subtitle_style(style)
        style_value = style.value if isinstance(style, SubtitleStyle) else style
        suffix = cls._LEGACY_PROFILE_SUFFIXES.get(style_value, style_value)
        return f"subtitulo_{component.value}_{platform}_{suffix}"

    @property
    def relative_path(self):
        return Path(self.component.value) / self.platform / self.family / "subtitulos" / f"{self.profile_id}.json"


@dataclass(frozen=True)
class ResolvedSubtitleProfile:
    key: SubtitleProfileKey
    path: Path
    display_name: str
    cue_policy: dict
    render_style: dict


@dataclass(frozen=True)
class SubtitleProfileDescriptor:
    key: SubtitleProfileKey
    display_name: str
    mode: str

    @property
    def profile_id(self):
        return self.key.profile_id

    @property
    def component(self):
        return self.key.component

    @property
    def platform(self):
        return self.key.platform
