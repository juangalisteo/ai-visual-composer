import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.start import _load_video_component_profile
from app.modules.video.video_config import VideoConfigLoader
from app.shared.config_manager import ConfigManager
from app.shared.profile_identity import (
    ProfileComponent,
    ProfileKey,
    ProfilePlatform,
)
from app.shared.profile_resolver import ProfileResolver


class ProfileCharacterizationTest(unittest.TestCase):

    PLATFORM_EXPECTATIONS = {
        ProfilePlatform.INSTAGRAM: {
            "format": "vertical",
            "resolution": "1080x1920",
            "width": 1080,
            "height": 1920,
            "fps": 30,
            "subtitle_config": "word_by_word",
            "subtitle_font": "unisans",
            "subtitle_size": 14,
            "subtitle_margin": 55,
            "subtitle_offset": -0.06,
            "seconds_per_image": 10,
        },
        ProfilePlatform.YOUTUBE: {
            "format": "horizontal",
            "resolution": "1920x1080",
            "width": 1920,
            "height": 1080,
            "fps": 30,
            "subtitle_config": "single_line",
            "subtitle_font": "gotham",
            "subtitle_size": 16,
            "subtitle_margin": 25,
            "subtitle_offset": 0.0,
            "seconds_per_image": 15,
        },
    }

    def setUp(self):
        self.resolver = ProfileResolver()

    def test_guion_image_and_video_profiles_keep_effective_behavior(self):
        for component in ProfileComponent:
            for platform, expected in self.PLATFORM_EXPECTATIONS.items():
                with self.subTest(
                    component=component.value,
                    platform=platform.value
                ):
                    profile_key = ProfileKey.for_component(
                        component,
                        platform
                    )
                    profile = self.resolver.load(
                        profile_key
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
                            ConfigManager().get_subtitle_profile(
                                expected["subtitle_config"]
                            )
                        )
                    subtitles = subtitle_profile.render_style

                    self.assertEqual(
                        platform.value,
                        profile["platform"]
                    )
                    self.assertEqual(
                        expected["format"],
                        profile["format"]
                    )
                    self.assertEqual(
                        expected["resolution"],
                        profile["resolution"]
                    )
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
                    self.assertEqual(
                        expected["subtitle_config"],
                        profile["subtitle_config"]
                    )
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
                    platform=platform.value
                ):
                    profile_key = ProfileKey.for_component(
                        target_component,
                        platform
                    )
                    path = self.resolver.resolve(
                        profile_key
                    )
                    profile = self.resolver.load(
                        profile_key
                    )
                    self.assertEqual(
                        self.resolver.resolve(
                            profile_key
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
            ProfilePlatform.INSTAGRAM: (
                (448, 800),
                (1080, 1920),
            ),
            ProfilePlatform.YOUTUBE: (
                (800, 448),
                (1920, 1080),
            ),
        }

        for platform, dimensions in expected_by_platform.items():
            with self.subTest(platform=platform.value):
                profile_key = ProfileKey.for_component(
                    ProfileComponent.VIDEO,
                    platform
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
                    / platform.value
                    / f"wan_i2v_{platform.value}.json",
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
            with self.subTest(platform=platform.value):
                profile_key = ProfileKey.for_component(
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
                        .get_subtitle_profile(
                            expected["subtitle_config"]
                        )
                    )

                self.assertEqual(
                    expected["subtitle_config"],
                    subtitle_profile.cue_policy["mode"]
                )
                self.assertEqual(
                    expected["subtitle_config"],
                    subtitle_profile.key.style.value
                )

    def test_structured_identity_controls_wan_profile_resolution(self):
        instagram_key = ProfileKey.for_component(
            ProfileComponent.VIDEO,
            ProfilePlatform.INSTAGRAM
        )

        self.assertEqual(
            self.resolver.load_video_component(instagram_key),
            _load_video_component_profile(
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
                "ProfileKey VIDEO explicito"
            ):
                _load_video_component_profile(
                    legacy_profile
                )

    def test_wan_profile_rejects_missing_or_incompatible_identity(self):
        with self.assertRaisesRegex(
            TypeError,
            "ProfileKey VIDEO explicito"
        ):
            _load_video_component_profile(
                None
            )

        image_key = ProfileKey.for_component(
            ProfileComponent.IMAGEN,
            ProfilePlatform.INSTAGRAM
        )
        with self.assertRaisesRegex(
            ValueError,
            "componente video"
        ):
            _load_video_component_profile(
                image_key
            )

    def test_runtime_objects_are_consistent_with_structured_identity(self):
        for platform, expected in self.PLATFORM_EXPECTATIONS.items():
            with self.subTest(platform=platform.value):
                profile_key = ProfileKey.for_component(
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
                        ConfigManager()
                        .get_subtitle_profile(
                            identity_profile["subtitle_config"]
                        )
                    )
                    identity_video = VideoConfigLoader(
                        subtitle_profile=subtitle_profile
                    ).load()

                self.assertEqual(
                    self.resolver.load(profile_key),
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
                    self.resolver.load_video_component(profile_key),
                    _load_video_component_profile(
                        profile_key
                    )
                )

    def _identity_environment(
        self,
        profile_key
    ):
        return {
            "MC_PROFILE_COMPONENT": profile_key.component.value,
            "MC_PROFILE_PLATFORM": profile_key.platform.value,
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
