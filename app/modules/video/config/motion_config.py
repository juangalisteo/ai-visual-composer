from dataclasses import dataclass


@dataclass(frozen=True)
class MotionConfig:

    enabled: bool
    internal_scale: int

    base_zoom: float
    zoom_amount: float

    pan_zoom_enabled: bool
    pan_zoom_start: float

    selection: str
    avoid_repeats: bool

    types: tuple[str, ...]
    weights: dict[str, float]

    def __post_init__(
        self
    ):
        allowed_motion_types = {
            "zoom_in",
            "zoom_out",
            "pan_left",
            "pan_right",
            "pan_up",
            "pan_down"
        }

        allowed_selection_modes = {
            "sequence",
            "random"
        }

        if self.internal_scale < 1:
            raise ValueError(
                "La escala interna del movimiento "
                "debe ser igual o superior a 1."
            )

        if self.base_zoom < 0:
            raise ValueError(
                "El zoom base "
                "no puede ser negativo."
            )

        if self.zoom_amount < 0:
            raise ValueError(
                "La intensidad del zoom "
                "no puede ser negativa."
            )

        if self.pan_zoom_start < 0:
            raise ValueError(
                "El zoom inicial de los paneos "
                "no puede ser negativo."
            )

        maximum_zoom_increment = (
            self.base_zoom
            + self.zoom_amount
        )

        if (
            self.pan_zoom_start
            > maximum_zoom_increment
        ):
            raise ValueError(
                "El zoom inicial de los paneos "
                "no puede superar el zoom máximo."
            )

        selection = str(
            self.selection
        ).strip().lower()

        if (
            selection
            not in allowed_selection_modes
        ):
            raise ValueError(
                "El modo de selección de movimiento "
                "debe ser 'sequence' o 'random'."
            )

        if not self.types:
            raise ValueError(
                "Debe existir al menos "
                "un tipo de movimiento."
            )

        invalid_motion_types = [
            motion_type
            for motion_type in self.types
            if motion_type not in allowed_motion_types
        ]

        if invalid_motion_types:
            raise ValueError(
                "Tipos de movimiento no válidos: "
                + ", ".join(
                    invalid_motion_types
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
                "Para evitar repeticiones deben existir "
                "al menos dos movimientos diferentes."
            )

        if not isinstance(
            self.weights,
            dict
        ):
            raise TypeError(
                "Los pesos de movimiento "
                "deben ser un diccionario."
            )

        for motion_type, weight in (
            self.weights.items()
        ):
            if (
                motion_type
                not in allowed_motion_types
            ):
                raise ValueError(
                    "Peso configurado para un movimiento "
                    f"no válido: {motion_type}"
                )

            if float(
                weight
            ) <= 0:
                raise ValueError(
                    "El peso de cada movimiento "
                    "debe ser superior a cero."
                )