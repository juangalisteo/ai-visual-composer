import json
from dataclasses import dataclass
from pathlib import Path

from app.shared.profile_identity import (
    OperationalProfileKey,
    ProfileComponent,
    coerce_profile_platform,
)
from app.shared.operational_error import create_operational_error


@dataclass(frozen=True)
class OperationalProfileDescriptor:
    """An operational document discovered at its component/platform root."""

    key: OperationalProfileKey
    path: Path
    display_name: str


class ProfileResolver:
    _VIDEO_COMPONENT_PATHS = {
        "instagram": Path(
            "video/instagram/wan_i2v_instagram.json"
        ),
        "youtube": Path(
            "video/youtube/wan_i2v_youtube.json"
        ),
    }

    def __init__(
        self,
        profiles_root=Path("config/profiles")
    ):
        self.profiles_root = Path(
            profiles_root
        )

    def discover_operational_profiles(self, component, platform):
        """Discover operational documents by canonical identity.

        Operational documents exist only at component/platform root. Subtitle
        families are resolved by ``SubtitleProfileResolver`` independently.
        """
        component = ProfileComponent(component)
        platform = coerce_profile_platform(platform)
        descriptors = self._operational_candidates(component, platform)
        self._raise_if_duplicate_operational_ids(descriptors)
        return tuple(sorted(
            descriptors,
            key=lambda descriptor: (
                descriptor.display_name.casefold(),
                descriptor.key.profile_id,
            ),
        ))

    def resolve_operational(self, profile_key):
        """Resolve one operational document from its canonical identity."""
        profile_key = self._require_operational_key(profile_key)
        matches = [
            descriptor
            for descriptor in self._operational_candidates(
                profile_key.component,
                profile_key.platform,
            )
            if descriptor.key.profile_id == profile_key.profile_id
        ]
        if not matches:
            error = FileNotFoundError(
                f"No existe un perfil operacional: {profile_key.profile_id}"
            )
            raise create_operational_error(
                family="PROFILE",
                user_message="No se encontro el perfil operacional solicitado.",
                recommended_action=(
                    "Revise la identidad seleccionada y la configuracion de "
                    "perfiles."
                ),
                operation="Resolver perfil operacional",
                resource=self._operational_resource(profile_key),
            ) from error
        if len(matches) > 1:
            self._raise_ambiguous_operational_ids(matches)
        return matches[0].path

    def load_operational(self, profile_key):
        """Load a general operational document by canonical identity."""
        return self._load_profile_json(self.resolve_operational(profile_key))

    def _operational_candidates(self, component, platform):
        return self._discover_root_operational_profiles(component, platform)

    def _discover_root_operational_profiles(self, component, platform):
        directory = self.profiles_root / component.value / platform
        self._ensure_within_profiles_root(directory)
        if not directory.is_dir():
            return ()
        discovered = []
        for path in sorted(directory.glob("*.json"), key=lambda item: item.name.casefold()):
            self._ensure_within_profiles_root(path)
            data = self._load_profile_json(path)
            if not self._is_operational_document(data):
                continue
            key = OperationalProfileKey(
                component,
                platform,
                data.get("profile_id", ""),
            )
            self._validate_operational_identity(data, key, path)
            discovered.append(OperationalProfileDescriptor(
                key=key,
                path=path,
                display_name=self._display_name(data, key),
            ))
        return tuple(discovered)

    @staticmethod
    def _is_operational_document(data):
        """Recognize operational documents structurally, never by file name."""
        return "component" in data or "profile_id" in data

    def _validate_operational_identity(self, data, key, path):
        expected = {
            "component": key.component.value,
            "platform": key.platform,
            "profile_id": key.profile_id,
        }
        if not isinstance(data, dict) or any(
            data.get(field) != value
            for field, value in expected.items()
        ):
            error = ValueError(f"Identidad operacional invalida: {path}")
            raise create_operational_error(
                family="PROFILE",
                user_message=(
                    "La identidad interna del perfil operacional no coincide "
                    "con su ruta."
                ),
                recommended_action=(
                    "Revise component, platform y profile_id del perfil."
                ),
                operation="Validar perfil operacional",
                resource=str(path),
                technical_metadata={
                    "requested_profile": self._operational_resource(key),
                },
            ) from error

    @staticmethod
    def _display_name(data, key):
        display_name = data.get("display_name")
        if isinstance(display_name, str) and display_name.strip():
            return display_name.strip()
        return key.profile_id

    def _raise_if_duplicate_operational_ids(self, descriptors):
        seen = {}
        for descriptor in descriptors:
            profile_id = descriptor.key.profile_id
            if profile_id in seen:
                self._raise_ambiguous_operational_ids(
                    (seen[profile_id], descriptor),
                )
            seen[profile_id] = descriptor

    def _raise_ambiguous_operational_ids(self, descriptors):
        profile_id = descriptors[0].key.profile_id
        error = ValueError(f"profile_id operacional duplicado: {profile_id}")
        raise create_operational_error(
            family="AMBIGUITY",
            user_message=(
                "La identidad operacional coincide con varios perfiles."
            ),
            recommended_action=(
                "Elimine o corrija los perfiles duplicados antes de continuar."
            ),
            operation="Resolver perfil operacional",
            resource=self._operational_resource(descriptors[0].key),
            technical_metadata={
                "candidates": [str(descriptor.path) for descriptor in descriptors],
            },
        ) from error

    def discover_platforms(self, component):
        component = ProfileComponent(component)
        directory = self.profiles_root / component.value
        self._ensure_within_profiles_root(directory)
        if not directory.is_dir():
            return ()
        platforms = []
        for path in directory.iterdir():
            if not path.is_dir():
                continue
            try:
                platform = coerce_profile_platform(path.name)
            except ValueError:
                continue
            self._ensure_within_profiles_root(path)
            platforms.append(platform)
        return tuple(sorted(platforms))

    def _load_profile_json(self, path):
        path = Path(path)
        try:
            with path.open("r", encoding="utf-8") as file:
                profile = json.load(file)
        except FileNotFoundError as error:
            raise create_operational_error(
                family="FILESYSTEM",
                user_message="No se encontró el archivo del perfil operacional.",
                recommended_action="Revise que el archivo de perfil exista.",
                operation="Leer perfil operacional",
                resource=str(path),
            ) from error
        except json.JSONDecodeError as error:
            raise create_operational_error(
                family="CONFIG",
                user_message="El perfil operacional no contiene JSON válido.",
                recommended_action="Corrija el JSON del perfil indicado.",
                operation="Leer perfil operacional",
                resource=str(path),
                technical_metadata={"line": error.lineno, "column": error.colno},
            ) from error
        except OSError as error:
            raise create_operational_error(
                family="FILESYSTEM",
                user_message="No se pudo leer el archivo del perfil operacional.",
                recommended_action="Revise la ruta y permisos del perfil.",
                operation="Leer perfil operacional",
                resource=str(path),
            ) from error
        if not isinstance(profile, dict):
            error = TypeError("El perfil debe ser un objeto JSON.")
            raise create_operational_error(
                family="CONFIG",
                user_message="El perfil operacional debe ser un objeto JSON.",
                recommended_action="Corrija la estructura JSON del perfil.",
                operation="Leer perfil operacional",
                resource=str(path),
            ) from error
        return profile

    def resolve_video_component(
        self,
        profile_key
    ):
        profile_key = self._require_operational_key(
            profile_key
        )
        if profile_key.component is not ProfileComponent.VIDEO:
            raise ValueError(
                "La configuración técnica Wan solo pertenece "
                "al componente video."
            )
        relative_path = self._VIDEO_COMPONENT_PATHS.get(profile_key.platform)
        if relative_path is None:
            raise FileNotFoundError(
                "No existe configuración Wan para la plataforma: "
                f"{profile_key.platform}"
            )
        return self._existing_path(relative_path)

    def load_video_component(
        self,
        profile_key
    ):
        return self._load_json(
            self.resolve_video_component(
                profile_key
            )
        )

    def _existing_path(
        self,
        relative_path
    ):
        root = self.profiles_root.resolve()
        candidate = (
            self.profiles_root
            / relative_path
        ).resolve()

        if candidate != root and root not in candidate.parents:
            raise ValueError(
                "La ruta de perfil queda fuera de "
                "config/profiles."
            )
        if not candidate.is_file():
            raise FileNotFoundError(
                f"No existe el perfil esperado: {candidate}"
            )

        return self.profiles_root / relative_path

    def _ensure_within_profiles_root(self, path):
        root = self.profiles_root.resolve()
        candidate = Path(path).resolve()
        if candidate != root and root not in candidate.parents:
            raise ValueError(
                "La ruta de perfil queda fuera de config/profiles."
            )
        return candidate

    def _load_json(
        self,
        path
    ):
        with Path(path).open(
            "r",
            encoding="utf-8"
        ) as file:
            profile = json.load(file)

        if not isinstance(profile, dict):
            raise TypeError(
                "El perfil debe ser un objeto JSON."
            )
        return profile

    @staticmethod
    def _require_operational_key(profile_key):
        if isinstance(profile_key, OperationalProfileKey):
            return profile_key
        raise TypeError(
            "La resolucion operacional canonica requiere una "
            "OperationalProfileKey."
        )

    @staticmethod
    def _operational_resource(profile_key):
        return "/".join(
            (
                profile_key.component.value,
                profile_key.platform,
                profile_key.profile_id,
            )
        )
