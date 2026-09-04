import json
import os
from copy import deepcopy
from pathlib import Path

from app.shared.profile_identity import ProfileKey
from app.shared.profile_resolver import ProfileResolver
from app.shared.subtitle_profile_identity import (
    ResolvedSubtitleProfile,
    SubtitleProfileKey,
    coerce_subtitle_style,
)
from app.shared.subtitle_profile_resolver import (
    SubtitleProfileResolver,
)


class ConfigManager:

    def __init__(
        self,
        profile_resolver=None,
        subtitle_profile_resolver=None
    ):
        self.config_path = Path("config")
        self.profile_resolver = (
            profile_resolver
            or ProfileResolver(
                self.config_path / "profiles"
            )
        )
        self.subtitle_profile_resolver = (
            subtitle_profile_resolver
            or SubtitleProfileResolver(
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
        if profile_key is not None:
            return self.profile_resolver.load(profile_key)

        raise ValueError(
            "Falta identidad estructurada de perfil. Configure "
            "MC_PROFILE_COMPONENT, MC_PROFILE_PLATFORM y "
            "MC_PROFILE_ID."
        )

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
        return deepcopy(
            self.get_subtitle_profile().cue_policy
        )

    def get_subtitle_profile(self):
        profile_key = self.get_profile_key()
        profile = self.get_profile_config()
        selected_subtitle_config = os.environ.get("MC_SUBTITLE_CONFIG")

        if not selected_subtitle_config:
            selected_subtitle_config = profile["subtitle_config"]

        style = coerce_subtitle_style(
            selected_subtitle_config
        )

        if profile_key is not None:
            subtitle_key = SubtitleProfileKey.for_profile(
                profile_key=profile_key,
                style=style
            )
            return self.subtitle_profile_resolver.load(
                subtitle_key
            )

        subtitle_config_path = (
            self.config_path
            / "subtitle_configs"
            / f"{style.value}.json"
        )

        video_style = profile.get(
            "video_style",
            {}
        )
        render_style = video_style.get(
            "subtitles",
            {}
        )
        if not isinstance(render_style, dict):
            raise TypeError(
                "La configuracion legacy "
                "video_style.subtitles debe ser un diccionario."
            )

        return ResolvedSubtitleProfile(
            key=None,
            path=subtitle_config_path,
            cue_policy=deepcopy(
                self.load_json(subtitle_config_path)
            ),
            render_style=deepcopy(render_style),
            legacy=True
        )
