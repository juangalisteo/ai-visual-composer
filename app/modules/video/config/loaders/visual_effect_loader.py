from app.modules.video.config.loaders.layer_config_loader import (
    LayerConfigLoader
)
from app.modules.video.config.visual_effect_config import (
    VisualEffectConfig
)


class VisualEffectConfigLoader:

    def __init__(
        self
    ):
        self.layer_loader = LayerConfigLoader()

    def load(
        self,
        profile
    ):
        effect_data = self.layer_loader.load_section(
            profile=profile,
            section_name="visual_effects",
            section_error_message=(
                "La configuraciÃ³n "
                "video_style.visual_effects "
                "debe ser un diccionario."
            )
        )

        mode = str(
            effect_data.get(
                "mode",
                "overlay"
            )
        ).strip().lower()

        layer_data = self.layer_loader.load_common(
            data=effect_data,
            default_directory="assets/videos/visual_effects",
            use_legacy_selection=False,
            use_legacy_weights=False
        )

        return VisualEffectConfig(
            mode=mode,
            **layer_data
        )
