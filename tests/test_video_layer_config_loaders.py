import json
from dataclasses import fields
from pathlib import Path
import unittest

from app.modules.video.config.loaders.overlay_loader import (
    OverlayConfigLoader
)
from app.modules.video.config.loaders.visual_effect_loader import (
    VisualEffectConfigLoader
)
from app.modules.video.config.overlay_config import OverlayConfig
from app.modules.video.config.visual_effect_config import (
    VisualEffectConfig
)


def profile(
    overlays=None,
    visual_effects=None
):
    video_style = {}

    if overlays is not None:
        video_style["overlays"] = overlays

    if visual_effects is not None:
        video_style["visual_effects"] = visual_effects

    return {
        "video_style": video_style
    }


class LayerConfigLoaderTest(
    unittest.TestCase
):

    def test_overlay_loader_preserves_defaults_and_contract(
        self
    ):
        config = OverlayConfigLoader().load(
            profile(
                overlays={}
            )
        )

        self.assertIsInstance(
            config,
            OverlayConfig
        )
        self.assertEqual(
            config.enabled,
            False
        )
        self.assertEqual(
            config.directory,
            "assets/videos/overlays"
        )
        self.assertEqual(
            config.folder_selection,
            "random"
        )
        self.assertEqual(
            config.file_selection,
            "random"
        )
        self.assertEqual(
            config.repeat_mode,
            "interval"
        )
        self.assertEqual(
            config.min_seconds,
            6.0
        )
        self.assertEqual(
            config.max_seconds,
            12.0
        )
        self.assertEqual(
            config.extensions,
            (
                ".mov",
                ".mp4"
            )
        )

    def test_visual_effect_loader_preserves_defaults_and_contract(
        self
    ):
        config = VisualEffectConfigLoader().load(
            profile(
                visual_effects={}
            )
        )

        self.assertIsInstance(
            config,
            VisualEffectConfig
        )
        self.assertEqual(
            config.enabled,
            False
        )
        self.assertEqual(
            config.directory,
            "assets/videos/visual_effects"
        )
        self.assertEqual(
            config.mode,
            "overlay"
        )
        self.assertEqual(
            config.folder_selection,
            "random"
        )
        self.assertEqual(
            config.file_selection,
            "random"
        )
        self.assertEqual(
            config.file_weights,
            {}
        )

    def test_overlay_legacy_selection_and_weights_are_rejected(
        self
    ):
        for legacy_data in (
            {
                "selection": "sequence"
            },
            {
                "weights": {
                    "spark.mov": 2
                }
            },
        ):
            with self.subTest(
                legacy_data=legacy_data
            ), self.assertRaisesRegex(
                ValueError,
                "no admite las claves legacy selection/weights"
            ):
                OverlayConfigLoader().load(
                    profile(
                        overlays=legacy_data
                    )
                )

    def test_visual_effect_legacy_selection_and_weights_remain_ignored(
        self
    ):
        config = VisualEffectConfigLoader().load(
            profile(
                visual_effects={
                    "selection": "sequence",
                    "weights": {
                        "light.mov": 2
                    }
                }
            )
        )

        self.assertEqual(
            config.folder_selection,
            "random"
        )
        self.assertEqual(
            config.file_selection,
            "random"
        )
        self.assertEqual(
            config.file_weights,
            {}
        )

    def test_validation_errors_are_preserved(
        self
    ):
        with self.assertRaisesRegex(
            ValueError,
            "modo de efecto visual"
        ):
            VisualEffectConfigLoader().load(
                profile(
                    visual_effects={
                        "mode": "invalid"
                    }
                )
            )

        with self.assertRaisesRegex(
            ValueError,
            "opacidad"
        ):
            OverlayConfigLoader().load(
                profile(
                    overlays={
                        "opacity": 2
                    }
                )
            )

    def test_section_type_validation_is_preserved(
        self
    ):
        with self.assertRaisesRegex(
            TypeError,
            "video_style.overlays"
        ):
            OverlayConfigLoader().load(
                profile(
                    overlays=[]
                )
            )

        with self.assertRaisesRegex(
            TypeError,
            "video_style.visual_effects"
        ):
            VisualEffectConfigLoader().load(
                profile(
                    visual_effects=[]
                )
            )

    def test_config_field_contracts_are_preserved(
        self
    ):
        self.assertEqual(
            tuple(
                field.name
                for field in fields(
                    OverlayConfig
                )
            ),
            (
                "enabled",
                "directory",
                "folder_selection",
                "file_selection",
                "avoid_repeats",
                "repeat_mode",
                "min_seconds",
                "max_seconds",
                "loop_file",
                "opacity",
                "blend_mode",
                "probability",
                "folders",
                "types",
                "extensions",
                "folder_weights",
                "file_weights"
            )
        )

        self.assertEqual(
            tuple(
                field.name
                for field in fields(
                    VisualEffectConfig
                )
            ),
            (
                "enabled",
                "directory",
                "mode",
                "folder_selection",
                "file_selection",
                "avoid_repeats",
                "repeat_mode",
                "min_seconds",
                "max_seconds",
                "loop_file",
                "opacity",
                "blend_mode",
                "probability",
                "folders",
                "types",
                "extensions",
                "folder_weights",
                "file_weights"
            )
        )

    def test_current_profiles_remain_compatible(
        self
    ):
        profile_paths = sorted(
            path
            for component in ("guion", "imagen", "video")
            for path in Path(
                "config/profiles"
            ).glob(
                f"{component}/*/perfil_*.json"
            )
        )

        self.assertEqual(
            6,
            len(profile_paths)
        )

        for profile_path in profile_paths:
            with self.subTest(
                profile_path=profile_path
            ):
                data = json.loads(
                    profile_path.read_text(
                        encoding="utf-8-sig"
                    )
                )

                overlay_config = (
                    OverlayConfigLoader().load(
                        data
                    )
                )
                visual_effect_config = (
                    VisualEffectConfigLoader().load(
                        data
                    )
                )

                self.assertIsInstance(
                    overlay_config,
                    OverlayConfig
                )
                self.assertIsInstance(
                    visual_effect_config,
                    VisualEffectConfig
                )
                self.assertNotIn(
                    "selection",
                    data["video_style"]["overlays"]
                )
                self.assertNotIn(
                    "weights",
                    data["video_style"]["overlays"]
                )
                self.assertEqual(
                    "random",
                    overlay_config.folder_selection
                )
                self.assertEqual(
                    "random",
                    overlay_config.file_selection
                )
                self.assertTrue(
                    overlay_config.avoid_repeats
                )
                self.assertEqual(
                    "scene",
                    overlay_config.repeat_mode
                )
                self.assertEqual(
                    0.15,
                    overlay_config.opacity
                )
                self.assertEqual(
                    "screen",
                    overlay_config.blend_mode
                )
                self.assertEqual(
                    {},
                    overlay_config.folder_weights
                )
                self.assertEqual(
                    {},
                    overlay_config.file_weights
                )


if __name__ == "__main__":
    unittest.main()
