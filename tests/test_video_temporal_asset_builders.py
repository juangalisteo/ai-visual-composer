from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import tempfile
import unittest

from app.modules.video.overlays.overlay_builder import OverlayBuilder
from app.modules.video.visual_effects.visual_effect_builder import (
    VisualEffectBuilder
)


class FakeSelector:

    def __init__(
        self,
        *paths
    ):
        self.paths = list(
            paths
        )
        self.calls = 0

    def select(
        self,
        scene_index,
        scene_count,
        scene_metadata=None
    ):
        self.calls += 1

        return self.paths[
            min(
                self.calls - 1,
                len(self.paths) - 1
            )
        ]


def builder_config(
    enabled=True,
    probability=1.0,
    min_seconds=1.5,
    max_seconds=3.5,
    repeat_mode="loop",
    loop_file=True,
    opacity=0.65,
    blend_mode="screen",
    mode="blend"
):
    return SimpleNamespace(
        enabled=enabled,
        probability=probability,
        min_seconds=min_seconds,
        max_seconds=max_seconds,
        repeat_mode=repeat_mode,
        loop_file=loop_file,
        opacity=opacity,
        blend_mode=blend_mode,
        mode=mode,
        directory="unused",
        folders=(),
        types=(),
        extensions=(".mov",),
        folder_selection="sequence",
        file_selection="sequence",
        avoid_repeats=True,
        folder_weights={},
        file_weights={}
    )


class TemporalAssetBuilderTest(
    unittest.TestCase
):

    def test_overlay_disabled_returns_empty_selection(
        self
    ):
        path = Path("overlay.mov")
        selector = FakeSelector(
            path
        )
        builder = OverlayBuilder(
            builder_config(
                enabled=False
            )
        )
        builder.selector = selector

        self.assertEqual(
            builder.build(
                scene_index=0,
                scene_count=1
            ),
            {
                "inputs": [],
                "overlay": None,
                "overlay_path": None
            }
        )
        self.assertEqual(
            selector.calls,
            0
        )

    def test_visual_effect_probability_zero_returns_empty_selection(
        self
    ):
        path = Path("effect.mov")
        selector = FakeSelector(
            path
        )
        builder = VisualEffectBuilder(
            builder_config(
                probability=0.0
            )
        )
        builder.selector = selector

        with patch(
            "app.modules.video.assets.temporal_asset_builder.random.random",
            return_value=1.0
        ):
            result = builder.build(
                scene_index=0,
                scene_count=1
            )

        self.assertEqual(
            result,
            {
                "inputs": [],
                "effect": None,
                "effect_path": None
            }
        )
        self.assertEqual(
            selector.calls,
            0
        )

    def test_overlay_probability_one_generates_selection_with_current_contract(
        self
    ):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "overlay.mov"
            path.touch()

            builder = OverlayBuilder(
                builder_config()
            )
            builder.selector = FakeSelector(
                path
            )

            with patch(
                "app.modules.video.assets.temporal_asset_builder.random.random",
                return_value=0.0
            ), patch(
                "app.modules.video.assets.temporal_asset_builder.random.uniform",
                return_value=2.5
            ):
                result = builder.build(
                    scene_index=0,
                    scene_count=1
                )

            self.assertEqual(
                result,
                {
                    "inputs": [
                        path.resolve()
                    ],
                    "overlay": "overlay.mov",
                    "overlay_path": path.resolve(),
                    "input_position": 0,
                    "repeat_mode": "loop",
                    "duration": 2.5,
                    "loop_file": True,
                    "opacity": 0.65,
                    "blend_mode": "screen",
                    "probability": 1.0
                }
            )
            self.assertNotIn(
                "mode",
                result
            )

    def test_visual_effect_preserves_mode_and_current_contract(
        self
    ):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "effect.mov"
            path.touch()

            builder = VisualEffectBuilder(
                builder_config(
                    mode="overlay"
                )
            )
            builder.selector = FakeSelector(
                path
            )

            with patch(
                "app.modules.video.assets.temporal_asset_builder.random.random",
                return_value=0.0
            ), patch(
                "app.modules.video.assets.temporal_asset_builder.random.uniform",
                return_value=2.5
            ):
                result = builder.build(
                    scene_index=0,
                    scene_count=1
                )

            self.assertEqual(
                result,
                {
                    "inputs": [
                        path.resolve()
                    ],
                    "effect": "effect.mov",
                    "effect_path": path.resolve(),
                    "input_position": 0,
                    "mode": "overlay",
                    "repeat_mode": "loop",
                    "duration": 2.5,
                    "loop_file": True,
                    "opacity": 0.65,
                    "blend_mode": "screen",
                    "probability": 1.0
                }
            )

    def test_reuses_input_position_for_same_file(
        self
    ):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "same.mov"
            path.touch()

            builder = OverlayBuilder(
                builder_config()
            )
            builder.selector = FakeSelector(
                path,
                path
            )

            with patch(
                "app.modules.video.assets.temporal_asset_builder.random.random",
                return_value=0.0
            ), patch(
                "app.modules.video.assets.temporal_asset_builder.random.uniform",
                return_value=2.5
            ):
                first = builder.build(
                    scene_index=0,
                    scene_count=2
                )
                second = builder.build(
                    scene_index=1,
                    scene_count=2
                )

            self.assertEqual(
                first["input_position"],
                0
            )
            self.assertEqual(
                second["input_position"],
                0
            )
            self.assertEqual(
                builder.inputs,
                (
                    path.resolve(),
                )
            )

    def test_overlay_builder_reset_clears_category_distribution_state(
        self
    ):
        builder = OverlayBuilder(
            builder_config()
        )
        builder.selector.category_distribution_policy.previous_category = (
            "Electricity"
        )

        builder.reset()

        self.assertIsNone(
            builder
            .selector
            .category_distribution_policy
            .previous_category
        )

    def test_duration_is_within_configured_bounds(
        self
    ):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "duration.mov"
            path.touch()

            config = builder_config(
                min_seconds=1.0,
                max_seconds=1.1
            )
            builder = VisualEffectBuilder(
                config
            )
            builder.selector = FakeSelector(
                path
            )

            with patch(
                "app.modules.video.assets.temporal_asset_builder.random.random",
                return_value=0.0
            ):
                result = builder.build(
                    scene_index=0,
                    scene_count=1
                )

            self.assertGreaterEqual(
                result["duration"],
                config.min_seconds
            )
            self.assertLessEqual(
                result["duration"],
                config.max_seconds
            )


if __name__ == "__main__":
    unittest.main()
