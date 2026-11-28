from collections import Counter
import json
import os
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
from app.modules.subtitles.io.whisper_settings import (
    whisper_cuda_cache_dir,
    whisper_transcription_config,
    whisper_triton_cache_dir,
)
from app.modules.subtitles.io.whisper_transcription_config import (
    WhisperTranscriptionConfig,
)
from app.modules.subtitles.policies.timing import whisper_timing_path
from app.shared.progress_logger import ProgressLogger
from app.shared.operational_error import (
    create_operational_error,
    summarize_technical_text,
)


class SubtitleBuilder:

    DISCARD_REASON_LABELS = {
        REPETITION_IN_SILENCE: "repetición en silencio",
        REPETITION_WITHOUT_SPEECH: "repetición sin voz",
    }

    def __init__(
        self,
        transcription_config: WhisperTranscriptionConfig | None = None,
        segment_filter: WhisperRepetitionFilter | None = None,
        triton_cache_dir: Path | None = None,
        cuda_cache_dir: Path | None = None,
    ):
        # Without them, they are read from config/whisper.json when needed.
        self._transcription_config = transcription_config
        self._triton_cache_dir = triton_cache_dir
        self._cuda_cache_dir = cuda_cache_dir
        self.segment_filter = (
            segment_filter
            if segment_filter is not None
            else WhisperRepetitionFilter()
        )

    @property
    def transcription_config(self) -> WhisperTranscriptionConfig:
        if self._transcription_config is None:
            self._transcription_config = whisper_transcription_config()
        return self._transcription_config

    def build(
        self,
        audio_path=None,
        output_path=None,
        voice_pauses=()
    ):
        """Transcribe ``audio_path`` with Whisper into an SRT and its JSON.

        ``voice_pauses`` are the ``(start, end)`` silences, in seconds, that
        the voice backend wrote into that audio. They are recorded in the JSON
        as ``voice_pauses`` so the timing resolution can keep words out of
        them; Whisper's own word times are stored unchanged.
        """
        voice_pauses = tuple(
            (float(start), float(end))
            for start, end in voice_pauses
        )
        transcription_config = self.transcription_config
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

        whisper_environment = self._whisper_environment()

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
                *transcription_config.cli_arguments(),
                "--output_dir",
                str(temp_output_dir)
            ]

            try:
                completed = subprocess.run(
                    command,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env=whisper_environment,
                )
            except subprocess.CalledProcessError as error:
                self._record_whisper_output(error.output)
                raise create_operational_error(
                    family="SUBTITLES",
                    user_message="Whisper no pudo generar los subtítulos temporales.",
                    recommended_action="Comprueba la instalación de Whisper y el audio de entrada.",
                    operation="Transcribir audio con Whisper",
                    resource=str(audio_path),
                    technical_metadata={
                        "command": tuple(map(str, error.cmd or command)),
                        "returncode": error.returncode,
                        "model": transcription_config.model,
                        "phase": "transcription",
                        "expected_output": str(temp_output_dir),
                        "output_summary": summarize_technical_text(
                            error.output
                        ),
                    },
                ) from error
            self._record_whisper_output(getattr(completed, "stdout", None))

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
                transcription_config.no_speech_threshold,
            )

            if discarded:
                ProgressLogger.detail(
                    self._discarded_message(
                        discarded
                    )
                )

            if voice_pauses and generated_json.exists():
                self._record_voice_pauses(
                    generated_json,
                    voice_pauses
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

    def _whisper_environment(self):
        """The environment of the Whisper process.

        - ``TRITON_CACHE_DIR``: the folder of ``config/whisper.json``
          (``triton_cache_dir``), inside the project; without it Triton keeps
          its kernels in the user folder (~/.triton/cache). Triton creates it.
        - ``CUDA_CACHE_PATH``: the folder of ``config/whisper.json``
          (``cuda_cache_dir``), inside the project; without it CUDA keeps its
          kernels in %APPDATA%\\NVIDIA\\ComputeCache. CUDA reads it when it
          starts in the Whisper process, which this environment creates. CUDA
          does not create the folder (it just keeps no cache), so it is
          created here.
        - ``PYTHONIOENCODING``: its output goes to the record of the run (not
          to the screen) through a pipe; UTF-8, so no character stops Whisper.
        """
        triton_cache_dir = (
            self._triton_cache_dir
            if self._triton_cache_dir is not None
            else whisper_triton_cache_dir()
        )
        cuda_cache_dir = (
            self._cuda_cache_dir
            if self._cuda_cache_dir is not None
            else whisper_cuda_cache_dir()
        )
        try:
            cuda_cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise create_operational_error(
                family="FILESYSTEM",
                user_message=(
                    "No se pudo crear la carpeta de la caché de CUDA de Whisper."
                ),
                recommended_action=(
                    "Comprueba los permisos de la carpeta o cambia "
                    "«cuda_cache_dir» en config/whisper.json."
                ),
                operation="Preparar transcripción con Whisper",
                resource=str(cuda_cache_dir),
            ) from error
        return {
            **os.environ,
            "TRITON_CACHE_DIR": str(triton_cache_dir),
            "CUDA_CACHE_PATH": str(cuda_cache_dir),
            "PYTHONIOENCODING": "utf-8",
        }

    @staticmethod
    def _record_whisper_output(output):
        """Whisper's own lines (its segments and notices) go to the record."""
        if isinstance(output, str) and output.strip():
            ProgressLogger.detail(output.rstrip())

    @staticmethod
    def _record_voice_pauses(timing_path, voice_pauses):
        data = json.loads(
            timing_path.read_text(encoding="utf-8")
        )
        data["voice_pauses"] = [
            {"start": start, "end": end}
            for start, end in voice_pauses
        ]
        timing_path.write_text(
            json.dumps(data),
            encoding="utf-8"
        )

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
