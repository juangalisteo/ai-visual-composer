from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from app.managers.project_manager import ProjectManager
from app.modules.subtitles.io.whisper_transcription_config import (
    WhisperTranscriptionConfig,
)
from app.modules.subtitles.policies.timing import whisper_timing_path
from app.shared.progress_logger import ProgressLogger
from app.shared.operational_error import create_operational_error


class SubtitleBuilder:

    def __init__(
        self,
        transcription_config: WhisperTranscriptionConfig | None = None,
    ):
        self.transcription_config = (
            transcription_config
            if transcription_config is not None
            else WhisperTranscriptionConfig()
        )

    def build(
        self,
        audio_path=None,
        output_path=None
    ):
        ProgressLogger.start(
            "GENERANDO TRANSCRIPCI\u00d3N TEMPORAL"
        )

        start = time.perf_counter()

        if audio_path is None:
            audio_path = ProjectManager().audio_path()

        if output_path is None:
            output_path = ProjectManager().subtitle_path()

        audio_path = Path(
            audio_path
        )

        output_path = Path(
            output_path
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        if not audio_path.exists():
            error = FileNotFoundError(
                f"No existe el audio: "
                f"{audio_path}"
            )
            raise create_operational_error(
                family="FILESYSTEM",
                user_message="No se encontró el audio requerido para transcribir.",
                recommended_action="Comprueba la ruta del audio de entrada.",
                operation="Preparar transcripción con Whisper",
                resource=str(audio_path),
            ) from error

        with tempfile.TemporaryDirectory(
            dir=output_path.parent
        ) as temp_dir:
            temp_output_dir = Path(
                temp_dir
            )

            command = [
                "python",
                "-m",
                "whisper",
                str(audio_path),
                *self.transcription_config.cli_arguments(),
                "--output_dir",
                str(temp_output_dir)
            ]

            try:
                subprocess.run(command, check=True)
            except subprocess.CalledProcessError as error:
                raise create_operational_error(
                    family="SUBTITLES",
                    user_message="Whisper no pudo generar los subtítulos temporales.",
                    recommended_action="Comprueba la instalación de Whisper y el audio de entrada.",
                    operation="Transcribir audio con Whisper",
                    resource=str(audio_path),
                    technical_metadata={
                        "command": tuple(map(str, error.cmd or command)),
                        "returncode": error.returncode,
                        "model": self.transcription_config.model,
                        "phase": "transcription",
                        "expected_output": str(temp_output_dir),
                    },
                ) from error

            generated_srt = (
                temp_output_dir
                / f"{audio_path.stem}.srt"
            )

            if not generated_srt.exists():
                error = FileNotFoundError(
                    "No se generó el SRT esperado: "
                    f"{generated_srt}"
                )
                raise create_operational_error(
                    family="VALIDATION",
                    user_message="Whisper terminó sin generar el SRT esperado.",
                    recommended_action="Revisa el audio de entrada y vuelve a ejecutar la transcripción.",
                    operation="Validar salida de Whisper",
                    resource=str(generated_srt),
                    technical_metadata={"phase": "transcription_output"},
                ) from error

            shutil.move(
                str(generated_srt),
                str(output_path)
            )

            generated_json = (
                temp_output_dir
                / f"{audio_path.stem}.json"
            )

            if generated_json.exists():
                shutil.move(
                    str(generated_json),
                    str(
                        whisper_timing_path(
                            output_path
                        )
                    )
                )

        if not output_path.exists():
            error = FileNotFoundError(
                "El proceso terminó, pero no se encontró "
                "el archivo de subtítulos esperado: "
                f"{output_path}"
            )
            raise create_operational_error(
                family="VALIDATION",
                user_message="La transcripción terminó sin dejar el archivo de subtítulos esperado.",
                recommended_action="Revisa el resultado de Whisper y el directorio de salida.",
                operation="Validar salida de Whisper",
                resource=str(output_path),
                technical_metadata={"phase": "transcription_output"},
            ) from error

        if output_path.stat().st_size <= 0:
            error = RuntimeError(
                "El archivo de subtítulos generado "
                "está vacío."
            )
            raise create_operational_error(
                family="VALIDATION",
                user_message="La transcripción generó un archivo de subtítulos vacío.",
                recommended_action="Revisa el audio de entrada y vuelve a ejecutar la transcripción.",
                operation="Validar salida de Whisper",
                resource=str(output_path),
                technical_metadata={"phase": "transcription_output"},
            ) from error

        elapsed = (
            time.perf_counter()
            - start
        )

        ProgressLogger.finish(
            "TRANSCRIPCI\u00d3N TEMPORAL GENERADA",
            elapsed
        )

        return output_path
