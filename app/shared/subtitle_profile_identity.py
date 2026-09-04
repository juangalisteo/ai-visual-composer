from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from app.shared.profile_identity import (
    ProfileComponent,
    ProfileKey,
    ProfilePlatform,
    coerce_profile_component,
    coerce_profile_platform,
)


class SubtitleStyle(str, Enum):
    SINGLE_LINE = "single_line"
    WORD_BY_WORD = "word_by_word"


def coerce_subtitle_style(value):
    if isinstance(value, SubtitleStyle):
        return value

    normalized = str(value).strip().lower()
    try:
        return SubtitleStyle(normalized)
    except ValueError as error:
        raise ValueError(
            f"Estilo de subtitulos no soportado: {value}"
        ) from error


@dataclass(frozen=True)
class SubtitleProfileKey:
    component: ProfileComponent
    platform: ProfilePlatform
    style: SubtitleStyle
    profile_id: str

    _STYLE_SUFFIXES = {
        SubtitleStyle.SINGLE_LINE: "linea_unica",
        SubtitleStyle.WORD_BY_WORD: "palabra_por_palabra",
    }

    def __post_init__(self):
        component = coerce_profile_component(
            self.component
        )
        platform = coerce_profile_platform(
            self.platform
        )
        style = coerce_subtitle_style(
            self.style
        )
        profile_id = str(
            self.profile_id
        ).strip().lower()
        expected_id = self.expected_profile_id(
            component=component,
            platform=platform,
            style=style
        )

        if profile_id != expected_id:
            raise ValueError(
                "profile_id de subtitulos incompatible: "
                f"se esperaba {expected_id}, "
                f"se recibio {self.profile_id}"
            )

        object.__setattr__(self, "component", component)
        object.__setattr__(self, "platform", platform)
        object.__setattr__(self, "style", style)
        object.__setattr__(self, "profile_id", profile_id)

    @classmethod
    def for_profile(
        cls,
        profile_key,
        style
    ):
        if not isinstance(profile_key, ProfileKey):
            raise TypeError(
                "La identidad principal debe ser un ProfileKey."
            )
        style = coerce_subtitle_style(style)
        return cls(
            component=profile_key.component,
            platform=profile_key.platform,
            style=style,
            profile_id=cls.expected_profile_id(
                component=profile_key.component,
                platform=profile_key.platform,
                style=style
            )
        )

    @classmethod
    def expected_profile_id(
        cls,
        component,
        platform,
        style
    ):
        component = coerce_profile_component(component)
        platform = coerce_profile_platform(platform)
        style = coerce_subtitle_style(style)
        return (
            f"subtitulo_{component.value}_{platform.value}_"
            f"{cls._STYLE_SUFFIXES[style]}"
        )

    @property
    def relative_path(self):
        return Path(
            self.component.value
        ) / self.platform.value / "subtitulos" / (
            f"{self.profile_id}.json"
        )


@dataclass(frozen=True)
class ResolvedSubtitleProfile:
    key: SubtitleProfileKey
    path: Path
    cue_policy: dict
    render_style: dict
