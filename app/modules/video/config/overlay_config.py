from dataclasses import dataclass

from app.modules.video.config.layer_config_validator import (
    LayerConfigValidator
)


@dataclass(frozen=True)
class OverlayConfig:

    enabled: bool

    directory: str

    folder_selection: str
    file_selection: str
    avoid_repeats: bool

    repeat_mode: str
    min_seconds: float
    max_seconds: float
    loop_file: bool

    opacity: float
    blend_mode: str
    probability: float

    folders: tuple[str, ...]
    types: tuple[str, ...]
    extensions: tuple[str, ...]

    folder_weights: dict[str, float]
    file_weights: dict[str, float]

    def __post_init__(
        self
    ):
        LayerConfigValidator().validate(
            config=self,
            min_seconds_message=(
                "La duraciÃ³n mÃ­nima del overlay "
                "debe ser superior a cero."
            ),
            max_seconds_message=(
                "La duraciÃ³n mÃ¡xima del overlay "
                "debe ser superior a cero."
            ),
            max_less_than_min_message=(
                "La duraciÃ³n mÃ¡xima del overlay "
                "no puede ser inferior a la mÃ­nima."
            )
        )
