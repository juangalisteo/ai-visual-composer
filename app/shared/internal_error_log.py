"""Evidence file for INTERNAL incidents, relative to the working directory."""

from datetime import datetime
from pathlib import Path


LOGS_DIRECTORY = Path("logs")


def write_internal_error_log(error, error_traceback, *, operation):
    """Return the new log path, or None: logging never hides the incident."""
    try:
        now = datetime.now()
        path = LOGS_DIRECTORY / (
            f"error_interno_{now:%Y-%m-%d_%H-%M-%S_%f}.txt"
        )
        LOGS_DIRECTORY.mkdir(exist_ok=True)
        with path.open(
            "x",
            encoding="utf-8",
            errors="backslashreplace",
        ) as log_file:
            log_file.write(
                f"Fecha: {now:%Y-%m-%d %H:%M:%S}\n"
                f"Operación: {operation}\n"
                f"Tipo: {type(error).__name__}\n"
                f"Mensaje: {error}\n"
                "\n"
                f"{error_traceback}"
            )
    except Exception:
        return None
    return path.as_posix()
