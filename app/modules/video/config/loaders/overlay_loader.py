from app.modules.video.config.loaders.layer_config_loader import (
    LayerConfigLoader
)
from app.modules.video.config.overlay_config import OverlayConfig


class OverlayConfigLoader:

    def __init__(
        self
    ):
        self.layer_loader = LayerConfigLoader()

    def load(
        self,
        profile
    ):
        overlay_data = self.layer_loader.load_section(
            profile=profile,
            section_name="overlays",
            section_error_message=(
                "La configuración "
                "video_style.overlays "
                "debe ser un diccionario."
            )
        )

        legacy_keys = tuple(
            key
            for key in (
                "selection",
                "weights"
            )
            if key in overlay_data
        )
        if legacy_keys:
            raise ValueError(
                "video_style.overlays no admite las claves "
                "legacy selection/weights. Use "
                "folder_selection, file_selection, "
                "folder_weights y file_weights."
            )

        layer_data = self.layer_loader.load_common(
            data=overlay_data,
            default_directory="assets/videos/overlays"
        )

        return OverlayConfig(
            **layer_data
        )
