from dataclasses import dataclass
from enum import Enum


class ProfileComponent(str, Enum):
    GUION = "guion"
    IMAGEN = "imagen"
    VIDEO = "video"
    STUDIO = "studio"


class ProfilePlatform(str, Enum):
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"


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

    def __post_init__(self):
        component = coerce_profile_component(
            self.component
        )
        platform = coerce_profile_platform(
            self.platform
        )
        profile_id = str(
            self.profile_id
        ).strip().lower()
        expected_id = (
            f"{component.value}_{platform.value}"
        )

        if profile_id != expected_id:
            raise ValueError(
                "profile_id incompatible con componente y "
                f"plataforma: se esperaba {expected_id}, "
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

    @classmethod
    def for_component(
        cls,
        component,
        platform
    ):
        component = coerce_profile_component(
            component
        )
        platform = coerce_profile_platform(
            platform
        )
        return cls(
            component=component,
            platform=platform,
            profile_id=(
                f"{component.value}_{platform.value}"
            )
        )
