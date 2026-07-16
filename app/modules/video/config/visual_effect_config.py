from dataclasses import dataclass

from app.modules.video.config.layer_config_validator import (
    LayerConfigValidator
)


@dataclass(frozen=True)
class VisualEffectConfig:

    enabled: bool

    directory: str
    mode: str

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
        allowed_modes = {
            "overlay",
            "transition",
            "both"
        }

        if (
            self.mode
            not in allowed_modes
        ):
            raise ValueError(
                "El modo de efecto visual debe ser "
                "'overlay', 'transition' o 'both'."
            )

        LayerConfigValidator().validate(
            config=self,
            min_seconds_message=(
                "La duración mínima del efecto "
                "debe ser superior a cero."
            ),
            max_seconds_message=(
                "La duración máxima del efecto "
                "debe ser superior a cero."
            ),
            max_less_than_min_message=(
                "La duración máxima no puede ser "
                "inferior a la mínima."
            )
        )
