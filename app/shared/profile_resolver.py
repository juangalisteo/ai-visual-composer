import json
from pathlib import Path

from app.shared.profile_identity import (
    ProfileComponent,
    ProfileKey,
    coerce_profile_family,
    coerce_profile_platform,
)
from app.shared.operational_error import create_operational_error


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

    def resolve(
        self,
        profile_key
    ):
        profile_key = self._require_operational_profile_key(
            profile_key
        )
        return self._generic_profile_path(profile_key)

    def discover(self, component, platform, family):
        component = ProfileComponent(component)
        platform = coerce_profile_platform(platform)
        family = coerce_profile_family(family)
        directory = self.profiles_root / component.value / platform / family
        self._ensure_within_profiles_root(directory)
        if not directory.is_dir():
            return ()
        return self._discover_dynamic_family(component, platform, family, directory)

    def discover_families(self, component, platform):
        component = ProfileComponent(component)
        platform = coerce_profile_platform(platform)
        families = []
        root = self.profiles_root / component.value / platform
        if not root.is_dir():
            return tuple(families)
        for directory in sorted(root.iterdir(), key=lambda item: item.name.casefold()):
            if not directory.is_dir():
                continue
            try:
                family = coerce_profile_family(directory.name)
            except (ValueError, TypeError):
                continue
            if self.discover(component, platform, family):
                families.append(family)
        return tuple(families)

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

    def _generic_profile_path(self, profile_key):
        directory = self.profiles_root / profile_key.component.value / profile_key.platform / profile_key.family
        self._ensure_within_profiles_root(directory)
        matches = []
        for path in directory.glob("*.json"):
            self._ensure_within_profiles_root(path)
            data = self._load_profile_json(path)
            if data.get("profile_id") == profile_key.profile_id:
                self._validate_profile_identity(data, profile_key, path)
                matches.append(path)
        if not matches:
            error = FileNotFoundError(
                f"No existe un perfil unico: {profile_key.profile_id}"
            )
            raise create_operational_error(
                family="PROFILE",
                user_message="No se encontró el perfil operacional solicitado.",
                recommended_action=(
                    "Revise la identidad seleccionada y la configuración de "
                    "perfiles."
                ),
                operation="Resolver perfil operacional",
                resource=self._profile_resource(profile_key),
            ) from error
        if len(matches) > 1:
            error = ValueError(f"profile_id duplicado: {profile_key.profile_id}")
            raise create_operational_error(
                family="AMBIGUITY",
                user_message="La identidad operacional coincide con varios perfiles.",
                recommended_action=(
                    "Elimine o corrija los perfiles duplicados antes de "
                    "continuar."
                ),
                operation="Resolver perfil operacional",
                resource=self._profile_resource(profile_key),
                technical_metadata={
                    "candidates": [str(path) for path in matches],
                },
            ) from error
        return matches[0]

    def _discover_dynamic_family(self, component, platform, family, directory):
        discovered = []
        profile_ids = set()
        for path in sorted(directory.glob("*.json"), key=lambda item: item.name.casefold()):
            self._ensure_within_profiles_root(path)
            data = self._load_profile_json(path)
            profile_id = data.get("profile_id", "")
            key = ProfileKey(component, platform, data.get("profile_id", ""), family)
            self._validate_profile_identity(data, key, path)
            display_name = data.get("display_name")
            if not isinstance(display_name, str) or not display_name.strip():
                display_name = key.profile_id
            if key.profile_id in profile_ids:
                error = ValueError(f"profile_id duplicado: {key.profile_id}")
                raise create_operational_error(
                    family="AMBIGUITY",
                    user_message=(
                        "La familia contiene perfiles operacionales con la "
                        "misma identidad."
                    ),
                    recommended_action=(
                        "Elimine o corrija los perfiles duplicados antes de "
                        "continuar."
                    ),
                    operation="Descubrir perfiles operacionales",
                    resource=self._profile_resource(key),
                    technical_metadata={"candidate": str(path)},
                ) from error
            profile_ids.add(key.profile_id)
            discovered.append((key, display_name.strip()))
        return tuple(sorted(discovered, key=lambda item: (item[1].casefold(), item[0].profile_id)))

    def _validate_profile_identity(self, data, key, path):
        expected = {
            "component": key.component.value,
            "platform": key.platform,
            "family": key.family,
            "profile_id": key.profile_id,
        }
        if not isinstance(data, dict) or any(
            data.get(field) != value
            for field, value in expected.items()
        ):
            error = ValueError(f"Identidad de perfil invalida: {path}")
            raise create_operational_error(
                family="PROFILE",
                user_message="La identidad interna del perfil no coincide con su ruta.",
                recommended_action=(
                    "Revise component, platform, family y profile_id del "
                    "perfil."
                ),
                operation="Validar perfil operacional",
                resource=str(path),
                technical_metadata={"requested_profile": self._profile_resource(key)},
            ) from error
    def load(
        self,
        profile_key
    ):
        return self._load_profile_json(
            self.resolve(profile_key)
        )

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
        profile_key = self._require_profile_key(
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

    def _require_profile_key(
        self,
        profile_key
    ):
        if not isinstance(
            profile_key,
            ProfileKey
        ):
            raise TypeError(
                "ProfileResolver requiere un ProfileKey."
            )
        return profile_key

    def _require_operational_profile_key(self, profile_key):
        try:
            return self._require_profile_key(profile_key)
        except TypeError as error:
            raise create_operational_error(
                family="VALIDATION",
                user_message="La identidad operacional no tiene el contrato requerido.",
                recommended_action="Use una ProfileKey completa y válida.",
                operation="Resolver perfil operacional",
            ) from error

    @staticmethod
    def _profile_resource(profile_key):
        return "/".join(
            (
                profile_key.component.value,
                profile_key.platform,
                profile_key.family,
                profile_key.profile_id,
            )
        )
