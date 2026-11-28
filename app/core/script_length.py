"""Length budget of a script generated from a topic.

``PromptEngine`` computes the budget from the requested duration and the
selected voice's pacing, writes it into the prompt and hands it to
``ScriptBuilder`` as data. Nobody reads it back from the prompt text.
"""

from dataclasses import dataclass
import math
from typing import Mapping

from app.shared.operational_error import create_operational_error
from app.shared.screen_number import screen_decimal


# Where the margin is declared: config/ai.json, section of the topic script.
_AI_CONFIG_RESOURCE = "config/ai.json"
_MARGIN_KEY = "script.duration_margin"


@dataclass(frozen=True)
class DurationMargin:
    """Accepted deviation of a topic script's voice from the requested duration.

    ``below`` and ``above`` are fractions of the requested duration (0.10 is
    10 %). ``above`` set to ``None`` means there is no upper limit: a longer
    voice is always accepted. Declared in ``config/ai.json``
    (``script.duration_margin``); the code has no default.
    """

    below: float
    above: float | None

    def __post_init__(self):
        object.__setattr__(self, "below", _fraction(self.below, "below"))
        if self.above is not None:
            object.__setattr__(self, "above", _fraction(self.above, "above"))

    def minimum_seconds(self, target_seconds) -> float:
        return float(target_seconds) * (1 - self.below)

    def maximum_seconds(self, target_seconds) -> float | None:
        if self.above is None:
            return None
        return float(target_seconds) * (1 + self.above)

    def shortfall(self, seconds, target_seconds) -> float:
        """Seconds that ``seconds`` lies outside the margin; 0 when it fits."""
        seconds = float(seconds)
        minimum = self.minimum_seconds(target_seconds)
        if seconds < minimum - 1e-9:
            return minimum - seconds
        maximum = self.maximum_seconds(target_seconds)
        if maximum is not None and seconds > maximum + 1e-9:
            return seconds - maximum
        return 0.0

    def fits(self, seconds, target_seconds) -> bool:
        return self.shortfall(seconds, target_seconds) == 0.0

    def describe(self) -> str:
        """The margin for the terminal, e.g. «-10 %, sin tope por arriba»."""
        below = f"-{_percent_text(self.below)} %"
        if self.above is None:
            return f"{below}, sin tope por arriba"
        return f"{below} / +{_percent_text(self.above)} %"


def script_duration_margin(ai_config) -> DurationMargin:
    """Margin declared in ``config/ai.json`` for scripts generated from a topic.

    Missing or invalid: CONFIG error in Spanish naming the file and the key.
    """
    section = (
        ai_config.get("script")
        if isinstance(ai_config, Mapping)
        else None
    )
    value = (
        section.get("duration_margin")
        if isinstance(section, Mapping)
        else None
    )
    if value is None:
        raise _margin_error(
            f"falta «{_MARGIN_KEY}», el margen aceptado para la duración de "
            "un guion generado por tema."
        )
    if not isinstance(value, Mapping) or set(value) != {"below", "above"}:
        raise _margin_error(
            f"«{_MARGIN_KEY}» debe ser un objeto con «below» y «above» "
            "(y nada más)."
        )
    try:
        return DurationMargin(below=value["below"], above=value["above"])
    except (TypeError, ValueError) as error:
        raise _margin_error(str(error)) from error


def _fraction(value, name: str) -> float:
    message = (
        f"«{_MARGIN_KEY}.{name}» debe ser un número de 0 a 1 sin llegar a 1 "
        "(0.10 es un 10 %)."
    )
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(message)
    if not 0 <= value < 1:  # also rejects nan and infinity
        raise ValueError(message)
    return float(value)


def _percent_text(fraction: float) -> str:
    return screen_decimal(fraction * 100)


def _margin_error(message):
    return create_operational_error(
        family="CONFIG",
        user_message=(
            f"Configuración del guion no válida en {_AI_CONFIG_RESOURCE}: "
            f"{message}"
        ),
        recommended_action=(
            f"Declara en {_AI_CONFIG_RESOURCE}, sección «script», "
            "«duration_margin» con «below» (p. ej. 0.10) y «above» "
            "(un número o null, sin tope) y vuelve a intentarlo."
        ),
        operation="Preparar el guion",
        resource=_AI_CONFIG_RESOURCE,
        technical_metadata={"key": _MARGIN_KEY},
    )


def count_letters(text) -> int:
    """Letters that will be read aloud; spaces, digits and punctuation do not count."""
    return sum(1 for character in str(text) if character.isalpha())


def _positive_number(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} debe ser un número.")
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} debe ser un número mayor que cero.")
    return float(value)


@dataclass(frozen=True)
class SpeechPacing:
    """Reading rate measured for one voice and declared in its voice document.

    ``letters_per_second`` estimates how long a written script will sound
    (letters vary half as much as words between texts). ``words_per_second``
    only turns a duration into the number of words asked of the language
    model, which cannot count letters.
    """

    letters_per_second: float
    words_per_second: float

    def __post_init__(self):
        object.__setattr__(
            self,
            "letters_per_second",
            _positive_number(self.letters_per_second, "letters_per_second"),
        )
        object.__setattr__(
            self,
            "words_per_second",
            _positive_number(self.words_per_second, "words_per_second"),
        )

    def estimate_seconds(self, text) -> float:
        return count_letters(text) / self.letters_per_second


@dataclass(frozen=True)
class ScriptLengthBudget:
    """Requested duration of one script and the word range asked for it.

    ``max_words`` is ``None`` when the margin has no upper limit.
    """

    duration_seconds: float
    target_words: int
    min_words: int
    max_words: int | None
    pacing: SpeechPacing
    margin: DurationMargin

    def __post_init__(self):
        if not isinstance(self.pacing, SpeechPacing):
            raise TypeError("pacing debe ser SpeechPacing.")
        if not isinstance(self.margin, DurationMargin):
            raise TypeError("margin debe ser DurationMargin.")

    @classmethod
    def for_duration(cls, duration_seconds, pacing, margin):
        duration_seconds = _positive_number(duration_seconds, "duration")
        if not isinstance(pacing, SpeechPacing):
            raise TypeError("pacing debe ser SpeechPacing.")
        return cls._around(
            duration_seconds=duration_seconds,
            target_words=duration_seconds * pacing.words_per_second,
            pacing=pacing,
            margin=margin,
        )

    @classmethod
    def _around(cls, *, duration_seconds, target_words, pacing, margin):
        target = max(1, round(target_words))
        minimum = max(1, round(target * (1 - margin.below)))
        maximum = (
            None
            if margin.above is None
            else max(minimum, round(target * (1 + margin.above)))
        )
        return cls(
            duration_seconds=duration_seconds,
            target_words=target,
            min_words=minimum,
            max_words=maximum,
            pacing=pacing,
            margin=margin,
        )

    def estimate_seconds(self, script) -> float:
        """How long ``script`` should sound with the voice's pacing."""
        return self.pacing.estimate_seconds(script)

    def deviation(self, seconds) -> float:
        """Signed relative deviation of ``seconds`` from the requested duration."""
        return (float(seconds) - self.duration_seconds) / self.duration_seconds

    def fits(self, seconds) -> bool:
        return self.margin.fits(seconds, self.duration_seconds)

    def rescaled(self, *, words, observed_seconds):
        """Same duration; word range scaled by what ``words`` really took."""
        words = int(words)
        observed_seconds = float(observed_seconds)
        if words <= 0 or observed_seconds <= 0:
            return self
        return self._around(
            duration_seconds=self.duration_seconds,
            target_words=words * self.duration_seconds / observed_seconds,
            pacing=self.pacing,
            margin=self.margin,
        )


@dataclass(frozen=True)
class ScriptRequest:
    """Prompt of a generated script together with its length budget."""

    prompt: str
    length: ScriptLengthBudget
