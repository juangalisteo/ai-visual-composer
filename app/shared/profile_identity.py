from dataclasses import dataclass
from enum import Enum
import re


class ProfileComponent(str, Enum):
    GUION = "guion"
    IMAGEN = "imagen"
    VIDEO = "video"
    STUDIO = "studio"


def coerce_profile_component(value):
    return _coerce_enum(
        ProfileComponent,
        value,
        "Componente"
    )


def coerce_profile_platform(value):
    if not isinstance(value, str):
        raise ValueError(
            f"Plataforma de perfil no soportado: {value}"
        )
    normalized = value.strip().lower()
    if not re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", normalized):
        raise ValueError(
            f"Plataforma de perfil no soportado: {value}"
        )
    return normalized


def coerce_profile_family(value):
    if not isinstance(value, str):
        raise ValueError(
            f"Familia de perfil no soportada: {value}"
        )
    normalized = value.strip().lower()
    if normalized == "system" or not re.fullmatch(
        r"[a-z0-9]+(?:_[a-z0-9]+)*", normalized
    ):
        raise ValueError(f"Familia de perfil no soportada: {value}")
    return normalized


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
        if not isinstance(self.profile_id, str):
            raise ValueError(
                "profile_id invalido: debe ser texto."
            )
        profile_id = str(
            self.profile_id
        ).strip().lower()
        if not re.fullmatch(
            r"[a-z0-9]+(?:_[a-z0-9]+)*",
            profile_id,
        ):
            raise ValueError(
                "profile_id invalido: se requiere un identificador tecnico "
                f"seguro, se recibio {self.profile_id}"
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
        family=None,
        profile_id=None,
    ):
        component = coerce_profile_component(
            component
        )
        platform = coerce_profile_platform(
            platform
        )
        legacy_family_missing = family is None
        # LEGACY_ADAPTER: this creates only a subtitle-parent identity for
        # callers that still use the former subtitle-selection input. It is
        # not an operational-profile factory: modern operational code uses
        # OperationalProfileKey explicitly.
        family = coerce_profile_family("estandar" if family is None else family)
        if not legacy_family_missing and profile_id is None:
            raise ValueError(
                "Una family explicita requiere un profile_id concreto."
            )
        return cls(
            component=component,
            platform=platform,
            profile_id=(profile_id or f"{component.value}_{platform}"),
            family=family,
        )


@dataclass(frozen=True)
class OperationalProfileKey:
    """Canonical identity for a general operational profile.

    Subtitle family is deliberately absent: it belongs exclusively to the
    subtitle-profile domain. ``ProfileKey`` remains only an isolated legacy
    subtitle-selection compatibility identity.
    """

    component: ProfileComponent
    platform: str
    profile_id: str

    def __post_init__(self):
        component = coerce_profile_component(self.component)
        platform = coerce_profile_platform(self.platform)
        if not isinstance(self.profile_id, str):
            raise ValueError("profile_id invalido: debe ser texto.")
        profile_id = self.profile_id.strip().lower()
        if not re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", profile_id):
            raise ValueError(
                "profile_id invalido: se requiere un identificador tecnico "
                f"seguro, se recibio {self.profile_id}"
            )
        object.__setattr__(self, "component", component)
        object.__setattr__(self, "platform", platform)
        object.__setattr__(self, "profile_id", profile_id)
