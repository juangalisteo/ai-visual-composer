import json
from copy import deepcopy
from pathlib import Path

from app.shared.subtitle_profile_identity import (
    ResolvedSubtitleProfile,
    SubtitleProfileKey,
)
from app.shared.profile_identity import ProfileKey
from app.shared.profile_resolver import ProfileResolver


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
        if not isinstance(cue_policy, dict):
            raise TypeError(
                f"cue_policy invalida en {path}."
            )
        if not isinstance(render_style, dict):
            raise TypeError(
                f"render_style invalido en {path}."
            )

        return ResolvedSubtitleProfile(
            key=profile_key,
            path=path,
            cue_policy=deepcopy(cue_policy),
            render_style=deepcopy(render_style)
        )

    def discover_styles(
        self,
        profile_key
    ):
        if not isinstance(profile_key, ProfileKey):
            raise TypeError(
                "La identidad principal debe ser un ProfileKey."
            )

        if profile_key.family.value == "design":
            data = ProfileResolver(self.profiles_root).load(profile_key)
            style = data.get("subtitle_config")
            key = SubtitleProfileKey.for_profile(profile_key, style)
            self.load(key)
            return (key.style,)

        directory = self.profiles_root / profile_key.component.value / profile_key.platform.value / "estandar"
        if not directory.is_dir():
            raise FileNotFoundError(
                "No existe la carpeta de perfiles de subtitulos: "
                f"{directory}"
            )

        styles = []
        for path in sorted(directory.glob("*.json")):
            with path.open("r", encoding="utf-8") as file:
                data = json.load(file)

            if not isinstance(data, dict):
                raise TypeError(
                    "El perfil de subtitulos debe ser JSON object: "
                    f"{path}."
                )

            style = data.get("style")
            key = SubtitleProfileKey(
                component=profile_key.component,
                platform=profile_key.platform,
                style=style,
                profile_id=data.get("profile_id", ""),
                family=profile_key.family,
                parent_profile_id=profile_key.profile_id,
            )
            self._validate_identity(
                data=data,
                profile_key=key,
                path=path
            )
            if path != self.resolve(key):
                raise ValueError(
                    "La ruta del perfil de subtitulos no coincide "
                    f"con su identidad: {path}."
                )
            styles.append(key.style)

        if not styles:
            raise FileNotFoundError(
                "No existen perfiles de subtitulos para: "
                f"{profile_key.profile_id}."
            )
        return tuple(styles)

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
