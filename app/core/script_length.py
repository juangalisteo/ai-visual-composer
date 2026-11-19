"""Length budget of a script generated from a topic.

``PromptEngine`` computes the budget from the requested duration, writes it
into the prompt and hands it to ``ScriptBuilder`` as data. Nobody reads it
back from the prompt text.
"""

from dataclasses import dataclass
import math


# Accepted deviation from the requested duration: ±10 % (owner decision P1, phase I).
DURATION_TOLERANCE = 0.10


def _positive_number(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} debe ser un número.")
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} debe ser un número mayor que cero.")
    return float(value)


@dataclass(frozen=True)
class ScriptLengthBudget:
    """Requested duration of one script and the word range asked for it."""

    duration_seconds: float
    target_words: int
    min_words: int
    max_words: int

    @classmethod
    def for_duration(cls, duration_seconds, *, words_per_second):
        duration_seconds = _positive_number(duration_seconds, "duration")
        words_per_second = _positive_number(words_per_second, "words_per_second")
        return cls._around(
            duration_seconds=duration_seconds,
            target_words=duration_seconds * words_per_second,
        )

    @classmethod
    def _around(cls, *, duration_seconds, target_words):
        target = max(1, round(target_words))
        minimum = max(1, round(target * (1 - DURATION_TOLERANCE)))
        maximum = max(minimum, round(target * (1 + DURATION_TOLERANCE)))
        return cls(
            duration_seconds=duration_seconds,
            target_words=target,
            min_words=minimum,
            max_words=maximum,
        )

    def accepts_words(self, words: int) -> bool:
        return self.min_words <= int(words) <= self.max_words

    def word_distance(self, words: int) -> int:
        """How far ``words`` is from the target, to keep the closest script."""
        return abs(int(words) - self.target_words)


@dataclass(frozen=True)
class ScriptRequest:
    """Prompt of a generated script together with its length budget."""

    prompt: str
    length: ScriptLengthBudget
