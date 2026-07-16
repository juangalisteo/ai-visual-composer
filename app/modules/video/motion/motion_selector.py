import random


class MotionSelector:

    def __init__(
        self,
        config
    ):
        self.config = config

        self._last_motion = None

    def select(
        self,
        image_index,
        image_count
    ):
        if image_count <= 0:
            raise ValueError(
                "El número de imágenes debe ser "
                "superior a cero."
            )

        if image_index < 0:
            raise ValueError(
                "El índice de imagen no puede ser "
                "negativo."
            )

        if self.config.selection == "sequence":
            return self._select_sequence(
                image_index
            )

        if self.config.selection == "random":
            return self._select_random()

        raise ValueError(
            f"Modo de selección no soportado: "
            f"{self.config.selection}"
        )

    def _select_sequence(
        self,
        image_index
    ):
        motions = self.config.types

        motion = motions[
            image_index
            % len(motions)
        ]

        self._last_motion = motion

        return motion

    def _select_random(
        self
    ):
        motions = list(
            self.config.types
        )

        if (
            self.config.avoid_repeats
            and self._last_motion in motions
            and len(motions) > 1
        ):
            motions.remove(
                self._last_motion
            )

        weights = [
            self.config.weights.get(
                motion,
                1.0
            )
            for motion in motions
        ]

        motion = random.choices(
            population=motions,
            weights=weights,
            k=1
        )[0]

        self._last_motion = motion

        return motion