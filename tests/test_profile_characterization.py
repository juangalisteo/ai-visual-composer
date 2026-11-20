import json
import unittest
from pathlib import Path

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
    (ProfileComponent.GUION, "vertical"): "guion_vertical",
    (ProfileComponent.GUION, "horizontal"): "guion_horizontal",
    (ProfileComponent.IMAGEN, "vertical"): "imagen_vertical",
    (ProfileComponent.IMAGEN, "horizontal"): "imagen_horizontal",
    (ProfileComponent.VIDEO, "vertical"): "video_vertical",
    (ProfileComponent.VIDEO, "horizontal"): "video_horizontal",
}

OFFICIAL_SUBTITLE_PROFILE_IDS = {
    (ProfileComponent.GUION, "vertical"): (
        "subtitulo_guion_vertical_palabra_por_palabra"
    ),
    (ProfileComponent.GUION, "horizontal"): "subtitulo_guion_horizontal_linea_unica",
    (ProfileComponent.IMAGEN, "vertical"): (
        "subtitulo_imagen_vertical_palabra_por_palabra"
    ),
    (ProfileComponent.IMAGEN, "horizontal"): "subtitulo_imagen_horizontal_linea_unica",
    (ProfileComponent.VIDEO, "vertical"): (
        "subtitulo_video_vertical_palabra_por_palabra"
    ),
    (ProfileComponent.VIDEO, "horizontal"): "subtitulo_video_horizontal_linea_unica",
}


def _profile_key(component, profile_format):
    return OperationalProfileKey(
        component,
        profile_format,
        OPERATIONAL_PROFILE_IDS[(component, profile_format)],
    )


def _official_subtitle_key(profile_key):
    return SubtitleProfileKey(
        profile_key.component,
        profile_key.format,
        OFFICIAL_SUBTITLE_PROFILE_IDS[
            (profile_key.component, profile_key.format)
        ],
        "estandar",
    )


def _operational_key(profile_key):
    return OperationalProfileKey(
        profile_key.component,
        profile_key.format,
        profile_key.profile_id,
    )


class ProfileCharacterizationTest(unittest.TestCase):

    RUNTIME_COMPONENTS = (
        ProfileComponent.GUION,
        ProfileComponent.IMAGEN,
        ProfileComponent.VIDEO,
    )

    FORMAT_EXPECTATIONS = {
        "vertical": {
            "format": "vertical",
            "width": 1080,
            "height": 1920,
            "fps": 30,
            "subtitle_config": "word_by_word",
            "subtitle_font": "unisans",
            "subtitle_size": 14,
            "subtitle_margin": 55,
            "subtitle_offset": -0.06,
        },
        "horizontal": {
            "format": "horizontal",
            "width": 1920,
            "height": 1080,
            "fps": 30,
            "subtitle_config": "single_line",
            "subtitle_font": "gotham",
            "subtitle_size": 16,
            "subtitle_margin": 25,
            "subtitle_offset": 0.0,
        },
    }

    def setUp(self):
        self.resolver = ProfileResolver()
        self.subtitle_resolver = SubtitleProfileResolver()

    def test_guion_image_and_video_profiles_keep_effective_behavior(self):
        for component in self.RUNTIME_COMPONENTS:
            for profile_format, expected in self.FORMAT_EXPECTATIONS.items():
                with self.subTest(
                    component=component.value,
                    profile_format=profile_format
                ):
                    profile_key = _profile_key(
                        component,
                        profile_format
                    )
                    profile = self.resolver.load_operational(
                        _operational_key(profile_key)
                    )
                    video_style = profile["video_style"]
                    subtitle_profile = (
                        self._config_manager(profile_key)
                        .get_subtitle_profile_by_key(
                            _official_subtitle_key(profile_key)
                        )
                    )
                    subtitles = subtitle_profile.render_style

                    self.assertEqual(
                        profile_format,
                        profile["format"]
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
                    # The scene duration belongs to the format
                    # (config/formats.json), not to the profile.
                    self.assertNotIn("storyboard", video_style)
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
            for profile_format, expected in self.FORMAT_EXPECTATIONS.items():
                with self.subTest(
                    target=target_component.value,
                    profile_format=profile_format
                ):
                    profile_key = _profile_key(
                        target_component,
                        profile_format
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
                        expected["width"],
                        profile["video_style"]["width"]
                    )
                    self.assertEqual(
                        expected["height"],
                        profile["video_style"]["height"]
                    )

    def test_video_wan_profiles_keep_current_parameters(self):
        expected_by_format = {
            "vertical": (448, 800),
            "horizontal": (800, 448),
        }

        for profile_format, dimensions in expected_by_format.items():
            with self.subTest(profile_format=profile_format):
                profile_key = OperationalProfileKey(
                    ProfileComponent.VIDEO,
                    profile_format,
                    f"video_{profile_format}",
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
                    / profile_format
                    / f"wan_i2v_{profile_format}.json",
                    path
                )
                self.assertEqual(
                    dimensions,
                    (
                        video["generation"]["width"],
                        video["generation"]["height"],
                    )
                )
                self.assertEqual(81, video["frames"])
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
        for profile_format, expected in self.FORMAT_EXPECTATIONS.items():
            with self.subTest(profile_format=profile_format):
                profile_key = _profile_key(
                    ProfileComponent.VIDEO,
                    profile_format
                )
                subtitle_profile = (
                    self._config_manager(profile_key)
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
        vertical_key = OperationalProfileKey(
            ProfileComponent.VIDEO,
            "vertical",
            "video_vertical",
        )

        self.assertEqual(
            self.resolver.load_video_component(vertical_key),
            load_video_component_parameters(
                vertical_key
            )
        )

    def test_wan_profile_rejects_legacy_platform_and_format_inference(self):
        video_formats = self.resolver.discover_formats(
            ProfileComponent.VIDEO
        )
        self.assertTrue(video_formats)
        legacy_profiles = [
            {
                "video_component": {}
            },
        ]
        for video_format in video_formats:
            legacy_profiles.extend((
                {
                    "platform": video_format
                },
                {
                    "format": video_format
                },
            ))

        for legacy_profile in legacy_profiles:
            with self.subTest(
                legacy_profile=legacy_profile
            ), self.assertRaisesRegex(
                TypeError,
                "identidad operacional VIDEO explícita"
            ):
                load_video_component_parameters(
                    legacy_profile
                )

    def test_wan_profile_rejects_missing_or_incompatible_identity(self):
        with self.assertRaisesRegex(
            TypeError,
            "identidad operacional VIDEO explícita"
        ):
            load_video_component_parameters(
                None
            )

        image_key = OperationalProfileKey(
            ProfileComponent.IMAGEN,
            "vertical",
            "imagen_vertical",
        )
        with self.assertRaisesRegex(
            ValueError,
            "componente video"
        ):
            load_video_component_parameters(
                image_key
            )

    def test_runtime_objects_are_consistent_with_structured_identity(self):
        for profile_format, expected in self.FORMAT_EXPECTATIONS.items():
            with self.subTest(profile_format=profile_format):
                profile_key = _profile_key(
                    ProfileComponent.VIDEO,
                    profile_format
                )

                config = self._config_manager(profile_key)
                identity_profile = config.get_profile_config()
                subtitle_profile = config.get_subtitle_profile_by_key(
                    _official_subtitle_key(profile_key)
                )
                identity_video = VideoConfigLoader(
                    subtitle_profile=subtitle_profile,
                    config_manager=config,
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

    def _config_manager(
        self,
        profile_key
    ):
        return ConfigManager(
            operational_profile_key=_operational_key(profile_key)
        )

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
