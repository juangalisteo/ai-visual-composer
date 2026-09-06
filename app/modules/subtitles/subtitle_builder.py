from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from app.managers.project_manager import ProjectManager
from app.modules.subtitles.timing import whisper_timing_path
from app.shared.progress_logger import ProgressLogger


class SubtitleBuilder:

    def __init__(
        self
    ):
        self.model = "medium"
        self.language = "Spanish"
        self.device = "cuda"

    def build(
        self,
        audio_path=None,
        output_path=None
    ):
        ProgressLogger.start(
            "GENERANDO SUBTÍTULOS"
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
            raise FileNotFoundError(
                f"No existe el audio: "
                f"{audio_path}"
            )

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
                "--model",
                self.model,
                "--task",
                "transcribe",
                "--language",
                self.language,
                "--word_timestamps",
                "True",
                "--output_format",
                "all",
                "--device",
                self.device,
                "--output_dir",
                str(temp_output_dir)
            ]

            subprocess.run(
                command,
                check=True
            )

            generated_srt = (
                temp_output_dir
                / f"{audio_path.stem}.srt"
            )

            if not generated_srt.exists():
                raise FileNotFoundError(
                    "No se generó el SRT esperado: "
                    f"{generated_srt}"
                )

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
            raise FileNotFoundError(
                "El proceso terminó, pero no se encontró "
                "el archivo de subtítulos esperado: "
                f"{output_path}"
            )

        if output_path.stat().st_size <= 0:
            raise RuntimeError(
                "El archivo de subtítulos generado "
                "está vacío."
            )

        elapsed = (
            time.perf_counter()
            - start
        )

        ProgressLogger.finish(
            "Finalizado",
            elapsed
        )

        return output_path
