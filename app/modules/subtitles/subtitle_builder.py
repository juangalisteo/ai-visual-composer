from pathlib import Path
import shutil
import subprocess
import time

from app.managers.project_manager import ProjectManager
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

        project = ProjectManager()

        if audio_path is None:
            audio_path = project.audio_path()

        if output_path is None:
            output_path = project.subtitle_path()

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

        temp_output_dir = (
            output_path.parent
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
            "--output_format",
            "srt",
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