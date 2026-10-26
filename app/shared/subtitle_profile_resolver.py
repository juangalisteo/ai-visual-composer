import json
from copy import deepcopy
from pathlib import Path

from app.modules.subtitles.modes.registry import CueModelRegistry
from app.modules.subtitles.nlp.syllabifier import SyllabifierPolicy
from app.modules.subtitles.policies.text_case import TextCasePolicy
from app.modules.video.config.loaders.subtitle_loader import SubtitleConfigLoader
from app.shared.profile_identity import (
    ProfileComponent,
    coerce_profile_family,
    coerce_profile_format,
)
from app.shared.operational_error import create_operational_error
from app.shared.subtitle_profile_identity import (
    ResolvedSubtitleProfile,
    SubtitleProfileDescriptor,
    SubtitleProfileKey,
)


class SubtitleProfileResolver:
    """Resolve autonomous subtitle profiles from their physical hierarchy."""

    def __init__(self, profiles_root=Path("config/profiles")):
        self.profiles_root = Path(profiles_root)

    def resolve(self, profile_key):
        profile_key = self._require_operational_key(profile_key)
        matches = []
        for path, data in self._profile_documents(
            profile_key.component, profile_key.format, profile_key.family
        ):
            if data.get("profile_id") == profile_key.profile_id:
                self._validate_identity(data, profile_key, path)
                matches.append(path)
        if not matches:
            error = FileNotFoundError(
                "No existe el perfil de subtitulos: "
                f"{profile_key.profile_id}"
            )
            raise create_operational_error(
                family="PROFILE",
                user_message="No se encontró el perfil de subtítulos solicitado.",
                recommended_action=(
                    "Revise la identidad seleccionada y la configuración de "
                    "perfiles de subtítulos."
                ),
                operation="Resolver perfil de subtítulos",
                resource=self._profile_resource(profile_key),
            ) from error
        if len(matches) > 1:
            error = ValueError(
                "profile_id de subtitulos duplicado: "
                f"{profile_key.profile_id}"
            )
            raise create_operational_error(
                family="AMBIGUITY",
                user_message=(
                    "La identidad de subtítulos coincide con varios perfiles."
                ),
                recommended_action=(
                    "Elimine o corrija los perfiles duplicados antes de "
                    "continuar."
                ),
                operation="Resolver perfil de subtítulos",
                resource=self._profile_resource(profile_key),
                technical_metadata={
                    "candidates": [str(path) for path in matches],
                },
            ) from error
        return matches[0]

    def load(self, profile_key):
        profile_key = self._require_operational_key(profile_key)
        path = self.resolve(profile_key)
        data = self._load_json(path)
        self._validate_identity(data, profile_key, path)
        self._validate_profile_contract(data, path)
        return ResolvedSubtitleProfile(
            key=profile_key,
            path=path,
            display_name=self._display_name(data, path),
            cue_policy=deepcopy(data["cue_policy"]),
            render_style=deepcopy(data["render_style"]),
        )

    def discover_formats(self, component):
        component = ProfileComponent(component)
        root = self.profiles_root / component.value
        self._ensure_within_profiles_root(root)
        if not root.is_dir():
            return ()
        profile_formats = []
        for directory in root.iterdir():
            if not directory.is_dir():
                continue
            try:
                profile_format = coerce_profile_format(directory.name)
            except ValueError:
                continue
            if self.discover_families(component, profile_format):
                profile_formats.append(profile_format)
        return tuple(sorted(profile_formats))

    def discover_families(self, component, profile_format):
        component = ProfileComponent(component)
        profile_format = coerce_profile_format(profile_format)
        root = self.profiles_root / component.value / profile_format
        self._ensure_within_profiles_root(root)
        if not root.is_dir():
            return ()
        families = []
        for directory in sorted(root.iterdir(), key=lambda item: item.name.casefold()):
            if not directory.is_dir():
                continue
            try:
                family = coerce_profile_family(directory.name)
            except (TypeError, ValueError):
                continue
            if self.discover_profiles_for_family(component, profile_format, family):
                families.append(family)
        return tuple(families)

    def discover_profiles_for_family(self, component, profile_format, family):
        component = ProfileComponent(component)
        profile_format = coerce_profile_format(profile_format)
        family = coerce_profile_family(family)
        discovered = []
        profile_ids = set()
        for path, data in self._profile_documents(component, profile_format, family):
            key = SubtitleProfileKey(
                component=component,
                format=profile_format,
                family=family,
                profile_id=data.get("profile_id", ""),
            )
            self._validate_identity(data, key, path)
            self._validate_profile_contract(data, path)
            if path != self.resolve(key):
                error = ValueError(
                    "La ruta del perfil de subtitulos no coincide "
                    f"con su identidad: {path}."
                )
                raise create_operational_error(
                    family="PROFILE",
                    user_message=(
                        "La ruta del perfil de subtítulos no coincide con su "
                        "identidad."
                    ),
                    recommended_action=(
                        "Revise la estructura y la identidad interna del "
                        "perfil."
                    ),
                    operation="Descubrir perfiles de subtítulos",
                    resource=str(path),
                ) from error
            if key.profile_id in profile_ids:
                error = ValueError(
                    "profile_id de subtitulos duplicado: "
                    f"{key.profile_id}"
                )
                raise create_operational_error(
                    family="AMBIGUITY",
                    user_message=(
                        "La familia contiene perfiles de subtítulos con la "
                        "misma identidad."
                    ),
                    recommended_action=(
                        "Elimine o corrija los perfiles duplicados antes de "
                        "continuar."
                    ),
                    operation="Descubrir perfiles de subtítulos",
                    resource=self._profile_resource(key),
                    technical_metadata={"candidate": str(path)},
                ) from error
            profile_ids.add(key.profile_id)
            discovered.append(
                SubtitleProfileDescriptor(
                    key=key,
                    display_name=self._display_name(data, path),
                    mode=CueModelRegistry.mode_from(data["cue_policy"]),
                )
            )
        return tuple(sorted(
            discovered,
            key=lambda descriptor: (
                descriptor.display_name.casefold(), descriptor.profile_id,
            ),
        ))

    def _profile_documents(self, component, profile_format, family):
        directory = (
            self.profiles_root / component.value / profile_format / family / "subtitulos"
        )
        self._ensure_within_profiles_root(directory)
        if not directory.is_dir():
            return ()
        documents = []
        for path in sorted(directory.glob("*.json"), key=lambda item: item.name.casefold()):
            self._ensure_within_profiles_root(path)
            documents.append((path, self._load_json(path)))
        return tuple(documents)

    def _load_json(self, path):
        path = Path(path)
        try:
            with path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except FileNotFoundError as error:
            raise create_operational_error(
                family="FILESYSTEM",
                user_message="No se encontró el archivo del perfil de subtítulos.",
                recommended_action="Revise que el archivo de perfil exista.",
                operation="Leer perfil de subtítulos",
                resource=str(path),
            ) from error
        except json.JSONDecodeError as error:
            raise create_operational_error(
                family="CONFIG",
                user_message="El perfil de subtítulos no contiene JSON válido.",
                recommended_action="Corrija el JSON del perfil indicado.",
                operation="Leer perfil de subtítulos",
                resource=str(path),
                technical_metadata={"line": error.lineno, "column": error.colno},
            ) from error
        except OSError as error:
            raise create_operational_error(
                family="FILESYSTEM",
                user_message="No se pudo leer el perfil de subtítulos.",
                recommended_action="Revise la ruta y permisos del perfil.",
                operation="Leer perfil de subtítulos",
                resource=str(path),
            ) from error
        if not isinstance(data, dict):
            error = TypeError(
                f"El perfil de subtitulos debe ser JSON object: {path}."
            )
            raise create_operational_error(
                family="CONFIG",
                user_message="El perfil de subtítulos debe ser un objeto JSON.",
                recommended_action="Corrija la estructura JSON del perfil.",
                operation="Leer perfil de subtítulos",
                resource=str(path),
            ) from error
        return data

    def _validate_identity(self, data, profile_key, path):
        expected = {
            "component": profile_key.component.value,
            "format": profile_key.format,
            "family": profile_key.family,
            "profile_id": profile_key.profile_id,
        }
        if any(data.get(field) != value for field, value in expected.items()):
            error = ValueError(
                "La identidad interna del perfil de subtitulos "
                f"no coincide con su ruta: {path}."
            )
            raise create_operational_error(
                family="PROFILE",
                user_message=(
                    "La identidad interna del perfil de subtítulos no coincide "
                    "con su ruta."
                ),
                recommended_action=(
                    "Revise component, format, family y profile_id del "
                    "perfil."
                ),
                operation="Validar perfil de subtítulos",
                resource=str(path),
                technical_metadata={
                    "requested_profile": self._profile_resource(profile_key),
                },
            ) from error

    def _display_name(self, data, path):
        display_name = data.get("display_name")
        if isinstance(display_name, str) and display_name.strip():
            return display_name.strip()
        error = ValueError(
            "El perfil de subtitulos requiere display_name: "
            f"{path}."
        )
        raise create_operational_error(
            family="VALIDATION",
            user_message="El perfil de subtítulos no declara display_name válido.",
            recommended_action="Corrija el contrato del perfil de subtítulos.",
            operation="Validar perfil de subtítulos",
            resource=str(path),
        ) from error

    @staticmethod
    def _require_key(profile_key):
        if not isinstance(profile_key, SubtitleProfileKey):
            raise TypeError(
                "SubtitleProfileResolver requiere un SubtitleProfileKey."
            )
        return profile_key

    def _require_operational_key(self, profile_key):
        try:
            return self._require_key(profile_key)
        except TypeError as error:
            raise create_operational_error(
                family="VALIDATION",
                user_message="La identidad de subtítulos no tiene el contrato requerido.",
                recommended_action="Use una SubtitleProfileKey completa y válida.",
                operation="Resolver perfil de subtítulos",
            ) from error

    def _ensure_within_profiles_root(self, path):
        root = self.profiles_root.resolve()
        candidate = Path(path).resolve()
        if candidate != root and root not in candidate.parents:
            raise ValueError(
                "La ruta de subtitulos queda fuera de config/profiles."
            )
        return candidate

    def _validate_profile_contract(self, data, path):
        try:
            cue_policy = data.get("cue_policy")
            render_style = data.get("render_style")
            if not isinstance(cue_policy, dict):
                raise TypeError(f"cue_policy invalida en {path}.")
            if not isinstance(render_style, dict):
                raise TypeError(f"render_style invalido en {path}.")
            CueModelRegistry().resolve(CueModelRegistry.mode_from(cue_policy))
            TextCasePolicy.from_cue_policy(cue_policy)
            subtitle_style = SubtitleConfigLoader().load_render_style(
                render_style,
                profile_path=path,
            )
            if (
                subtitle_style.word_effect is not None
                and subtitle_style.word_effect.name == "continuous_karaoke"
            ):
                SyllabifierPolicy.from_cue_policy(cue_policy)
        except (KeyError, TypeError, ValueError) as error:
            raise create_operational_error(
                family="VALIDATION",
                user_message="El perfil de subtítulos no cumple su contrato.",
                recommended_action=(
                    "Corrija cue_policy y render_style del perfil indicado."
                ),
                operation="Validar perfil de subtítulos",
                resource=str(path),
            ) from error

    @staticmethod
    def _profile_resource(profile_key):
        return "/".join(
            (
                profile_key.component.value,
                profile_key.format,
                profile_key.family,
                profile_key.profile_id,
            )
        )
