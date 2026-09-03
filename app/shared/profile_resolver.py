import json
from pathlib import Path

from app.shared.profile_identity import (
    ProfileComponent,
    ProfileKey,
    ProfilePlatform,
    coerce_profile_component,
    coerce_profile_platform,
)


class ProfileResolver:

    _LEGACY_PROFILE_PATHS = {
        (
            ProfileComponent.GUION,
            ProfilePlatform.INSTAGRAM,
        ): Path("guion/instagram.json"),
        (
            ProfileComponent.GUION,
            ProfilePlatform.YOUTUBE,
        ): Path("guion/youtube.json"),
        (
            ProfileComponent.IMAGEN,
            ProfilePlatform.INSTAGRAM,
        ): Path("instagram/modo_conciencia.json"),
        (
            ProfileComponent.IMAGEN,
            ProfilePlatform.YOUTUBE,
        ): Path("youtube/modo_conciencia.json"),
        (
            ProfileComponent.VIDEO,
            ProfilePlatform.INSTAGRAM,
        ): Path("instagram/modo_conciencia.json"),
        (
            ProfileComponent.VIDEO,
            ProfilePlatform.YOUTUBE,
        ): Path("youtube/modo_conciencia.json"),
    }

    _LEGACY_VIDEO_COMPONENT_PATHS = {
        ProfilePlatform.INSTAGRAM: Path(
            "video/instagram.json"
        ),
        ProfilePlatform.YOUTUBE: Path(
            "video/youtube.json"
        ),
    }

    _LEGACY_DESIGN_PATHS = {
        (
            ProfileComponent.IMAGEN,
            ProfilePlatform.INSTAGRAM,
        ): Path("diseno/imagen/instagram.json"),
        (
            ProfileComponent.IMAGEN,
            ProfilePlatform.YOUTUBE,
        ): Path("diseno/imagen/youtube.json"),
        (
            ProfileComponent.VIDEO,
            ProfilePlatform.INSTAGRAM,
        ): Path("diseno/video/instagram.json"),
        (
            ProfileComponent.VIDEO,
            ProfilePlatform.YOUTUBE,
        ): Path("diseno/video/youtube.json"),
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
        relative_path = self._LEGACY_PROFILE_PATHS.get(
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
            self._LEGACY_VIDEO_COMPONENT_PATHS[
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

    def resolve_design(
        self,
        target_component,
        platform
    ):
        target_component = coerce_profile_component(
            target_component
        )
        platform = coerce_profile_platform(
            platform
        )
        relative_path = self._LEGACY_DESIGN_PATHS.get(
            (
                target_component,
                platform,
            )
        )
        if relative_path is None:
            raise ValueError(
                "Diseño solo admite los destinos imagen "
                "y video."
            )
        return self._existing_path(
            relative_path
        )

    def load_design(
        self,
        target_component,
        platform
    ):
        return self._load_json(
            self.resolve_design(
                target_component,
                platform
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
                f"No existe el perfil legacy esperado: {candidate}"
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
