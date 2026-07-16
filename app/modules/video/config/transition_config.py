from dataclasses import dataclass

from app.modules.video.config.transition_contract import (
    SUPPORTED_TRANSITION_TYPES
)


@dataclass(frozen=True)
class TransitionConfig:

    enabled: bool

    duration: float

    selection: str
    avoid_repeats: bool

    types: tuple[str, ...]

    weights: dict[str, float]

    def __post_init__(
        self
    ):
        allowed_selection_modes = {
            "sequence",
            "random"
        }

        allowed_transition_types = set(
            SUPPORTED_TRANSITION_TYPES
        )

        if self.duration <= 0:
            raise ValueError(
                "La duración de las transiciones "
                "debe ser superior a cero."
            )

        selection = str(
            self.selection
        ).strip().lower()

        if (
            selection
            not in allowed_selection_modes
        ):
            raise ValueError(
                "El modo de selección debe ser "
                "'sequence' o 'random'."
            )

        if not self.types:
            raise ValueError(
                "Debe existir al menos "
                "una transición."
            )

        invalid_transition_types = [
            transition_type
            for transition_type in self.types
            if transition_type
            not in allowed_transition_types
        ]

        if invalid_transition_types:
            raise ValueError(
                "Tipos de transición no válidos: "
                + ", ".join(
                    invalid_transition_types
                )
            )

        if (
            self.avoid_repeats
            and len(
                set(
                    self.types
                )
            ) < 2
        ):
            raise ValueError(
                "Para evitar repeticiones "
                "deben existir al menos "
                "dos transiciones diferentes."
            )

        if not isinstance(
            self.weights,
            dict
        ):
            raise TypeError(
                "Los pesos de transición "
                "deben ser un diccionario."
            )

        for transition_type, weight in (
            self.weights.items()
        ):
            if (
                transition_type
                not in allowed_transition_types
            ):
                raise ValueError(
                    "Peso configurado para una "
                    f"transición no válida: "
                    f"{transition_type}"
                )

            if float(
                weight
            ) <= 0:
                raise ValueError(
                    "El peso de cada transición "
                    "debe ser superior a cero."
                )
