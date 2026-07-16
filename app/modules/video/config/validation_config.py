from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationConfig:

    max_duration_difference: float

    def __post_init__(
        self
    ):
        if self.max_duration_difference < 0:
            raise ValueError(
                "La diferencia máxima permitida "
                "no puede ser negativa."
            )