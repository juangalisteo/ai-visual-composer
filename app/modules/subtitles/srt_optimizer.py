from pathlib import Path
import re
import time

from app.managers.project_manager import ProjectManager
from app.shared.config_manager import ConfigManager
from app.shared.progress_logger import ProgressLogger

from app.modules.subtitles.models.single_line_model import (
    SingleLineModel
)
from app.modules.subtitles.models.word_by_word_model import (
    WordByWordModel
)


class SrtOptimizer:

    def __init__(
        self
    ):
        config = ConfigManager()

        subtitle_config = (
            config.get_subtitle_config()
        )

        mode = subtitle_config["mode"]

        if mode == "single_line":
            self.model = SingleLineModel(
                subtitle_config
            )

        elif mode == "word_by_word":
            self.model = WordByWordModel(
                subtitle_config
            )

        else:
            raise ValueError(
                "Modelo de subtítulos no soportado: "
                f"{mode}"
            )

    def optimize(
        self,
        input_path=None,
        output_path=None
    ):
        ProgressLogger.start(
            "OPTIMIZANDO SRT"
        )

        start = time.perf_counter()

        project = ProjectManager()

        if input_path is None:
            input_path = (
                project.subtitle_path()
            )

        if output_path is None:
            output_path = (
                project.subtitle_path()
            )

        input_path = Path(
            input_path
        )

        output_path = Path(
            output_path
        )

        if not input_path.exists():
            raise FileNotFoundError(
                f"No existe el SRT: "
                f"{input_path}"
            )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        content = input_path.read_text(
            encoding="utf-8"
        )

        if not content.strip():
            raise ValueError(
                "El archivo SRT está vacío."
            )

        blocks = re.split(
            r"\n\s*\n",
            content.strip()
        )

        optimized_blocks = (
            self.model.optimize(
                blocks
            )
        )

        output_path.write_text(
            "\n\n".join(
                optimized_blocks
            ),
            encoding="utf-8"
        )

        if not output_path.exists():
            raise FileNotFoundError(
                "No se encontró el SRT optimizado: "
                f"{output_path}"
            )

        if output_path.stat().st_size <= 0:
            raise RuntimeError(
                "El SRT optimizado está vacío."
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