from dataclasses import dataclass
from enum import Enum
import re


class ProfileComponent(str, Enum):
    GUION = "guion"
    IMAGEN = "imagen"
    VIDEO = "video"
    STUDIO = "studio"


class ProfilePlatform(str, Enum):
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"


class ProfileFamily(str, Enum):
    SYSTEM = "system"
    DESIGN = "design"


_DESIGN_PROFILE_ID = re.compile(
    r"^(guion|imagen|video|studio)_(instagram|youtube)_design_"
    r"[a-z0-9]+(?:_[a-z0-9]+)*$"
)


def coerce_profile_component(value):
    return _coerce_enum(
        ProfileComponent,
        value,
        "Componente"
    )


def coerce_profile_platform(value):
    return _coerce_enum(
        ProfilePlatform,
        value,
        "Plataforma"
    )


def coerce_profile_family(value):
    return _coerce_enum(ProfileFamily, value, "Familia")


def _coerce_enum(
    enum_type,
    value,
    label
):
    if isinstance(value, enum_type):
        return value

    normalized = str(value).strip().lower()
    try:
        return enum_type(normalized)
    except ValueError as error:
        raise ValueError(
            f"{label} de perfil no soportado: {value}"
        ) from error


@dataclass(frozen=True)
class ProfileKey:
    component: ProfileComponent
    platform: ProfilePlatform
    profile_id: str
    family: ProfileFamily = ProfileFamily.SYSTEM

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
        expected_id = f"{component.value}_{platform.value}"
        if family is ProfileFamily.SYSTEM:
            valid = profile_id == expected_id
        else:
            valid = bool(_DESIGN_PROFILE_ID.fullmatch(profile_id)) and (
                profile_id.startswith(
                    f"{component.value}_{platform.value}_design_"
                )
            )
        if not valid:
            raise ValueError(
                "profile_id incompatible con componente y "
                f"plataforma/familia: se esperaba {expected_id} "
                "para SYSTEM o un ID DESIGN canónico, "
                f"se recibió {self.profile_id}"
            )

        object.__setattr__(
            self,
            "component",
            component
        )
        object.__setattr__(
            self,
            "platform",
            platform
        )
        object.__setattr__(
            self,
            "profile_id",
            profile_id
        )
        object.__setattr__(self, "family", family)

    @classmethod
    def for_component(
        cls,
        component,
        platform,
        family=ProfileFamily.SYSTEM,
        profile_id=None,
    ):
        component = coerce_profile_component(
            component
        )
        platform = coerce_profile_platform(
            platform
        )
        family = coerce_profile_family(family)
        if family is ProfileFamily.DESIGN and not profile_id:
            raise ValueError(
                "Un perfil DESIGN requiere un profile_id concreto."
            )
        return cls(
            component=component,
            platform=platform,
            profile_id=(profile_id or f"{component.value}_{platform.value}"),
            family=family,
        )
