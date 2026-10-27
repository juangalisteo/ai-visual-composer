from dataclasses import dataclass
from pathlib import Path
import re

from app.shared.profile_identity import (
    ProfileComponent,
    coerce_profile_component,
    coerce_profile_format,
    coerce_profile_family,
)


@dataclass(frozen=True)
class SubtitleProfileKey:
    component: ProfileComponent
    format: str
    profile_id: str
    family: str

    def __post_init__(self):
        component = coerce_profile_component(
            self.component
        )
        profile_format = coerce_profile_format(
            self.format
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
                "profile_id de subtítulos inválido: "
                f"{self.profile_id}"
            )

        object.__setattr__(self, "component", component)
        object.__setattr__(self, "format", profile_format)
        object.__setattr__(self, "profile_id", profile_id)
        object.__setattr__(self, "family", family)

    @property
    def relative_path(self):
        return Path(self.component.value) / self.format / self.family / "subtitulos" / f"{self.profile_id}.json"


def require_subtitle_profile_key(subtitle_profile_key):
    """Validate and return the full subtitle identity."""
    if subtitle_profile_key is None:
        raise ValueError("La ruta de subtítulos requiere una SubtitleProfileKey.")
    if not isinstance(subtitle_profile_key, SubtitleProfileKey):
        raise TypeError(
            "La ruta moderna requiere una SubtitleProfileKey completa."
        )
    return subtitle_profile_key


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
    def format(self):
        return self.key.format
