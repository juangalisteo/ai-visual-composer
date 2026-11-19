"""Length budget of a script generated from a topic.

``PromptEngine`` computes the budget from the requested duration and the
selected voice's pacing, writes it into the prompt and hands it to
``ScriptBuilder`` as data. Nobody reads it back from the prompt text.
"""

from dataclasses import dataclass
import math


# Accepted deviation from the requested duration: ±10 % (owner decision P1, phase I).
DURATION_TOLERANCE = 0.10


def duration_fits(seconds, target_seconds) -> bool:
    """True when ``seconds`` is within the accepted deviation of ``target_seconds``."""
    target_seconds = float(target_seconds)
    return abs(float(seconds) - target_seconds) <= (
        target_seconds * DURATION_TOLERANCE + 1e-9
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
    """Requested duration of one script and the word range asked for it."""

    duration_seconds: float
    target_words: int
    min_words: int
    max_words: int
    pacing: SpeechPacing

    def __post_init__(self):
        if not isinstance(self.pacing, SpeechPacing):
            raise TypeError("pacing debe ser SpeechPacing.")

    @classmethod
    def for_duration(cls, duration_seconds, pacing):
        duration_seconds = _positive_number(duration_seconds, "duration")
        if not isinstance(pacing, SpeechPacing):
            raise TypeError("pacing debe ser SpeechPacing.")
        return cls._around(
            duration_seconds=duration_seconds,
            target_words=duration_seconds * pacing.words_per_second,
            pacing=pacing,
        )

    @classmethod
    def _around(cls, *, duration_seconds, target_words, pacing):
        target = max(1, round(target_words))
        minimum = max(1, round(target * (1 - DURATION_TOLERANCE)))
        maximum = max(minimum, round(target * (1 + DURATION_TOLERANCE)))
        return cls(
            duration_seconds=duration_seconds,
            target_words=target,
            min_words=minimum,
            max_words=maximum,
            pacing=pacing,
        )

    def estimate_seconds(self, script) -> float:
        """How long ``script`` should sound with the voice's pacing."""
        return self.pacing.estimate_seconds(script)

    def deviation(self, seconds) -> float:
        """Signed relative deviation of ``seconds`` from the requested duration."""
        return (float(seconds) - self.duration_seconds) / self.duration_seconds

    def fits(self, seconds) -> bool:
        return duration_fits(seconds, self.duration_seconds)

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
        )


@dataclass(frozen=True)
class ScriptRequest:
    """Prompt of a generated script together with its length budget."""

    prompt: str
    length: ScriptLengthBudget
