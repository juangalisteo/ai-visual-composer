import json
from copy import deepcopy
from pathlib import Path

from app.shared.subtitle_profile_identity import (
    ResolvedSubtitleProfile,
    SubtitleProfileDescriptor,
    SubtitleProfileKey,
)
from app.shared.profile_identity import ProfileKey
from app.shared.profile_resolver import ProfileResolver
from app.modules.subtitles.text_case import TextCasePolicy
from app.modules.video.config.loaders.subtitle_loader import (
    SubtitleConfigLoader,
)


class SubtitleProfileResolver:

    def __init__(
        self,
        profiles_root=Path("config/profiles")
    ):
        self.profiles_root = Path(profiles_root)

    def resolve(
        self,
        profile_key
    ):
        profile_key = self._require_key(profile_key)
        root = self.profiles_root.resolve()
        candidate = (
            self.profiles_root
            / profile_key.relative_path
        ).resolve()

        if candidate != root and root not in candidate.parents:
            raise ValueError(
                "La ruta de subtitulos queda fuera de "
                "config/profiles."
            )
        if not candidate.is_file():
            raise FileNotFoundError(
                "No existe el perfil de subtitulos esperado: "
                f"{candidate}"
            )

        return self.profiles_root / profile_key.relative_path

    def load(
        self,
        profile_key
    ):
        profile_key = self._require_key(profile_key)
        path = self.resolve(profile_key)

        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        source_data = data
        if profile_key.family.value == "design":
            data = self._design_subtitle_data(
                data=data,
                profile_key=profile_key,
                path=path,
            )

        self._validate_identity(
            data=data,
            profile_key=profile_key,
            path=path
        )

        cue_policy = data.get("cue_policy")
        render_style = data.get("render_style")
        display_name = self._display_name(
            data=(
                source_data
                if profile_key.family.value == "design"
                else data
            ),
            profile_key=profile_key,
            path=path,
        )
        if not isinstance(cue_policy, dict):
            raise TypeError(
                f"cue_policy invalida en {path}."
            )
        if not isinstance(render_style, dict):
            raise TypeError(
                f"render_style invalido en {path}."
            )
        self._validate_profile_contract(data, path)

        return ResolvedSubtitleProfile(
            key=profile_key,
            path=path,
            display_name=display_name,
            cue_policy=deepcopy(cue_policy),
            render_style=deepcopy(render_style)
        )

    def discover_profiles(
        self,
        profile_key,
    ):
        if not isinstance(profile_key, ProfileKey):
            raise TypeError(
                "La identidad principal debe ser un ProfileKey."
            )

        if profile_key.family.value == "design":
            style = ProfileResolver(self.profiles_root).declared_subtitle_style(
                profile_key
            )
            key = SubtitleProfileKey.for_profile(profile_key, style)
            resolved = self.load(key)
            return (
                SubtitleProfileDescriptor(
                    key=key,
                    display_name=resolved.display_name,
                ),
            )

        directory = (
            self.profiles_root
            / profile_key.component.value
            / profile_key.platform.value
            / "estandar"
        )
        if not directory.is_dir():
            raise FileNotFoundError(
                "No existe la carpeta de perfiles de subtitulos: "
                f"{directory}"
            )

        discovered = []
        profile_ids = set()
        for path in sorted(directory.glob("*.json"), key=lambda item: item.name.casefold()):
            with path.open("r", encoding="utf-8") as file:
                data = json.load(file)

            if not isinstance(data, dict):
                raise TypeError(
                    "El perfil de subtitulos debe ser JSON object: "
                    f"{path}."
                )

            key = SubtitleProfileKey(
                component=profile_key.component,
                platform=profile_key.platform,
                style=data.get("style"),
                profile_id=data.get("profile_id", ""),
                family=profile_key.family,
                parent_profile_id=profile_key.profile_id,
            )
            self._validate_identity(
                data=data,
                profile_key=key,
                path=path,
            )
            self._validate_profile_contract(
                data=data,
                path=path,
            )
            if path != self.resolve(key):
                raise ValueError(
                    "La ruta del perfil de subtitulos no coincide "
                    f"con su identidad: {path}."
                )
            if key.profile_id in profile_ids:
                raise ValueError(
                    "profile_id de subtitulos duplicado: "
                    f"{key.profile_id}"
                )
            profile_ids.add(key.profile_id)
            discovered.append(
                SubtitleProfileDescriptor(
                    key=key,
                    display_name=self._display_name(
                        data=data,
                        profile_key=key,
                        path=path,
                    ),
                )
            )

        if not discovered:
            raise FileNotFoundError(
                "No existen perfiles de subtitulos para: "
                f"{profile_key.profile_id}."
            )
        return tuple(
            sorted(
                discovered,
                key=lambda descriptor: (
                    descriptor.display_name.casefold(),
                    descriptor.profile_id,
                ),
            )
        )

    def load_selection(
        self,
        profile_key,
        selection,
    ):
        if not isinstance(profile_key, ProfileKey):
            raise TypeError(
                "La identidad principal debe ser un ProfileKey."
            )
        if isinstance(selection, SubtitleProfileKey):
            if (
                selection.component is not profile_key.component
                or selection.platform is not profile_key.platform
                or selection.family is not profile_key.family
            ):
                raise ValueError(
                    "La seleccion de subtitulos no coincide con el perfil."
                )
            return self.load(selection)

        selected = (
            selection.value
            if hasattr(selection, "value")
            else str(selection)
        )
        selected = str(selected).strip().lower()
        if not selected:
            raise ValueError("La seleccion de subtitulos esta vacia.")

        descriptors = self.discover_profiles(profile_key)
        for descriptor in descriptors:
            if descriptor.profile_id == selected:
                return self.load(descriptor.key)

        matches = [
            descriptor
            for descriptor in descriptors
            if (
                descriptor.style.value
                if hasattr(descriptor.style, "value")
                else descriptor.style
            ) == selected
        ]
        if len(matches) == 1:
            return self.load(matches[0].key)
        if len(matches) > 1:
            raise ValueError(
                "La seleccion heredada por style es ambigua; "
                "use profile_id."
            )
        raise ValueError(
            "No existe el perfil de subtitulos seleccionado: "
            f"{selection}"
        )

    def discover_styles(
        self,
        profile_key
    ):
        if not isinstance(profile_key, ProfileKey):
            raise TypeError(
                "La identidad principal debe ser un ProfileKey."
            )

        return tuple(
            descriptor.style
            for descriptor in self.discover_profiles(profile_key)
        )

    def _design_subtitle_data(self, *, data, profile_key, path):
        """Extract the embedded subtitle configuration from one design JSON."""
        expected_parent = ProfileKey(
            component=profile_key.component,
            platform=profile_key.platform,
            profile_id=profile_key.parent_profile_id,
            family=profile_key.family,
        )
        ProfileResolver._validate_design_identity(data, expected_parent, path)

        declared_style = data.get("subtitle_config")
        expected_style = (
            profile_key.style.value
            if hasattr(profile_key.style, "value")
            else profile_key.style
        )
        if declared_style != expected_style:
            raise ValueError(
                "El perfil DESIGN declara un estilo de subtitulos distinto: "
                f"{path}."
            )

        embedded = data.get("subtitle_profile")
        if not isinstance(embedded, dict):
            raise TypeError(
                "El perfil DESIGN requiere subtitle_profile embebido: "
                f"{path}."
            )

        return {
            "component": profile_key.component.value,
            "platform": profile_key.platform.value,
            "profile_id": profile_key.profile_id,
            "style": expected_style,
            "family": "design",
            "parent_profile_id": profile_key.parent_profile_id,
            **embedded,
        }

    def _validate_identity(
        self,
        data,
        profile_key,
        path
    ):
        if not isinstance(data, dict):
            raise TypeError(
                f"El perfil de subtitulos debe ser JSON object: {path}."
            )

        expected = {
            "component": profile_key.component.value,
            "platform": profile_key.platform.value,
            "profile_id": profile_key.profile_id,
            "style": (
                profile_key.style.value
                if hasattr(profile_key.style, "value")
                else profile_key.style
            ),
        }
        if profile_key.family.value == "design":
            expected["family"] = "design"
            expected["parent_profile_id"] = profile_key.parent_profile_id
        actual = {
            field: data.get(field)
            for field in expected
        }
        if actual != expected:
            raise ValueError(
                "La identidad interna del perfil de subtitulos "
                f"no coincide con su ruta: {path}."
            )

    @staticmethod
    def _display_name(data, profile_key, path):
        display_name = data.get("display_name")
        if isinstance(display_name, str) and display_name.strip():
            return display_name.strip()

        if (
            profile_key.family.value != "design"
            and SubtitleProfileKey.is_legacy_standard_profile_id(
                component=profile_key.component,
                platform=profile_key.platform,
                style=profile_key.style,
                profile_id=profile_key.profile_id,
            )
        ):
            return profile_key.profile_id

        raise ValueError(
            "El perfil de subtitulos requiere display_name: "
            f"{path}."
        )

    def _require_key(
        self,
        profile_key
    ):
        if not isinstance(profile_key, SubtitleProfileKey):
            raise TypeError(
                "SubtitleProfileResolver requiere un "
                "SubtitleProfileKey."
            )
        return profile_key

    @staticmethod
    def _validate_profile_contract(data, path):
        cue_policy = data.get("cue_policy")
        render_style = data.get("render_style")
        if not isinstance(cue_policy, dict):
            raise TypeError(f"cue_policy invalida en {path}.")
        if not isinstance(render_style, dict):
            raise TypeError(f"render_style invalido en {path}.")
        TextCasePolicy.from_cue_policy(cue_policy)
        SubtitleConfigLoader().load_render_style(
            render_style,
            profile_path=path,
        )
