import unittest
from copy import deepcopy
from types import SimpleNamespace

from app.core.start import _required_builders
from app.modules.images.image_builder import ImageBuilder
from app.modules.storyboard.storyboard_builder import StoryboardBuilder
from app.modules.subtitles.models.single_line_model import SingleLineModel
from app.modules.subtitles.models.word_by_word_model import WordByWordModel
from app.modules.subtitles.srt_optimizer import SrtOptimizer
from app.modules.video.config.loaders.overlay_loader import OverlayConfigLoader
from app.modules.video.config.loaders.subtitle_loader import SubtitleConfigLoader
from app.modules.video.config.loaders.visual_effect_loader import (
    VisualEffectConfigLoader,
)
from app.modules.video.video_config import VideoConfigLoader
from app.shared.profile_identity import (
    ProfileComponent,
    ProfileKey,
    ProfilePlatform,
)
from app.shared.profile_resolver import ProfileResolver
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


class RequiredProfileContractsTest(unittest.TestCase):

    RUNTIME_COMPONENTS = (
        ProfileComponent.GUION,
        ProfileComponent.IMAGEN,
        ProfileComponent.VIDEO,
    )

    EXPECTED = {
        ProfilePlatform.INSTAGRAM: {
            "format": "vertical",
            "width": 1080,
            "height": 1920,
            "fps": 30,
            "seconds_per_image": 20.0,
            "codec": "libx264",
            "preset": "slow",
            "crf": 16,
            "pixel_format": "yuv420p",
            "movflags": "+faststart",
            "audio_codec": "aac",
            "audio_bitrate": "192k",
        },
        ProfilePlatform.YOUTUBE: {
            "format": "horizontal",
            "width": 1920,
            "height": 1080,
            "fps": 30,
            "seconds_per_image": 30.0,
            "codec": "libx264",
            "preset": "slow",
            "crf": 16,
            "pixel_format": "yuv420p",
            "movflags": "+faststart",
            "audio_codec": "aac",
            "audio_bitrate": "192k",
        },
    }

    def setUp(self):
        self.profile_resolver = ProfileResolver()
        self.subtitle_resolver = SubtitleProfileResolver()

    def test_official_profiles_preserve_effective_configuration(self):
        for component in self.RUNTIME_COMPONENTS:
            for platform, expected in self.EXPECTED.items():
                with self.subTest(
                    component=component.value,
                    platform=platform.value,
                ):
                    profile_key, profile = self._profile(
                        component,
                        platform,
                    )
                    video_config = self._video_config(
                        profile_key,
                        profile,
                    )

                    self.assertEqual(expected["format"], profile["format"])
                    self.assertFalse(profile["image_validation"]["enabled"])
                    self.assertEqual(profile["builders"], _required_builders(profile))
                    self.assertEqual(expected["width"], video_config.width)
                    self.assertEqual(expected["height"], video_config.height)
                    self.assertEqual(expected["fps"], video_config.fps)
                    self.assertEqual(expected["codec"], video_config.codec)
                    self.assertEqual(expected["preset"], video_config.preset)
                    self.assertEqual(expected["crf"], video_config.crf)
                    self.assertEqual(
                        expected["pixel_format"],
                        video_config.pixel_format,
                    )
                    self.assertEqual(expected["movflags"], video_config.movflags)
                    self.assertEqual(
                        expected["audio_codec"],
                        video_config.audio_codec,
                    )
                    self.assertEqual(
                        expected["audio_bitrate"],
                        video_config.audio_bitrate,
                    )
                    self.assertEqual(
                        expected["seconds_per_image"],
                        StoryboardBuilder.__new__(StoryboardBuilder)
                        ._resolve_scene_duration(profile, None),
                    )

    def test_video_loader_rejects_every_missing_critical_key(self):
        profile_key, profile = self._profile(
            ProfileComponent.VIDEO,
            ProfilePlatform.INSTAGRAM,
        )
        critical_paths = (
            ("video_style", "width"),
            ("video_style", "height"),
            ("video_style", "fps"),
            ("video", "codec"),
            ("video", "preset"),
            ("video", "crf"),
            ("video", "pixel_format"),
            ("video", "movflags"),
            ("audio", "codec"),
            ("audio", "bitrate"),
            ("validation", "max_duration_difference"),
        )

        for section, key in critical_paths:
            with self.subTest(path=f"{section}.{key}"):
                incomplete = deepcopy(profile)
                del incomplete[section][key]
                with self.assertRaisesRegex(
                    ValueError,
                    f"{section}.{key}",
                ):
                    self._video_config(profile_key, incomplete)

    def test_visual_loaders_reject_missing_critical_keys(self):
        profile_key, profile = self._profile(
            ProfileComponent.VIDEO,
            ProfilePlatform.INSTAGRAM,
        )
        critical_paths = {
            "motion": (
                "enabled",
                "internal_scale",
                "base_zoom",
                "zoom_amount",
                "pan_zoom_enabled",
                "pan_zoom_start",
                "selection",
                "avoid_repeats",
                "types",
                "weights",
            ),
            "transitions": (
                "enabled",
                "duration",
                "selection",
                "avoid_repeats",
                "types",
                "weights",
            ),
            "fade": (
                "enabled",
                "fade_in",
                "fade_out",
                "duration",
            ),
        }

        for section, keys in critical_paths.items():
            for key in keys:
                with self.subTest(path=f"video_style.{section}.{key}"):
                    incomplete = deepcopy(profile)
                    del incomplete["video_style"][section][key]
                    with self.assertRaisesRegex(
                        ValueError,
                        f"video_style.{section}.{key}",
                    ):
                        self._video_config(profile_key, incomplete)

    def test_image_storyboard_and_builder_contracts_fail_fast(self):
        _, profile = self._profile(
            ProfileComponent.IMAGEN,
            ProfilePlatform.INSTAGRAM,
        )
        builder = ImageBuilder.__new__(ImageBuilder)
        storyboard = StoryboardBuilder.__new__(StoryboardBuilder)

        without_format = deepcopy(profile)
        del without_format["format"]
        with self.assertRaisesRegex(ValueError, "format"):
            builder._profile_format_guidance(without_format)

        without_validation = deepcopy(profile)
        del without_validation["image_validation"]["enabled"]
        with self.assertRaisesRegex(ValueError, "image_validation.enabled"):
            builder._is_image_validation_enabled(without_validation)

        without_duration = deepcopy(profile)
        del without_duration["video_style"]["storyboard"][
            "seconds_per_image"
        ]
        with self.assertRaisesRegex(ValueError, "seconds_per_image"):
            storyboard._resolve_scene_duration(without_duration, None)

        for key in tuple(profile["builders"]):
            with self.subTest(path=f"builders.{key}"):
                incomplete = deepcopy(profile)
                del incomplete["builders"][key]
                with self.assertRaisesRegex(ValueError, f"builders.{key}"):
                    _required_builders(incomplete)

    def test_subtitle_render_style_rejects_missing_critical_keys(self):
        profile_key, profile = self._profile(
            ProfileComponent.VIDEO,
            ProfilePlatform.INSTAGRAM,
        )
        subtitle = self._subtitle_profile(profile_key, profile)

        for key in tuple(subtitle.render_style):
            with self.subTest(path=f"render_style.{key}"):
                incomplete = deepcopy(subtitle.render_style)
                del incomplete[key]
                with self.assertRaisesRegex(
                    ValueError,
                    f"render_style.{key}",
                ):
                    SubtitleConfigLoader().load_render_style(incomplete)

    def test_subtitle_cue_policy_rejects_missing_critical_keys(self):
        for style in ("single_line", "word_by_word"):
            with self.subTest(style=style):
                profile_key = ProfileKey.for_component(
                    ProfileComponent.VIDEO,
                    ProfilePlatform.INSTAGRAM,
                )
                subtitle_key = SubtitleProfileKey.for_profile(
                    profile_key,
                    style,
                )
                cue_policy = deepcopy(
                    self.subtitle_resolver.load(subtitle_key).cue_policy
                )
                cue_policy["render_fps"] = 30

                model_type = (
                    SingleLineModel
                    if style == "single_line"
                    else WordByWordModel
                )
                required_keys = (
                    "max_chars_per_line",
                    "min_duration",
                    "max_duration",
                    "significant_gap_threshold",
                ) if style == "single_line" else (
                    "min_duration",
                    "max_duration",
                    "uppercase",
                    "punctuation",
                    "significant_gap_threshold",
                    "render_fps",
                    "micro_cues",
                )

                for key in required_keys:
                    with self.subTest(style=style, path=f"cue_policy.{key}"):
                        incomplete = deepcopy(cue_policy)
                        del incomplete[key]
                        with self.assertRaisesRegex(
                            ValueError,
                            f"cue_policy.{key}",
                        ):
                            model_type(incomplete)

                for key in tuple(cue_policy["punctuation"]):
                    with self.subTest(
                        style=style,
                        path=f"cue_policy.punctuation.{key}",
                    ):
                        incomplete = deepcopy(cue_policy)
                        del incomplete["punctuation"][key]
                        with self.assertRaisesRegex(
                            ValueError,
                            f"cue_policy.punctuation.{key}",
                        ):
                            model_type(incomplete)

                if style == "word_by_word":
                    for key in tuple(cue_policy["micro_cues"]):
                        with self.subTest(
                            style=style,
                            path=f"cue_policy.micro_cues.{key}",
                        ):
                            incomplete = deepcopy(cue_policy)
                            del incomplete["micro_cues"][key]
                            with self.assertRaisesRegex(
                                ValueError,
                                f"cue_policy.micro_cues.{key}",
                            ):
                                model_type(incomplete)

                without_mode = deepcopy(cue_policy)
                del without_mode["mode"]
                with self.assertRaisesRegex(ValueError, "cue_policy.mode"):
                    SrtOptimizer(
                        subtitle_profile=SimpleNamespace(
                            cue_policy=without_mode,
                        ),
                        render_fps=30,
                    )

    def test_absent_optional_layers_remain_safely_disabled(self):
        overlay = OverlayConfigLoader().load({})
        visual_effect = VisualEffectConfigLoader().load({})

        self.assertFalse(overlay.enabled)
        self.assertFalse(visual_effect.enabled)
        self.assertEqual("overlay", visual_effect.mode)

        _, profile = self._profile(
            ProfileComponent.VIDEO,
            ProfilePlatform.INSTAGRAM,
        )
        self.assertEqual(
            7.5,
            StoryboardBuilder.__new__(StoryboardBuilder)
            ._resolve_scene_duration(profile, 7.5),
        )

    def _profile(self, component, platform):
        key = ProfileKey.for_component(component, platform)
        return key, self.profile_resolver.load(key)

    def _subtitle_profile(self, profile_key, profile):
        subtitle_key = SubtitleProfileKey.for_profile(
            profile_key,
            profile["subtitle_config"],
        )
        return self.subtitle_resolver.load(subtitle_key)

    def _video_config(self, profile_key, profile):
        subtitle_profile = self._subtitle_profile(profile_key, profile)
        manager = SimpleNamespace(
            get_profile_config=lambda: deepcopy(profile),
        )
        return VideoConfigLoader(
            subtitle_profile=subtitle_profile,
            config_manager=manager,
        ).load()


if __name__ == "__main__":
    unittest.main()
