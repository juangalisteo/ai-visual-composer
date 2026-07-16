from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from app.modules.video.overlays.overlay_selector import OverlaySelector
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

    def test_overlay_avoid_repeats_keeps_previous_overlay_alias(
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
                selector.previous_overlay,
                first
            )

            self.assertEqual(
                selector.select(
                    scene_index=1,
                    scene_count=2
                ),
                second
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


if __name__ == "__main__":
    unittest.main()
