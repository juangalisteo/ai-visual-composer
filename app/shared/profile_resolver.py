import json
from pathlib import Path

from app.shared.profile_identity import (
    ProfileComponent,
    ProfileKey,
    ProfilePlatform,
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
