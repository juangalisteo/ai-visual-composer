import json
import os
from pathlib import Path

from app.shared.profile_identity import ProfileKey
from app.shared.profile_resolver import ProfileResolver


class ConfigManager:

    def __init__(
        self,
        profile_resolver=None
    ):
        self.config_path = Path("config")
        self.profile_resolver = (
            profile_resolver
            or ProfileResolver(
                self.config_path / "profiles"
            )
        )

    def load_json(self, path):
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)

    def get_app_config(self):
        return self.load_json(self.config_path / "app.json")

    def get_ai_config(self):
        return self.load_json(self.config_path / "ai.json")

    def get_voice_config(self):
        selected_voice_config = os.environ.get("MC_VOICE_CONFIG")

        if not selected_voice_config:
            selected_voice_config = "masculina"

        voice_config_path = (
            self.config_path
            / "voice_configs"
            / f"{selected_voice_config}.json"
        )

        return self.load_json(voice_config_path)

    def get_profile_config(self):
        profile_key = self.get_profile_key()
        selected_profile_path = os.environ.get("MC_PROFILE_PATH")

        if profile_key is not None:
            resolved_path = self.profile_resolver.resolve(
                profile_key
            )
            if selected_profile_path and (
                Path(selected_profile_path).resolve()
                != resolved_path.resolve()
            ):
                raise ValueError(
                    "MC_PROFILE_PATH no coincide con la "
                    "identidad de perfil seleccionada."
                )
            return self.profile_resolver.load(
                profile_key
            )

        if selected_profile_path:
            return self.load_json(Path(selected_profile_path))

        app = self.get_app_config()

        platform = app["platform"]
        profile = app["profile"]

        profile_path = (
            self.config_path
            / "profiles"
            / platform
            / f"{profile}.json"
        )

        return self.load_json(profile_path)

    def get_profile_key(self):
        values = (
            os.environ.get(
                "MC_PROFILE_COMPONENT",
                ""
            ).strip(),
            os.environ.get(
                "MC_PROFILE_PLATFORM",
                ""
            ).strip(),
            os.environ.get(
                "MC_PROFILE_ID",
                ""
            ).strip(),
        )

        if not any(values):
            return None
        if not all(values):
            raise ValueError(
                "La identidad de perfil requiere component, "
                "platform y profile_id."
            )

        return ProfileKey(
            component=values[0],
            platform=values[1],
            profile_id=values[2]
        )

    def get_subtitle_config(self):
        selected_subtitle_config = os.environ.get("MC_SUBTITLE_CONFIG")

        if not selected_subtitle_config:
            profile = self.get_profile_config()
            selected_subtitle_config = profile["subtitle_config"]

        subtitle_config_path = (
            self.config_path
            / "subtitle_configs"
            / f"{selected_subtitle_config}.json"
        )

        return self.load_json(subtitle_config_path)
