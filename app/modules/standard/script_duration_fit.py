"""Fit a topic script to its requested duration with the real voice.

After the voice is generated, its duration is measured. When it falls
outside the margin declared in ``config/ai.json`` (``script.duration_margin``;
owner decision T0: up to 10 % shorter, no upper limit), Ollama is asked once
for an adjusted script and the voice is generated again. Of the two
well-formed scripts, the one closer to the margin is kept; if it is still
outside, the terminal says so in one line and the run goes on. There is no
loop and no timeout (``AGENTS.md`` §8). Only scripts generated from a topic go
through here, never a script written by the user.
"""

from dataclasses import dataclass
import os
from pathlib import Path

from app.modules.script.models import InvalidScriptOutputError
from app.shared.operation_warnings import OperationWarning
from app.shared.progress_logger import ProgressLogger


_OPERATION = "Ajustar la duración del guion"
_CANDIDATE_SUFFIX = "_ajuste"


@dataclass(frozen=True)
class DurationFitResult:
    """Script and voice kept after the fit."""

    script_text: str
    voice_pauses: tuple
    voice_seconds: float
    adjustment_requested: bool = False
    adjustment_adopted: bool = False


class ScriptDurationFit:
    """Measure the voice and ask once for an adjusted script when it is off.

    Collaborators are injected:
    - ``measure_seconds(path) -> float``: duration of an audio file.
    - ``adjust_script(previous_script, measured_seconds, output_path) -> str``:
      one request for the rewritten script, written at ``output_path``.
    - ``synthesize_voice(text, output_path) -> (path, pauses)``.
    - ``margin``: the ``DurationMargin`` declared in configuration.
    """

    def __init__(
        self,
        *,
        measure_seconds,
        adjust_script,
        synthesize_voice,
        margin,
        warnings=None,
    ):
        self._margin = margin
        self._measure_seconds = measure_seconds
        self._adjust_script = adjust_script
        self._synthesize_voice = synthesize_voice
        self._warnings = warnings

    def fit(
        self,
        *,
        script_text,
        target_seconds,
        script_path,
        voice_path,
        voice_pauses,
        adjustment_allowed=True,
    ) -> DurationFitResult:
        """Keep the voice or adjust once.

        ``adjustment_allowed`` is False when Ollama was already asked to fix
        the length before the voice: the single attempt is spent, so a voice
        outside the margin is only reported.
        """
        target_seconds = float(target_seconds)
        script_path = Path(script_path)
        voice_path = Path(voice_path)
        first = DurationFitResult(
            script_text=script_text,
            voice_pauses=tuple(voice_pauses),
            voice_seconds=float(self._measure_seconds(voice_path)),
        )
        if self._margin.fits(first.voice_seconds, target_seconds):
            return first
        if not adjustment_allowed:
            self._warn(
                f"{self._outside_margin(first.voice_seconds, target_seconds)} "
                "Ya se pidió a Ollama una corrección de extensión antes de "
                "la voz: se sigue con este guion."
            )
            return first

        ProgressLogger.info(
            f"La voz dura {_seconds(first.voice_seconds)} s y se pidieron "
            f"{_seconds(target_seconds)} s "
            f"({_percent(first.voice_seconds, target_seconds)}). "
            "Se pide a Ollama un guion más "
            f"{'corto' if first.voice_seconds > target_seconds else 'largo'}"
            " (una sola vez)."
        )
        candidate_script_path = _candidate_path(script_path)
        candidate_voice_path = _candidate_path(voice_path)
        try:
            chosen = self._try_adjustment(
                first=first,
                target_seconds=target_seconds,
                script_path=script_path,
                voice_path=voice_path,
                candidate_script_path=candidate_script_path,
                candidate_voice_path=candidate_voice_path,
            )
        finally:
            for leftover in (candidate_script_path, candidate_voice_path):
                leftover.unlink(missing_ok=True)

        if not self._margin.fits(chosen.voice_seconds, target_seconds):
            self._warn(
                f"{self._outside_margin(chosen.voice_seconds, target_seconds)} "
                "Se usa el guion que más se acerca."
            )
        return chosen

    def _outside_margin(self, seconds, target_seconds) -> str:
        return (
            f"La voz final dura {_seconds(seconds)} s y se pidieron "
            f"{_seconds(target_seconds)} s "
            f"({_percent(seconds, target_seconds)}), fuera del margen "
            f"({self._margin.describe()})."
        )

    def _try_adjustment(
        self,
        *,
        first,
        target_seconds,
        script_path,
        voice_path,
        candidate_script_path,
        candidate_voice_path,
    ) -> DurationFitResult:
        try:
            adjusted_text = self._adjust_script(
                previous_script=first.script_text,
                measured_seconds=first.voice_seconds,
                output_path=candidate_script_path,
            )
        except InvalidScriptOutputError:
            ProgressLogger.info(
                "Ollama no devolvió un guion ajustado válido. "
                "Se mantiene el primero."
            )
            return _requested(first, adopted=False)

        adjusted_voice_path, adjusted_pauses = self._synthesize_voice(
            adjusted_text,
            candidate_voice_path,
        )
        adjusted_seconds = float(self._measure_seconds(adjusted_voice_path))
        if self._margin.shortfall(
            adjusted_seconds, target_seconds
        ) >= self._margin.shortfall(first.voice_seconds, target_seconds):
            ProgressLogger.info(
                "Se mantiene el primer guion: con el ajustado la voz dura "
                f"{_seconds(adjusted_seconds)} s."
            )
            return _requested(first, adopted=False)

        os.replace(adjusted_voice_path, voice_path)
        os.replace(candidate_script_path, script_path)
        ProgressLogger.info(
            "Se usa el guion ajustado: la voz dura "
            f"{_seconds(adjusted_seconds)} s."
        )
        return DurationFitResult(
            script_text=adjusted_text,
            voice_pauses=tuple(adjusted_pauses),
            voice_seconds=adjusted_seconds,
            adjustment_requested=True,
            adjustment_adopted=True,
        )

    def _warn(self, message):
        ProgressLogger.warning(message)
        if self._warnings is not None:
            self._warnings.add(
                OperationWarning(
                    family="DEGRADATION",
                    user_message=message,
                    operation=_OPERATION,
                )
            )


def _requested(result, *, adopted) -> DurationFitResult:
    return DurationFitResult(
        script_text=result.script_text,
        voice_pauses=result.voice_pauses,
        voice_seconds=result.voice_seconds,
        adjustment_requested=True,
        adjustment_adopted=adopted,
    )


def _candidate_path(path: Path) -> Path:
    return path.with_name(f"{path.stem}{_CANDIDATE_SUFFIX}{path.suffix}")


def _seconds(value) -> str:
    return f"{float(value):.1f}".replace(".", ",")


def _percent(seconds, target_seconds) -> str:
    deviation = (seconds - target_seconds) / target_seconds * 100
    return f"{deviation:+.0f} %"
