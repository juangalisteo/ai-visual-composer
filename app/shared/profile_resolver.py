import json
from dataclasses import dataclass
from pathlib import Path

from app.shared.profile_identity import (
    OperationalProfileKey,
    ProfileComponent,
    coerce_profile_format,
)
from app.shared.operational_error import create_operational_error


@dataclass(frozen=True)
class OperationalProfileDescriptor:
    """An operational document discovered at its component/format root."""

    key: OperationalProfileKey
    path: Path
    display_name: str


class ProfileResolver:
    def __init__(
        self,
        profiles_root=Path("config/profiles")
    ):
        self.profiles_root = Path(
            profiles_root
        )

    def discover_operational_profiles(self, component, profile_format):
        """Discover operational documents by canonical identity.

        Operational documents exist only at component/format root. Subtitle
        families are resolved by ``SubtitleProfileResolver`` independently.
        """
        component = ProfileComponent(component)
        profile_format = coerce_profile_format(profile_format)
        descriptors = self._operational_candidates(component, profile_format)
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
                profile_key.format,
            )
            if descriptor.key.profile_id == profile_key.profile_id
        ]
        if not matches:
            error = FileNotFoundError(
                f"No existe un perfil operacional: {profile_key.profile_id}"
            )
            raise create_operational_error(
                family="PROFILE",
                user_message="No se encontró el perfil operacional solicitado.",
                recommended_action=(
                    "Revise la identidad seleccionada y la configuración de "
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
        path = self.resolve_operational(profile_key)
        profile = self._load_profile_json(path)
        self._validate_format_orientation(profile, path)
        return profile

    @staticmethod
    def _validate_format_orientation(profile, path):
        """Reject a declared format that contradicts video_style size."""
        profile_format = profile.get("format")
        video_style = profile.get("video_style")
        if not isinstance(profile_format, str) or not isinstance(
            video_style,
            dict,
        ):
            return
        width = video_style.get("width")
        height = video_style.get("height")
        if not all(
            isinstance(value, int) and not isinstance(value, bool)
            for value in (width, height)
        ):
            return

        profile_format = profile_format.strip().lower()
        if profile_format == "vertical" and width > height:
            orientation = "más ancho que alto"
        elif profile_format == "horizontal" and width < height:
            orientation = "más alto que ancho"
        else:
            return

        error = ValueError(
            f"format={profile_format} contradice video_style "
            f"{width}x{height}."
        )
        raise create_operational_error(
            family="CONFIG",
            user_message=(
                f"El perfil declara format «{profile_format}», pero "
                f"video_style mide {width}x{height} ({orientation})."
            ),
            recommended_action=(
                "Corrige format o video_style.width/height para que "
                "cuadren."
            ),
            operation="Validar perfil operacional",
            resource=str(path),
        ) from error

    def _operational_candidates(self, component, profile_format):
        return self._discover_root_operational_profiles(component, profile_format)

    def _discover_root_operational_profiles(self, component, profile_format):
        directory = self.profiles_root / component.value / profile_format
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
                profile_format,
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
            "format": key.format,
            "profile_id": key.profile_id,
        }
        if not isinstance(data, dict) or any(
            data.get(field) != value
            for field, value in expected.items()
        ):
            error = ValueError(f"Identidad operacional inválida: {path}")
            raise create_operational_error(
                family="PROFILE",
                user_message=(
                    "La identidad interna del perfil operacional no coincide "
                    "con su ruta."
                ),
                recommended_action=(
                    "Revise component, format y profile_id del perfil."
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

    def discover_formats(self, component):
        component = ProfileComponent(component)
        directory = self.profiles_root / component.value
        self._ensure_within_profiles_root(directory)
        if not directory.is_dir():
            return ()
        profile_formats = []
        for path in directory.iterdir():
            if not path.is_dir():
                continue
            try:
                profile_format = coerce_profile_format(path.name)
            except ValueError:
                continue
            self._ensure_within_profiles_root(path)
            profile_formats.append(profile_format)
        return tuple(sorted(profile_formats))

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
        declarative_matches = self._declarative_video_component_matches(
            profile_key
        )
        if len(declarative_matches) == 1:
            return declarative_matches[0]
        if len(declarative_matches) > 1:
            self._raise_ambiguous_video_component_documents(
                profile_key,
                declarative_matches,
            )
        self._raise_missing_declarative_video_component_document(profile_key)

    def _declarative_video_component_matches(
        self,
        profile_key,
    ):
        directory = (
            self.profiles_root
            / ProfileComponent.VIDEO.value
            / profile_key.format
        )
        self._ensure_within_profiles_root(directory)
        if not directory.is_dir():
            return ()

        matches = []
        for path in sorted(
            directory.glob("*.json"),
            key=lambda item: item.name.casefold(),
        ):
            self._ensure_within_profiles_root(path)
            data = self._load_profile_json(path)
            if not self._is_declarative_video_component_document(data):
                continue
            document = self._validate_declarative_video_component_document(
                data,
                path,
                profile_key,
            )
            if document.operational_profile.profile_id == profile_key.profile_id:
                matches.append(path)
        return tuple(matches)

    @staticmethod
    def _is_declarative_video_component_document(data):
        return isinstance(data, dict) and (
            data.get("kind") == "video_component"
            or "operational_profile_id" in data
        )

    def _validate_declarative_video_component_document(
        self,
        data,
        path,
        requested_key,
    ):
        # Import deferred: the video-component package currently imports
        # configuration consumers which import this resolver. Declarative WAN
        # validation occurs only after ProfileResolver is fully initialized.
        from app.modules.video_component.contracts import (
            WanDeliveryParameters,
            WanGenerationParameters,
            WanSamplingParameters,
            WanVideoComponentDocument,
        )

        try:
            if data.get("kind") != "video_component":
                raise ValueError("kind must be video_component.")
            declared_format = data["format"]
            if declared_format != requested_key.format:
                raise ValueError(
                    "format must match the requested directory exactly."
                )
            operational_key = OperationalProfileKey(
                ProfileComponent.VIDEO,
                declared_format,
                data["operational_profile_id"],
            )
            component = data["video_component"]
            generation = component["generation"]
            try:
                delivery = component["delivery"]
            except KeyError as error:
                raise ValueError(
                    "video_component.delivery is required."
                ) from error
            if not isinstance(delivery, dict):
                raise ValueError("video_component.delivery must be an object.")
            try:
                intermediate_output = delivery["intermediate_output"]
            except KeyError as error:
                raise ValueError(
                    "video_component.delivery.intermediate_output is required."
                ) from error
            sampling = component["sampling"]
            return WanVideoComponentDocument(
                kind=data["kind"],
                operational_profile=operational_key,
                format=declared_format,
                generation=WanGenerationParameters(
                    width=generation["width"],
                    height=generation["height"],
                    frames=component["frames"],
                    fps=component["fps"],
                    seed_mode=component["seed_mode"],
                    seed=component.get("seed"),
                ),
                delivery=WanDeliveryParameters(
                    intermediate_output=intermediate_output,
                ),
                sampling=WanSamplingParameters(
                    steps=sampling["steps"],
                    cfg=sampling["cfg"],
                    sampler=sampling["sampler"],
                    scheduler=sampling["scheduler"],
                ),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise self._invalid_video_component_document(
                path,
                requested_key,
                error,
            ) from error

    def _invalid_video_component_document(
        self,
        path,
        profile_key,
        error,
    ):
        return create_operational_error(
            family="CONFIG",
            user_message=(
                "El documento declarativo de componente Wan no es válido."
            ),
            recommended_action=(
                "Revise kind, operational_profile_id, format y video_component."
            ),
            operation="Validar componente Wan declarativo",
            resource=str(path),
            technical_metadata={
                "requested_profile": self._operational_resource(profile_key),
                "validation_error": str(error),
            },
        )

    def _raise_ambiguous_video_component_documents(
        self,
        profile_key,
        paths,
    ):
        error = ValueError(
            "operational_profile_id Wan duplicado: "
            f"{profile_key.profile_id}"
        )
        raise create_operational_error(
            family="CONFIG",
            user_message=(
                "La identidad operacional coincide con varios componentes Wan."
            ),
            recommended_action=(
                "Elimine o corrija los documentos Wan declarativos duplicados."
            ),
            operation="Resolver componente Wan declarativo",
            resource=self._operational_resource(profile_key),
            technical_metadata={
                "candidates": [str(path) for path in paths],
            },
        ) from error

    def _raise_missing_declarative_video_component_document(
        self,
        profile_key,
    ):
        directory = (
            self.profiles_root
            / ProfileComponent.VIDEO.value
            / profile_key.format
        )
        error = FileNotFoundError(
            "No existe un documento Wan declarativo para la identidad solicitada."
        )
        raise create_operational_error(
            family="CONFIG",
            user_message=(
                "No existe un componente Wan declarativo para el perfil solicitado."
            ),
            recommended_action=(
                "Cree exactamente un documento video_component válido en el "
                "directorio del formato solicitado."
            ),
            operation="Resolver componente Wan declarativo",
            resource=str(directory),
            technical_metadata={
                "component": ProfileComponent.VIDEO.value,
                "format": profile_key.format,
                "profile_id": profile_key.profile_id,
                "requested_profile": self._operational_resource(profile_key),
                "discovery_root": str(directory),
            },
        ) from error

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
            "La resolución operacional canónica requiere una "
            "OperationalProfileKey."
        )

    @staticmethod
    def _operational_resource(profile_key):
        return "/".join(
            (
                profile_key.component.value,
                profile_key.format,
                profile_key.profile_id,
            )
        )
