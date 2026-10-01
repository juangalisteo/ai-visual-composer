import sys

from app.shared.operation_warnings import OperationWarning, OperationWarnings
from app.shared.time_formatter import TimeFormatter


class ProgressLogger:
    _stdout_configured = False
    _stdout_stream = None

    @staticmethod
    def _configure_stdout():
        stream = sys.stdout
        if (
            ProgressLogger._stdout_configured
            and ProgressLogger._stdout_stream is stream
        ):
            return

        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (TypeError, ValueError, OSError):
                pass

        ProgressLogger._stdout_configured = True
        ProgressLogger._stdout_stream = stream

    @staticmethod
    def _safe_print(message, warnings=None, operation=None):
        """Print safely and return a warning only if visible text degraded."""
        ProgressLogger._configure_stdout()
        text = str(message)
        stream = sys.stdout
        encoding = getattr(stream, "encoding", None) or "utf-8"

        try:
            text.encode(encoding, errors="strict")
            print(text)
            return None
        except UnicodeEncodeError:
            safe_message = text.encode(
                encoding,
                errors="backslashreplace",
            ).decode(encoding, errors="replace")
            print(safe_message)
            return ProgressLogger._unicode_warning(
                warnings=warnings,
                operation=operation,
                encoding=encoding,
            )

    @staticmethod
    def _unicode_warning(warnings, operation, encoding):
        warning = OperationWarning(
            family="DEGRADATION",
            user_message=(
                "Parte del texto mostrado en terminal se adaptó por la "
                "codificación disponible."
            ),
            recommended_action=(
                "Usa una terminal UTF-8 para ver todos los caracteres."
            ),
            operation=operation or "Salida de terminal",
            technical_metadata={
                "encoding": encoding,
                "source": "progress_logger",
            },
        )
        if isinstance(warnings, OperationWarnings):
            warnings.add(warning)
        return warning

    @staticmethod
    def start(message, warnings=None, operation=None):
        return ProgressLogger._safe_print(
            f"\n{message}...",
            warnings=warnings,
            operation=operation,
        )

    @staticmethod
    def info(message, warnings=None, operation=None):
        return ProgressLogger._safe_print(
            message,
            warnings=warnings,
            operation=operation,
        )

    @staticmethod
    def finish(message, elapsed, warnings=None, operation=None):
        return ProgressLogger._safe_print(
            f"{message} ({TimeFormatter.format(elapsed)})",
            warnings=warnings,
            operation=operation,
        )

    @staticmethod
    def warning(message, warnings=None, operation=None):
        return ProgressLogger._safe_print(
            f"ADVERTENCIA: {message}",
            warnings=warnings,
            operation=operation,
        )

    @staticmethod
    def error(message, warnings=None, operation=None):
        return ProgressLogger._safe_print(
            f"ERROR: {message}",
            warnings=warnings,
            operation=operation,
        )
