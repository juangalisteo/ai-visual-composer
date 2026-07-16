class TimeFormatter:

    @staticmethod
    def format(seconds):
        seconds = max(
            0.0,
            float(seconds)
        )

        if seconds < 60:
            return f"{seconds:.2f} s"

        minutes = int(
            seconds // 60
        )

        remaining_seconds = (
            seconds % 60
        )

        if minutes < 60:
            return (
                f"{minutes} min "
                f"{remaining_seconds:.2f} s"
            )

        hours = int(
            minutes // 60
        )

        remaining_minutes = (
            minutes % 60
        )

        return (
            f"{hours} h "
            f"{remaining_minutes} min "
            f"{remaining_seconds:.2f} s"
        )