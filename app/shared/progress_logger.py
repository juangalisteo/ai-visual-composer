from app.shared.time_formatter import TimeFormatter


class ProgressLogger:

    @staticmethod
    def start(
        message
    ):
        print(
            f"\n{message}..."
        )

    @staticmethod
    def info(
        message
    ):
        print(
            message
        )

    @staticmethod
    def finish(
        message,
        elapsed
    ):
        print(
            f"{message} "
            f"({TimeFormatter.format(elapsed)})"
        )

    @staticmethod
    def warning(
        message
    ):
        print(
            f"ADVERTENCIA: {message}"
        )

    @staticmethod
    def error(
        message
    ):
        print(
            f"ERROR: {message}"
        )