from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import re

from app.shared.profile_identity import (
    ProfileComponent,
    ProfileFamily,
    ProfileKey,
    ProfilePlatform,
    coerce_profile_component,
    coerce_profile_platform,
    coerce_profile_family,
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
    platform: ProfilePlatform
    style: SubtitleStyle | str
    profile_id: str
    family: ProfileFamily = ProfileFamily.SYSTEM
    parent_profile_id: str | None = None

    _STYLE_PROFILE_SUFFIXES = {
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
        style = coerce_subtitle_style(
            self.style
        )
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

        if family is ProfileFamily.DESIGN:
            expected_id = self.expected_profile_id(
                component=component,
                platform=platform,
                style=style,
                family=family,
                parent_profile_id=self.parent_profile_id,
            )
            if profile_id != expected_id:
                raise ValueError(
                    "profile_id de subtitulos incompatible: "
                    f"se esperaba {expected_id}, "
                    f"se recibio {self.profile_id}"
                )
        else:
            prefix = f"subtitulo_{component.value}_{platform.value}_"
            if not profile_id.startswith(prefix):
                raise ValueError(
                    "profile_id de subtitulos incompatible con "
                    "component/platform: "
                    f"{self.profile_id}"
                )

        object.__setattr__(self, "component", component)
        object.__setattr__(self, "platform", platform)
        object.__setattr__(self, "style", style)
        object.__setattr__(self, "profile_id", profile_id)
        object.__setattr__(self, "family", family)
        object.__setattr__(self, "parent_profile_id", self.parent_profile_id)

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
                style=style,
                family=profile_key.family,
                parent_profile_id=profile_key.profile_id,
            ),
            family=profile_key.family,
            parent_profile_id=profile_key.profile_id,
        )

    @classmethod
    def expected_profile_id(
        cls,
        component,
        platform,
        style,
        family=ProfileFamily.SYSTEM,
        parent_profile_id=None,
    ):
        component = coerce_profile_component(component)
        platform = coerce_profile_platform(platform)
        style = coerce_subtitle_style(style)
        family = coerce_profile_family(family)
        if family is ProfileFamily.DESIGN:
            parent_key = ProfileKey(
                component=component,
                platform=platform,
                profile_id=parent_profile_id,
                family=family,
            )
            return (
                f"subtitulo_{component.value}_{platform.value}_design_"
                f"{parent_key.profile_id.removeprefix(component.value + '_' + platform.value + '_design_')}_"
                f"{cls._profile_suffix(style)}"
            )
        return (
            f"subtitulo_{component.value}_{platform.value}_"
            f"{cls._profile_suffix(style)}"
        )

    @classmethod
    def is_legacy_standard_profile_id(
        cls,
        component,
        platform,
        style,
        profile_id,
    ):
        return str(profile_id).strip().lower() == cls.expected_profile_id(
            component=component,
            platform=platform,
            style=style,
        )

    @classmethod
    def _profile_suffix(cls, style):
        style = (
            style.value
            if isinstance(style, SubtitleStyle)
            else style
        )
        return cls._STYLE_PROFILE_SUFFIXES.get(
            style,
            style
        )

    @property
    def relative_path(self):
        if self.family is ProfileFamily.DESIGN:
            slug = self.parent_profile_id.removeprefix(
                f"{self.component.value}_{self.platform.value}_design_"
            )
            # A design is a single, self-contained JSON document.  It owns
            # its subtitle settings instead of creating a second hierarchy
            # below ``design/<slug>/``.
            return Path(self.component.value) / self.platform.value / "design" / f"{slug}.json"
        return Path(
            self.component.value
        ) / self.platform.value / "estandar" / (
            f"{self.profile_id}.json"
        )


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

    @property
    def profile_id(self):
        return self.key.profile_id

    @property
    def style(self):
        return self.key.style

    @property
    def component(self):
        return self.key.component

    @property
    def platform(self):
        return self.key.platform
