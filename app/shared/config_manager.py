import json
import os
from pathlib import Path


class ConfigManager:

    def __init__(self):
        self.config_path = Path("config")

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
        selected_profile_path = os.environ.get("MC_PROFILE_PATH")

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
