import random
from pathlib import Path

from app.shared.operational_error import create_missing_asset_error


class TemporalAssetBuilder:

    def __init__(
        self,
        config,
        selector
    ):
        self.config = config
        self.selector = selector
        self._inputs = []

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
        self._inputs.clear()

    def build(
        self,
        scene_index,
        scene_count
    ):
        if not self.config.enabled:
            return None

        if (
            random.random()
            > self.config.probability
        ):
            return None

        try:
            asset_path = self.selector.select(
                scene_index=scene_index,
                scene_count=scene_count
            )
        except (FileNotFoundError, NotADirectoryError) as error:
            raise create_missing_asset_error(
                error, operation="Preparar overlays y efectos visuales"
            ) from error

        if asset_path is None:
            return None

        asset_path = Path(
            asset_path
        ).resolve()

        if asset_path not in self._inputs:
            self._inputs.append(
                asset_path
            )

        duration = random.uniform(
            self.config.min_seconds,
            self.config.max_seconds
        )

        return {
            "inputs": [
                asset_path
            ],

            "asset": asset_path.name,

            "asset_path": asset_path,

            "input_position": (
                self._inputs.index(
                    asset_path
                )
            ),

            "repeat_mode": (
                self.config.repeat_mode
            ),

            "duration": duration,

            "loop_file": (
                self.config.loop_file
            ),

            "opacity": (
                self.config.opacity
            ),

            "blend_mode": (
                self.config.blend_mode
            ),

            "probability": (
                self.config.probability
            )
        }
