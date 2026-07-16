from dataclasses import dataclass


@dataclass(frozen=True)
class FadeConfig:

    enabled: bool

    fade_in: bool

    fade_out: bool

    duration: float

    def __post_init__(
        self
    ):
        if self.duration < 0:
            raise ValueError(
                "La duración del fade "
                "no puede ser negativa."
            )