from app.modules.video.assets.temporal_asset_builder import (
    TemporalAssetBuilder
)
from app.modules.video.overlays.overlay_selector import (
    OverlaySelector
)


class OverlayBuilder:

    def __init__(
        self,
        config
    ):
        self.config = config

        self._asset_builder = TemporalAssetBuilder(
            config=config,
            selector=OverlaySelector(
                config
            )
        )

        self._inputs = self._asset_builder._inputs

    @property
    def selector(
        self
    ):
        return self._asset_builder.selector

    @selector.setter
    def selector(
        self,
        selector
    ):
        self._asset_builder.selector = selector

    @property
    def inputs(
        self
    ):
        return tuple(
            self._inputs
        )

    def reset(
        self
    ):
        self._asset_builder.reset()

    def build(
        self,
        scene_index,
        scene_count
    ):
        selection = self._asset_builder.build(
            scene_index=scene_index,
            scene_count=scene_count
        )

        if selection is None:
            return self._empty()

        return {
            "inputs": selection["inputs"],

            "overlay": selection["asset"],

            "overlay_path": selection["asset_path"],

            "input_position": selection["input_position"],

            "repeat_mode": (
                selection["repeat_mode"]
            ),

            "duration": selection["duration"],

            "loop_file": (
                selection["loop_file"]
            ),

            "opacity": (
                selection["opacity"]
            ),

            "blend_mode": (
                selection["blend_mode"]
            ),

            "probability": (
                selection["probability"]
            )
        }

    def _empty(
        self
    ):
        return {
            "inputs": [],
            "overlay": None,
            "overlay_path": None
        }
