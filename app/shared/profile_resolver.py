import json
from pathlib import Path

from app.shared.profile_identity import (
    ProfileComponent,
    ProfileFamily,
    ProfileKey,
    ProfilePlatform,
)
from app.shared.subtitle_profile_identity import (
    coerce_subtitle_style,
)


class ProfileResolver:

    _PROFILE_PATHS = {
        (
            ProfileComponent.GUION,
            ProfilePlatform.INSTAGRAM,
        ): Path(
            "guion/instagram/perfil_guion_instagram.json"
        ),
        (
            ProfileComponent.GUION,
            ProfilePlatform.YOUTUBE,
        ): Path(
            "guion/youtube/perfil_guion_youtube.json"
        ),
        (
            ProfileComponent.IMAGEN,
            ProfilePlatform.INSTAGRAM,
        ): Path(
            "imagen/instagram/perfil_imagen_instagram.json"
        ),
        (
            ProfileComponent.IMAGEN,
            ProfilePlatform.YOUTUBE,
        ): Path(
            "imagen/youtube/perfil_imagen_youtube.json"
        ),
        (
            ProfileComponent.VIDEO,
            ProfilePlatform.INSTAGRAM,
        ): Path(
            "video/instagram/perfil_video_instagram.json"
        ),
        (
            ProfileComponent.VIDEO,
            ProfilePlatform.YOUTUBE,
        ): Path(
            "video/youtube/perfil_video_youtube.json"
        ),
        (
            ProfileComponent.STUDIO,
            ProfilePlatform.INSTAGRAM,
        ): Path(
            "studio/instagram/perfil_studio_instagram.json"
        ),
        (
            ProfileComponent.STUDIO,
            ProfilePlatform.YOUTUBE,
        ): Path(
            "studio/youtube/perfil_studio_youtube.json"
        ),
    }

    _VIDEO_COMPONENT_PATHS = {
        ProfilePlatform.INSTAGRAM: Path(
            "video/instagram/wan_i2v_instagram.json"
        ),
        ProfilePlatform.YOUTUBE: Path(
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
        profile_key = self._require_profile_key(
            profile_key
        )
        if profile_key.family is ProfileFamily.DESIGN:
            path = self._design_path(profile_key)
            self._validate_design_identity(self._load_json(path), profile_key, path)
            return path
        relative_path = self._PROFILE_PATHS.get(
            (
                profile_key.component,
                profile_key.platform,
            )
        )
        if relative_path is None:
            raise ValueError(
                "Combinación de perfil no soportada: "
                f"{profile_key.profile_id}"
            )
        return self._existing_path(
            relative_path
        )

    def discover(self, component, platform, family=ProfileFamily.SYSTEM):
        component = ProfileComponent(component)
        platform = ProfilePlatform(platform)
        family = ProfileFamily(family)
        if family is ProfileFamily.SYSTEM:
            key = ProfileKey.for_component(component, platform)
            return ((key, self.load(key).get("display_name", key.profile_id)),)
        directory = self.profiles_root / component.value / platform.value / "design"
        if not directory.is_dir():
            return ()
        discovered = []
        for path in sorted(directory.glob("*.json"), key=lambda item: item.name.casefold()):
            try:
                data = self._load_json(path)
                key = ProfileKey(component, platform, data.get("profile_id", ""), family)
                self._validate_design_identity(data, key, path)
                self.declared_subtitle_style(key)
                if path.resolve() != self._design_path(key).resolve():
                    raise ValueError(
                        "La ruta del perfil DESIGN no coincide con su identidad."
                    )
            except (
                FileNotFoundError,
                TypeError,
                ValueError,
                json.JSONDecodeError,
            ):
                continue
            discovered.append((key, data["display_name"]))
        return tuple(sorted(discovered, key=lambda item: item[1].casefold()))

    def declared_subtitle_style(self, profile_key):
        """Return a concrete DESIGN profile's declared subtitle style."""
        profile_key = self._require_profile_key(profile_key)
        if profile_key.family is ProfileFamily.SYSTEM:
            return None

        style = self.load(profile_key).get("subtitle_config")
        if not isinstance(style, str) or not style.strip():
            raise ValueError(
                "El perfil DESIGN requiere subtitle_config declarado: "
                f"{profile_key.profile_id}"
            )
        style = coerce_subtitle_style(style)
        embedded = self.load(profile_key).get("subtitle_profile")
        if not isinstance(embedded, dict):
            raise ValueError(
                "El perfil DESIGN requiere subtitle_profile embebido: "
                f"{profile_key.profile_id}"
            )
        if embedded.get("style") not in (None, style.value if hasattr(style, "value") else style):
            raise ValueError(
                "subtitle_profile.style no coincide con subtitle_config: "
                f"{profile_key.profile_id}"
            )
        return style

    def _design_path(self, profile_key):
        slug = profile_key.profile_id.removeprefix(
            f"{profile_key.component.value}_{profile_key.platform.value}_design_"
        )
        path = self.profiles_root / profile_key.component.value / profile_key.platform.value / "design" / f"{slug}.json"
        if not path.is_file():
            raise FileNotFoundError(f"No existe el perfil DESIGN esperado: {path}")
        return path

    @staticmethod
    def _validate_design_identity(data, key, path):
        expected = {"component": key.component.value, "platform": key.platform.value, "family": "design", "profile_id": key.profile_id}
        if not isinstance(data, dict) or any(data.get(field) != value for field, value in expected.items()) or not isinstance(data.get("display_name"), str) or not data["display_name"].strip():
            raise ValueError(f"Identidad DESIGN inválida: {path}")

    def load(
        self,
        profile_key
    ):
        return self._load_json(
            self.resolve(profile_key)
        )

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
        return self._existing_path(
            self._VIDEO_COMPONENT_PATHS[
                profile_key.platform
            ]
        )

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
