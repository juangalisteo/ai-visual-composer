import sys

from app.shared.time_formatter import TimeFormatter


class ProgressLogger:
    _stdout_configured = False
    _stdout_stream = None

    @staticmethod
    def _configure_stdout():
        stream = sys.stdout

        if ProgressLogger._stdout_configured:
            if ProgressLogger._stdout_stream is stream:
                return

        reconfigure = getattr(
            stream,
            "reconfigure",
            None
        )

        if callable(reconfigure):
            try:
                reconfigure(
                    encoding="utf-8",
                    errors="replace"
                )
            except (TypeError, ValueError, OSError):
                pass

        ProgressLogger._stdout_configured = True
        ProgressLogger._stdout_stream = stream

    @staticmethod
    def _safe_print(message):
        ProgressLogger._configure_stdout()

        try:
            print(message)
        except UnicodeEncodeError:
            stream = sys.stdout
            encoding = getattr(
                stream,
                "encoding",
                None
            ) or "utf-8"
            safe_message = str(message).encode(
                encoding,
                errors="backslashreplace"
            ).decode(
                encoding,
                errors="replace"
            )
            print(safe_message)

    @staticmethod
    def start(
        message
    ):
        ProgressLogger._safe_print(
            f"\n{message}..."
        )

    @staticmethod
    def info(
        message
    ):
        ProgressLogger._safe_print(
            message
        )

    @staticmethod
    def finish(
        message,
        elapsed
    ):
        ProgressLogger._safe_print(
            f"{message} "
            f"({TimeFormatter.format(elapsed)})"
        )

    @staticmethod
    def warning(
        message
    ):
        ProgressLogger._safe_print(
            f"ADVERTENCIA: {message}"
        )

    @staticmethod
    def error(
        message
    ):
        ProgressLogger._safe_print(
            f"ERROR: {message}"
        )
