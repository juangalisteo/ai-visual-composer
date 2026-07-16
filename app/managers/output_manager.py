from pathlib import Path
import shutil

from app.shared.progress_logger import ProgressLogger


class OutputManager:

    def __init__(
        self
    ):
        self.output_path = Path(
            "output"
        )

    def reset(
        self
    ):
        self.output_path.mkdir(
            parents=True,
            exist_ok=True
        )

        for item in self.output_path.iterdir():
            if item.is_dir():
                shutil.rmtree(
                    item
                )
            else:
                item.unlink()

        ProgressLogger.info(
            "Output reseteado."
        )