from collections import Counter
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from app.managers.project_manager import ProjectManager
from app.modules.subtitles.io.whisper_segment_filter import (
    REPETITION_IN_SILENCE,
    REPETITION_WITHOUT_SPEECH,
    WhisperRepetitionFilter,
)
from app.modules.subtitles.io.whisper_transcription_config import (
    WhisperTranscriptionConfig,
)
from app.modules.subtitles.policies.timing import whisper_timing_path
from app.shared.progress_logger import ProgressLogger
from app.shared.operational_error import create_operational_error


class SubtitleBuilder:

    DISCARD_REASON_LABELS = {
        REPETITION_IN_SILENCE: "repetición en silencio",
        REPETITION_WITHOUT_SPEECH: "repetición sin voz",
    }

    def __init__(
        self,
        transcription_config: WhisperTranscriptionConfig | None = None,
        segment_filter: WhisperRepetitionFilter | None = None,
    ):
        self.transcription_config = (
            transcription_config
            if transcription_config is not None
            else WhisperTranscriptionConfig()
        )
        self.segment_filter = (
            segment_filter
            if segment_filter is not None
            else WhisperRepetitionFilter()
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

            generated_json = (
                temp_output_dir
                / f"{audio_path.stem}.json"
            )

            discarded = self.segment_filter.apply(
                generated_srt,
                generated_json,
                self.transcription_config.no_speech_threshold,
            )

            if discarded:
                ProgressLogger.info(
                    self._discarded_message(
                        discarded
                    )
                )

            shutil.move(
                str(generated_srt),
                str(output_path)
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

    @classmethod
    def _discarded_message(cls, discarded):
        count = len(discarded)
        noun = (
            "segmento descartado"
            if count == 1
            else "segmentos descartados"
        )
        reasons = Counter(
            cls.DISCARD_REASON_LABELS.get(
                entry["reason"],
                entry["reason"],
            )
            for entry in discarded
        )
        detail = (
            next(iter(reasons))
            if len(reasons) == 1
            else ", ".join(
                f"{number} por {label}"
                for label, number in reasons.items()
            )
        )
        return (
            f"Whisper: {count} {noun} "
            f"({detail})"
        )
