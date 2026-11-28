from app.shared.screen_number import screen_decimal


class TimeFormatter:

    @staticmethod
    def format(seconds, screen=True):
        """Elapsed time such as «1 min 22,23 s».

        With ``screen`` (the terminal and the summaries) the decimals take a
        comma; without it (the technical lines of the record) a point.
        """
        seconds = max(
            0.0,
            float(seconds)
        )

        def decimals(value):
            return (
                screen_decimal(value, 2)
                if screen
                else f"{value:.2f}"
            )

        if seconds < 60:
            return f"{decimals(seconds)} s"

        minutes = int(
            seconds // 60
        )

        remaining_seconds = (
            seconds % 60
        )

        if minutes < 60:
            return (
                f"{minutes} min "
                f"{decimals(remaining_seconds)} s"
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
            f"{decimals(remaining_seconds)} s"
        )
