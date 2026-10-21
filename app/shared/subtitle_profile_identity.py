from dataclasses import dataclass
from pathlib import Path
import re

from app.shared.profile_identity import (
    ProfileComponent,
    coerce_profile_component,
    coerce_profile_platform,
    coerce_profile_family,
)


@dataclass(frozen=True)
class SubtitleProfileKey:
    component: ProfileComponent
    platform: str
    profile_id: str
    family: str

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
