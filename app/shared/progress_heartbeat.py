"""Periodic progress line while one long step runs, such as a WAN clip.

The step itself runs untouched in the calling thread; a helper thread only
prints «<label> · <elapsed>» every ``interval_seconds`` until it ends.
"""

import threading
import time

from app.shared.progress_logger import ProgressLogger


def format_elapsed(seconds) -> str:
    """Whole seconds for the terminal: «45 s», «1 min», «1 min 30 s»."""
    total = max(0, round(float(seconds)))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    parts = []
    if hours:
        parts.append(f"{hours} h")
    if hours or minutes:
        parts.append(f"{minutes} min")
    if secs or not parts:
        parts.append(f"{secs} s")
    return " ".join(parts)


class ProgressHeartbeat:
    """Context manager: prints the elapsed time of ``label`` periodically.

    ``interval_seconds`` comes from configuration; ``None`` prints nothing.
    ``clock``, ``emit`` and ``wait`` are injectable for tests.
    """

    def __init__(
        self,
        label,
        interval_seconds,
        *,
        clock=None,
        emit=None,
        wait=None,
    ):
        self.label = str(label)
        self.interval_seconds = interval_seconds
        self._clock = clock or time.perf_counter
        self._emit = emit or ProgressLogger.info
        self._stop = threading.Event()
        self._wait = wait or self._stop.wait
        self._thread = None
        self._start = None

    def __enter__(self):
        self._start = self._clock()
        if self.interval_seconds is not None:
            self._thread = threading.Thread(
                target=self.run,
                name="progress-heartbeat",
                daemon=True,
            )
            self._thread.start()
        return self

    def __exit__(self, exc_type, exc, traceback):
        self._stop.set()
        if self._thread is not None:
            self._thread.join()
        return False

    def elapsed(self) -> float:
        return self._clock() - self._start

    def run(self):
        """Print one line per interval until the step ends."""
        while not self._wait(self.interval_seconds):
            if self._stop.is_set():
                return
            self._emit(
                f"{self.label} · {format_elapsed(self.elapsed())}"
            )
