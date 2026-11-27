"""Record of one execution: ``output/<proyecto>/registro.txt``.

``main.py`` starts it once the project is known (after the menus) and stops
it when the run ends, also after an error. Every line the terminal shows goes
here too, with the time, and so do the technical lines that are not shown on
screen (``ProgressLogger.detail``): FFmpeg graph details, timing sources,
the output of Whisper… Writing the record never stops the run: if the file
cannot be written, the run goes on without it.
"""

from datetime import datetime
from pathlib import Path


class RunLog:
    """One active record at a time; without one, writing does nothing."""

    def __init__(self, clock=datetime.now):
        self._clock = clock
        self._file = None
        self.path = None

    @property
    def active(self):
        return self._file is not None

    def start(self, path):
        """Open a new record at ``path``; return False if it cannot be written."""
        self.stop()
        path = Path(path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._file = path.open(
                "w",
                encoding="utf-8",
                errors="backslashreplace",
                newline="\n",
            )
        except OSError:
            self._file = None
            return False
        self.path = path
        self.write(f"Registro de la ejecución · {self._clock():%Y-%m-%d %H:%M:%S}")
        return True

    def write(self, text):
        """Append ``text``, one line per line, each with the time."""
        if self._file is None:
            return
        stamp = f"[{self._clock():%H:%M:%S}]"
        try:
            for line in str(text).split("\n"):
                line = line.rstrip()
                self._file.write(f"{stamp} {line}\n" if line else "\n")
            self._file.flush()
        except (OSError, ValueError):
            self._close_quietly()

    def stop(self):
        self._close_quietly()
        self.path = None

    def _close_quietly(self):
        if self._file is None:
            return
        try:
            self._file.close()
        except OSError:
            pass
        self._file = None


# The record of the current execution (one process runs one execution).
RUN_LOG = RunLog()
