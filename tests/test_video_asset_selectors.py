from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import tempfile
import unittest

from app.modules.video.assets.temporal_asset_builder import (
    TemporalAssetBuilder
)
from app.modules.video.overlays.overlay_selector import OverlaySelector
from app.shared.operational_error import OperationalError
from app.modules.video.visual_effects.visual_effect_selector import (
    VisualEffectSelector
)


def selector_config(
    directory,
    folder_selection="sequence",
    file_selection="sequence",
    avoid_repeats=True,
    folders=(),
    types=(),
    extensions=(".mov",),
    folder_weights=None,
    file_weights=None
):
    return SimpleNamespace(
        directory=str(directory),
        folder_selection=folder_selection,
        file_selection=file_selection,
        avoid_repeats=avoid_repeats,
        folders=folders,
        types=types,
        extensions=extensions,
        folder_weights=folder_weights or {},
        file_weights=file_weights or {}
    )


class VideoAssetSelectorTest(
    unittest.TestCase
):

    def test_overlay_sequence_selects_folder_and_file_by_scene(
        self
    ):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            warm = root_path / "warm"
            cool = root_path / "cool"
            warm.mkdir()
            cool.mkdir()

            warm_asset = warm / "a.mov"
            cool_asset = cool / "b.mov"
            warm_asset.touch()
            cool_asset.touch()

            selector = OverlaySelector(
                selector_config(
                    directory=root_path,
                    avoid_repeats=False
                )
            )

            self.assertEqual(
                selector.select(
                    scene_index=0,
                    scene_count=2
                ),
                cool_asset
            )

            self.assertEqual(
                selector.select(
                    scene_index=1,
                    scene_count=2
                ),
                warm_asset
            )

    def test_visual_effect_selector_filters_relative_types(
        self
    ):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            light = root_path / "LightLeak"
            light.mkdir()

            selected = light / "LightLeak 1.mov"
            ignored = light / "LightLeak 2.mov"
            selected.touch()
            ignored.touch()

            selector = VisualEffectSelector(
                selector_config(
                    directory=root_path,
                    folders=("LightLeak",),
                    types=("LightLeak/LightLeak 1.mov",)
                )
            )

            self.assertEqual(
                selector.select(
                    scene_index=0,
                    scene_count=1
                ),
                selected
            )

    def test_overlay_avoid_repeats_records_previous_asset(
        self
    ):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            first = root_path / "a.mov"
            second = root_path / "b.mov"
            first.touch()
            second.touch()

            selector = OverlaySelector(
                selector_config(
                    directory=root_path,
                    avoid_repeats=True
                )
            )

            self.assertEqual(
                selector.select(
                    scene_index=0,
                    scene_count=2
                ),
                first
            )

            self.assertEqual(
                selector.previous_asset,
                first
            )

            self.assertEqual(
                selector.select(
                    scene_index=1,
                    scene_count=2
                ),
                second
            )

    def test_overlay_random_folder_selection_uses_category_cooldown(
        self
    ):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            electricity = root_path / "Electricity"
            technology = root_path / "Technology"
            electricity.mkdir()
            technology.mkdir()

            electricity_asset = (
                electricity
                / "Electricity 1.mp4"
            )
            technology_asset = (
                technology
                / "Technology 1.mp4"
            )
            electricity_asset.touch()
            technology_asset.touch()

            selector = OverlaySelector(
                selector_config(
                    directory=root_path,
                    folder_selection="random",
                    file_selection="sequence",
                    avoid_repeats=False,
                    folders=(
                        "Electricity",
                        "Technology"
                    ),
                    extensions=(
                        ".mp4",
                    ),
                    folder_weights={
                        "Electricity": 3.0,
                        "Technology": 2.0
                    }
                )
            )

            with patch(
                "app.modules.video.overlays"
                ".overlay_category_distribution_policy"
                ".random.choices",
                side_effect=lambda population, weights, k: [
                    population[0]
                ]
            ) as choices:
                first = selector.select(
                    scene_index=0,
                    scene_count=2
                )
                second = selector.select(
                    scene_index=1,
                    scene_count=2
                )

        self.assertEqual(
            electricity_asset,
            first
        )
        self.assertEqual(
            technology_asset,
            second
        )
        first_population = tuple(
            folder.name
            for folder in (
                choices.call_args_list[0]
                .kwargs["population"]
            )
        )
        second_population = tuple(
            folder.name
            for folder in (
                choices.call_args_list[1]
                .kwargs["population"]
            )
        )
        self.assertEqual(
            (
                "Electricity",
                "Technology"
            ),
            first_population
        )
        self.assertEqual(
            (
                "Technology",
            ),
            second_population
        )

    def test_overlay_category_cooldown_allows_single_folder_reuse(
        self
    ):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            electricity = root_path / "Electricity"
            electricity.mkdir()

            asset = electricity / "Electricity 1.mp4"
            asset.touch()

            selector = OverlaySelector(
                selector_config(
                    directory=root_path,
                    folder_selection="random",
                    file_selection="sequence",
                    avoid_repeats=False,
                    folders=(
                        "Electricity",
                    ),
                    extensions=(
                        ".mp4",
                    )
                )
            )

            with patch(
                "app.modules.video.overlays"
                ".overlay_category_distribution_policy"
                ".random.choices",
                side_effect=lambda population, weights, k: [
                    population[0]
                ]
            ):
                first = selector.select(
                    scene_index=0,
                    scene_count=2
                )
                second = selector.select(
                    scene_index=1,
                    scene_count=2
                )

        self.assertEqual(
            asset,
            first
        )
        self.assertEqual(
            asset,
            second
        )

    def test_overlay_category_distribution_state_can_reset_per_video(
        self
    ):
        selector = OverlaySelector(
            selector_config(
                directory="unused",
                folder_selection="random"
            )
        )
        selector.category_distribution_policy.previous_category = (
            "Electricity"
        )

        selector.reset_category_distribution()

        self.assertIsNone(
            selector
            .category_distribution_policy
            .previous_category
        )

    def test_visual_effect_missing_directory_message_is_preserved(
        self
    ):
        missing = Path("missing_visual_effects_directory")
        selector = VisualEffectSelector(
            selector_config(
                directory=missing
            )
        )

        with self.assertRaisesRegex(
            FileNotFoundError,
            "No existe la carpeta de efectos visuales"
        ):
            selector.select(
                scene_index=0,
                scene_count=1
            )

    def test_missing_asset_directory_becomes_a_clear_filesystem_error(
        self
    ):
        missing = Path("missing_visual_effects_directory")
        config = SimpleNamespace(
            enabled=True,
            probability=1.0,
            **vars(selector_config(directory=missing))
        )
        builder = TemporalAssetBuilder(
            config=config,
            selector=VisualEffectSelector(config)
        )

        with self.assertRaises(OperationalError) as caught:
            builder.build(
                scene_index=0,
                scene_count=1
            )

        context = caught.exception.context
        self.assertEqual("FILESYSTEM", context.family)
        self.assertIn(
            "No existe la carpeta de efectos visuales",
            context.user_message
        )
        self.assertIn("assets/README.md", context.recommended_action)
        self.assertIsInstance(
            caught.exception.__cause__,
            FileNotFoundError
        )

    def test_visual_effect_selector_has_no_overlay_category_cooldown(
        self
    ):
        selector = VisualEffectSelector(
            selector_config(
                directory="unused"
            )
        )

        self.assertFalse(
            hasattr(
                selector,
                "category_distribution_policy"
            )
        )


if __name__ == "__main__":
    unittest.main()
