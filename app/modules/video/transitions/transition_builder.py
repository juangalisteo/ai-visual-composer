import time

from app.modules.video.config.transition_contract import (
    SUPPORTED_TRANSITION_TYPES
)

from app.shared.progress_logger import ProgressLogger


class TransitionBuilder:

    def build(
        self,
        previous_stream,
        current_stream,
        transition_type,
        duration,
        offset,
        output_stream,
        from_scene,
        to_scene
    ):
        start = time.perf_counter()

        if not previous_stream:
            raise ValueError(
                "Falta el stream anterior."
            )

        if not current_stream:
            raise ValueError(
                "Falta el stream actual."
            )

        if not output_stream:
            raise ValueError(
                "Falta el nombre del stream de salida."
            )

        duration = float(
            duration
        )

        offset = float(
            offset
        )

        if duration <= 0:
            raise ValueError(
                "La duración de la transición debe ser "
                "superior a cero."
            )

        if offset < 0:
            raise ValueError(
                "El offset de la transición no puede "
                "ser negativo."
            )

        allowed_transitions = set(
            SUPPORTED_TRANSITION_TYPES
        )

        if transition_type not in allowed_transitions:
            raise ValueError(
                "Transición no válida: "
                f"{transition_type}"
            )

        filter_value = (
            f"{previous_stream}"
            f"{current_stream}"
            f"xfade="
            f"transition={transition_type}:"
            f"duration={duration:.3f}:"
            f"offset={offset:.3f}"
            f"{output_stream}"
        )

        elapsed = (
            time.perf_counter()
            - start
        )

        ProgressLogger.info(
            f"Transición {from_scene}→{to_scene}: "
            f"{transition_type} | "
            f"{duration:.2f} s | "
            f"offset {offset:.2f} s | "
            f"{elapsed:.4f} s"
        )

        return {
            "type": transition_type,
            "filter": filter_value,
            "duration": duration,
            "offset": offset
        }
