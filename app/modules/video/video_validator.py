from pathlib import Path

from app.shared.media_probe import MediaProbe
from app.shared.progress_logger import ProgressLogger


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
            raise FileNotFoundError(
                "FFmpeg terminó, pero no se encontró "
                "el vídeo esperado: "
                f"{output_path}"
            )

        if output_path.stat().st_size <= 0:
            raise RuntimeError(
                "El vídeo generado está vacío: "
                f"{output_path}"
            )

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
            ProgressLogger.warning(
                "La duración del vídeo no coincide "
                "con la duración del audio."
            )

        return generated_duration