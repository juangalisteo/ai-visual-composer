from pathlib import Path
import shutil

from app.shared.progress_logger import ProgressLogger


class OutputResetBlockedError(RuntimeError):
    """Expected user-facing error when Windows keeps an output file open."""


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
            raise OutputResetBlockedError(
                "No se puede eliminar OUTPUT porque uno de sus archivos "
                "esta siendo utilizado por otro programa.\n\n"
                "Cierra el archivo y vuelve a intentarlo."
            ) from error

        ProgressLogger.info(
            "Output reseteado."
        )
