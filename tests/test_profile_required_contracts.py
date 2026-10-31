import unittest
from copy import deepcopy
from types import SimpleNamespace

from app.modules.standard.execution_coordinator import _required_builders
from app.modules.images.image_builder import ImageBuilder
from app.modules.storyboard.storyboard_builder import StoryboardBuilder
from app.modules.subtitles.modes.single_line import SingleLineModel
from app.modules.subtitles.modes.word_by_word import WordByWordModel
from app.modules.subtitles.pipeline.srt_optimizer import SrtOptimizer
from app.modules.video.config.loaders.overlay_loader import OverlayConfigLoader
from app.modules.video.config.loaders.subtitle_loader import SubtitleConfigLoader
from app.modules.video.config.loaders.visual_effect_loader import (
    VisualEffectConfigLoader,
)
from app.modules.video.video_config import VideoConfigLoader
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

WORD_BY_WORD_SUBTITLE_PROFILE_IDS = {
    (ProfileComponent.GUION, "vertical"): (
        "subtitulo_guion_vertical_palabra_por_palabra"
    ),
    (ProfileComponent.GUION, "horizontal"): (
        "subtitulo_guion_horizontal_palabra_por_palabra"
    ),
    (ProfileComponent.IMAGEN, "vertical"): (
        "subtitulo_imagen_vertical_palabra_por_palabra"
    ),
    (ProfileComponent.IMAGEN, "horizontal"): (
        "subtitulo_imagen_horizontal_palabra_por_palabra"
    ),
    (ProfileComponent.VIDEO, "vertical"): (
        "subtitulo_video_vertical_palabra_por_palabra"
    ),
    (ProfileComponent.VIDEO, "horizontal"): (
        "subtitulo_video_horizontal_palabra_por_palabra"
    ),
}


class RequiredProfileContractsTest(unittest.TestCase):

    RUNTIME_COMPONENTS = (
        ProfileComponent.GUION,
        ProfileComponent.IMAGEN,
        ProfileComponent.VIDEO,
    )

    EXPECTED = {
        "vertical": {
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
        "horizontal": {
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
            for profile_format, expected in self.EXPECTED.items():
                with self.subTest(
                    component=component.value,
                    profile_format=profile_format,
                ):
                    profile_key, profile = self._profile(
                        component,
                        profile_format,
                    )
                    video_config = self._video_config(
                        profile_key,
                        profile,
                    )

                    self.assertEqual(expected["format"], profile["format"])
                    self.assertNotIn("image_validation", profile)
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
            "vertical",
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
            "vertical",
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
            "vertical",
        )
        builder = ImageBuilder.__new__(ImageBuilder)
        storyboard = StoryboardBuilder.__new__(StoryboardBuilder)

        without_format = deepcopy(profile)
        del without_format["format"]
        with self.assertRaisesRegex(ValueError, "format"):
            builder._profile_format_guidance(without_format)

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
            "vertical",
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
        for style, subtitle_profile_id in (
            ("single_line", "subtitulo_video_vertical_linea_unica"),
            ("word_by_word", "subtitulo_video_vertical_palabra_por_palabra"),
        ):
            with self.subTest(style=style):
                subtitle_key = SubtitleProfileKey(
                    ProfileComponent.VIDEO,
                    "vertical",
                    subtitle_profile_id,
                    "estandar",
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
            "vertical",
        )
        self.assertEqual(
            7.5,
            StoryboardBuilder.__new__(StoryboardBuilder)
            ._resolve_scene_duration(profile, 7.5),
        )

    def _profile(self, component, profile_format):
        key = OperationalProfileKey(
            component,
            profile_format,
            OPERATIONAL_PROFILE_IDS[(component, profile_format)],
        )
        return key, self.profile_resolver.load_operational(key)

    def _subtitle_profile(self, profile_key, profile):
        del profile
        return self.subtitle_resolver.load(
            SubtitleProfileKey(
                profile_key.component,
                profile_key.format,
                WORD_BY_WORD_SUBTITLE_PROFILE_IDS[
                    (profile_key.component, profile_key.format)
                ],
                "estandar",
            )
        )

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
