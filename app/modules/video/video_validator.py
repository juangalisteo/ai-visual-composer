from pathlib import Path

from app.shared.media_probe import MediaProbe
from app.shared.progress_logger import ProgressLogger
from app.shared.operational_error import create_operational_error


class VideoValidator:

    def validate(
        self,
        output_path,
        expected_duration,
        max_duration_difference
    ):
        output_path = Path(
            output_path
        )

        if not output_path.exists():
            error = FileNotFoundError(
                "FFmpeg terminó, pero no se encontró "
                "el vídeo esperado: "
                f"{output_path}"
            )
            raise create_operational_error(
                family="VALIDATION",
                user_message="El render terminó sin generar el vídeo esperado.",
                recommended_action="Revisa el diagnóstico del render y el espacio disponible.",
                operation="Validar vídeo generado",
                resource=str(output_path),
            ) from error

        if output_path.stat().st_size <= 0:
            error = RuntimeError(
                "El vídeo generado está vacío: "
                f"{output_path}"
            )
            raise create_operational_error(
                family="VALIDATION",
                user_message="El render generó un vídeo vacío.",
                recommended_action="Revisa el diagnóstico del render antes de volver a intentarlo.",
                operation="Validar vídeo generado",
                resource=str(output_path),
            ) from error

        generated_duration = (
            MediaProbe.get_duration(
                output_path
            )
        )

        duration_difference = abs(
            expected_duration
            - generated_duration
        )

        ProgressLogger.info(
            f"Duración esperada: "
            f"{expected_duration:.2f} segundos"
        )

        ProgressLogger.info(
            f"Duración generada: "
            f"{generated_duration:.2f} segundos"
        )

        ProgressLogger.info(
            f"Diferencia de duración: "
            f"{duration_difference:.2f} segundos"
        )

        if (
            duration_difference
            > max_duration_difference
        ):
            error = RuntimeError(
                "La duración del vídeo no coincide "
                "con la duración del audio dentro de "
                "la tolerancia configurada."
            )
            raise create_operational_error(
                family="VALIDATION",
                user_message="El vídeo generado no cumple la duración esperada.",
                recommended_action="Revisa el diagnóstico del render y la entrada multimedia.",
                operation="Validar vídeo generado",
                resource=str(output_path),
            ) from error

        return generated_duration
