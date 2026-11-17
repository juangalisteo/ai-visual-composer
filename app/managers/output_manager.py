from pathlib import Path
import shutil

from app.shared.operational_error import create_operational_error
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

        try:
            for item in self.output_path.iterdir():
                if item.is_dir():
                    shutil.rmtree(
                        item
                    )
                else:
                    item.unlink()
        except PermissionError as error:
            if getattr(error, "winerror", None) != 32:
                raise
            raise create_operational_error(
                family="FILESYSTEM",
                user_message=(
                    "No se puede eliminar OUTPUT porque uno de sus archivos "
                    "está siendo utilizado por otro programa."
                ),
                recommended_action="Cierra el archivo y vuelve a intentarlo.",
                operation="Eliminar OUTPUT",
                resource=error.filename,
            ) from error

        ProgressLogger.info(
            "Output reseteado."
        )
