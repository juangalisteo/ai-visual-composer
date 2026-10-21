import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from app.modules.video_component.profile_parameters import (
    load_video_component_parameters,
)
from app.modules.video.video_config import VideoConfigLoader
from app.shared.config_manager import ConfigManager
from app.shared.profile_identity import (
    OperationalProfileKey,
    ProfileComponent,
)
from app.shared.profile_resolver import ProfileResolver
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


OPERATIONAL_PROFILE_IDS = {
    (ProfileComponent.GUION, "instagram"): "guion_instagram",
    (ProfileComponent.GUION, "youtube"): "guion_youtube",
    (ProfileComponent.IMAGEN, "instagram"): "imagen_instagram",
    (ProfileComponent.IMAGEN, "youtube"): "imagen_youtube",
    (ProfileComponent.VIDEO, "instagram"): "video_instagram",
    (ProfileComponent.VIDEO, "youtube"): "video_youtube",
}

OFFICIAL_SUBTITLE_PROFILE_IDS = {
    (ProfileComponent.GUION, "instagram"): (
        "subtitulo_guion_instagram_palabra_por_palabra"
    ),
    (ProfileComponent.GUION, "youtube"): "subtitulo_guion_youtube_linea_unica",
    (ProfileComponent.IMAGEN, "instagram"): (
        "subtitulo_imagen_instagram_palabra_por_palabra"
    ),
    (ProfileComponent.IMAGEN, "youtube"): "subtitulo_imagen_youtube_linea_unica",
    (ProfileComponent.VIDEO, "instagram"): (
        "subtitulo_video_instagram_palabra_por_palabra"
    ),
    (ProfileComponent.VIDEO, "youtube"): "subtitulo_video_youtube_linea_unica",
}


def _profile_key(component, platform):
    return OperationalProfileKey(
        component,
        platform,
        OPERATIONAL_PROFILE_IDS[(component, platform)],
    )


def _official_subtitle_key(profile_key):
    return SubtitleProfileKey(
        profile_key.component,
        profile_key.platform,
        OFFICIAL_SUBTITLE_PROFILE_IDS[
            (profile_key.component, profile_key.platform)
        ],
        "estandar",
    )


def _operational_key(profile_key):
    return OperationalProfileKey(
        profile_key.component,
        profile_key.platform,
        profile_key.profile_id,
    )


class ProfileCharacterizationTest(unittest.TestCase):

    RUNTIME_COMPONENTS = (
        ProfileComponent.GUION,
        ProfileComponent.IMAGEN,
        ProfileComponent.VIDEO,
    )

    PLATFORM_EXPECTATIONS = {
        "instagram": {
            "format": "vertical",
            "width": 1080,
            "height": 1920,
            "fps": 30,
            "subtitle_config": "word_by_word",
            "subtitle_font": "unisans",
            "subtitle_size": 14,
            "subtitle_margin": 55,
            "subtitle_offset": -0.06,
            "seconds_per_image": 20,
        },
        "youtube": {
            "format": "horizontal",
            "width": 1920,
            "height": 1080,
            "fps": 30,
            "subtitle_config": "single_line",
            "subtitle_font": "gotham",
            "subtitle_size": 16,
            "subtitle_margin": 25,
            "subtitle_offset": 0.0,
            "seconds_per_image": 30,
        },
    }

    def setUp(self):
        self.resolver = ProfileResolver()
        self.subtitle_resolver = SubtitleProfileResolver()

    def test_guion_image_and_video_profiles_keep_effective_behavior(self):
        for component in self.RUNTIME_COMPONENTS:
            for platform, expected in self.PLATFORM_EXPECTATIONS.items():
                with self.subTest(
                    component=component.value,
                    platform=platform
                ):
                    profile_key = _profile_key(
                        component,
                        platform
                    )
                    profile = self.resolver.load_operational(
                        _operational_key(profile_key)
                    )
                    video_style = profile["video_style"]
                    environment = self._identity_environment(
                        profile_key
                    )
                    with patch.dict(
                        os.environ,
                        environment,
                        clear=True
                    ):
                        subtitle_profile = (
                            ConfigManager().get_subtitle_profile_by_key(
                                _official_subtitle_key(profile_key)
                            )
                        )
                    subtitles = subtitle_profile.render_style

                    self.assertEqual(
                        platform,
                        profile["platform"]
                    )
                    self.assertEqual(
                        expected["format"],
                        profile["format"]
                    )
                    self.assertNotIn("resolution", profile)
                    self.assertEqual(
                        expected["width"],
                        video_style["width"]
                    )
                    self.assertEqual(
                        expected["height"],
                        video_style["height"]
                    )
                    self.assertEqual(
                        expected["fps"],
                        video_style["fps"]
                    )
                    self.assertNotIn("subtitle_config", profile)
                    self.assertNotIn("subtitles", video_style)
                    self.assertEqual(
                        expected["subtitle_font"],
                        subtitles["font"]
                    )
                    self.assertEqual(
                        expected["subtitle_size"],
                        subtitles["font_size"]
                    )
                    self.assertEqual(
                        expected["subtitle_margin"],
                        subtitles["margin_v"]
                    )
                    self.assertEqual(
                        expected["subtitle_offset"],
                        subtitles["offset"]
                    )
                    self.assertEqual(
                        expected["seconds_per_image"],
                        video_style["storyboard"][
                            "seconds_per_image"
                        ]
                    )
                    self.assertEqual(
                        "scene",
                        video_style["overlays"][
                            "repeat_mode"
                        ]
                    )
                    self.assertEqual(
                        "slow",
                        profile["video"]["preset"]
                    )
                    self.assertEqual(
                        16,
                        profile["video"]["crf"]
                    )

    def test_design_targets_use_component_profiles_without_own_tree(self):
        for target_component in (
            ProfileComponent.IMAGEN,
            ProfileComponent.VIDEO,
        ):
            for platform, expected in self.PLATFORM_EXPECTATIONS.items():
                with self.subTest(
                    target=target_component.value,
                    platform=platform
                ):
                    profile_key = _profile_key(
                        target_component,
                        platform
                    )
                    operational_key = _operational_key(profile_key)
                    path = self.resolver.resolve_operational(
                        operational_key
                    )
                    profile = self.resolver.load_operational(
                        operational_key
                    )
                    self.assertEqual(
                        self.resolver.resolve_operational(
                            operational_key
                        ),
                        path
                    )
                    self.assertFalse(
                        Path("config/profiles/diseno").exists()
                    )
                    self.assertEqual(
                        False,
                        bool(
                            profile.get(
                                "image_validation",
                                {}
                            ).get(
                                "enabled",
                                False
                            )
                        )
                    )
                    self.assertEqual(
                        expected["width"],
                        profile["video_style"]["width"]
                    )
                    self.assertEqual(
                        expected["height"],
                        profile["video_style"]["height"]
                    )

    def test_video_wan_profiles_keep_current_parameters(self):
        expected_by_platform = {
            "instagram": (
                (448, 800),
                (1080, 1920),
            ),
            "youtube": (
                (800, 448),
                (1920, 1080),
            ),
        }

        for platform, dimensions in expected_by_platform.items():
            with self.subTest(platform=platform):
                profile_key = OperationalProfileKey(
                    ProfileComponent.VIDEO,
                    platform,
                    f"video_{platform}",
                )
                path = self.resolver.resolve_video_component(
                    profile_key
                )
                profile = self.resolver.load_video_component(
                    profile_key
                )
                video = profile["video_component"]

                self.assertEqual(
                    Path("config/profiles/video")
                    / platform
                    / f"wan_i2v_{platform}.json",
                    path
                )
                self.assertEqual(
                    dimensions[0],
                    (
                        video["generation"]["width"],
                        video["generation"]["height"],
                    )
                )
                self.assertEqual(
                    dimensions[1],
                    (
                        video["target"]["width"],
                        video["target"]["height"],
                    )
                )
                self.assertEqual(49, video["frames"])
                self.assertEqual(12, video["fps"])
                self.assertEqual(20, video["sampling"]["steps"])
                self.assertEqual(5.0, video["sampling"]["cfg"])
                self.assertEqual(
                    "uni_pc",
                    video["sampling"]["sampler"]
                )
                self.assertEqual(
                    "simple",
                    video["sampling"]["scheduler"]
                )

    def test_official_subtitle_configuration_is_unified_and_equivalent(self):
        for platform, expected in self.PLATFORM_EXPECTATIONS.items():
            with self.subTest(platform=platform):
                profile_key = _profile_key(
                    ProfileComponent.VIDEO,
                    platform
                )
                environment = self._identity_environment(
                    profile_key
                )
                with patch.dict(
                    os.environ,
                    environment,
                    clear=True
                ):
                    subtitle_profile = (
                        ConfigManager()
                        .get_subtitle_profile_by_key(
                            _official_subtitle_key(profile_key)
                        )
                    )

                self.assertEqual(
                    expected["subtitle_config"],
                    subtitle_profile.cue_policy["mode"]
                )
                self.assertEqual(
                    expected["subtitle_config"],
                    subtitle_profile.cue_policy["mode"]
                )

    def test_structured_identity_controls_wan_profile_resolution(self):
        instagram_key = OperationalProfileKey(
            ProfileComponent.VIDEO,
            "instagram",
            "video_instagram",
        )

        self.assertEqual(
            self.resolver.load_video_component(instagram_key),
            load_video_component_parameters(
                instagram_key
            )
        )

    def test_wan_profile_rejects_legacy_platform_and_format_inference(self):
        for legacy_profile in (
            {
                "platform": "instagram"
            },
            {
                "format": "youtube"
            },
            {
                "video_component": {}
            },
        ):
            with self.subTest(
                legacy_profile=legacy_profile
            ), self.assertRaisesRegex(
                TypeError,
                "identidad operacional VIDEO explicito"
            ):
                load_video_component_parameters(
                    legacy_profile
                )

    def test_wan_profile_rejects_missing_or_incompatible_identity(self):
        with self.assertRaisesRegex(
            TypeError,
            "identidad operacional VIDEO explicito"
        ):
            load_video_component_parameters(
                None
            )

        image_key = OperationalProfileKey(
            ProfileComponent.IMAGEN,
            "instagram",
            "imagen_instagram",
        )
        with self.assertRaisesRegex(
            ValueError,
            "componente video"
        ):
            load_video_component_parameters(
                image_key
            )

    def test_runtime_objects_are_consistent_with_structured_identity(self):
        for platform, expected in self.PLATFORM_EXPECTATIONS.items():
            with self.subTest(platform=platform):
                profile_key = _profile_key(
                    ProfileComponent.VIDEO,
                    platform
                )

                with patch.dict(
                    os.environ,
                    self._identity_environment(profile_key),
                    clear=True
                ):
                    identity_profile = (
                        ConfigManager()
                        .get_profile_config()
                    )
                    subtitle_profile = (
                        ConfigManager().get_subtitle_profile_by_key(
                            _official_subtitle_key(profile_key)
                        )
                    )
                    identity_video = VideoConfigLoader(
                        subtitle_profile=subtitle_profile
                    ).load()

                self.assertEqual(
                    self.resolver.load_operational(
                        _operational_key(profile_key)
                    ),
                    identity_profile
                )
                self.assertEqual(
                    expected["width"],
                    identity_video.width
                )
                self.assertEqual(
                    expected["height"],
                    identity_video.height
                )
                self.assertEqual(
                    self.resolver.load_video_component(
                        _operational_key(profile_key)
                    ),
                    load_video_component_parameters(
                        _operational_key(profile_key)
                    )
                )

    def _identity_environment(
        self,
        profile_key
    ):
        return {
            "MC_PROFILE_COMPONENT": profile_key.component.value,
            "MC_PROFILE_PLATFORM": profile_key.platform,
            "MC_PROFILE_ID": profile_key.profile_id,
        }

    def _load(
        self,
        path
    ):
        return json.loads(
            Path(path).read_text(
                encoding="utf-8"
            )
        )

if __name__ == "__main__":
    unittest.main()
