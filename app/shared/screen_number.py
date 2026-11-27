"""Numbers as the user reads them in the terminal: with a decimal comma.

Only for text shown on screen (progress, summaries, warnings and errors).
Files (JSON, SRT, ASS, manifests, the technical lines of the record of the
run) and FFmpeg commands keep the decimal point and never use this.
"""


def screen_decimal(value, places=None):
    """``value`` with ``places`` decimals, or as short as possible with None.

    ``screen_decimal(5.5, 2)`` is ``"5,50"`` and ``screen_decimal(12.5)`` is
    ``"12,5"``.
    """
    value = float(value)
    text = f"{value:g}" if places is None else f"{value:.{places}f}"
    return text.replace(".", ",")
