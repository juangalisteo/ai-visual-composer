from dataclasses import dataclass
import math


@dataclass(frozen=True)
class TypewriterStep:
    start: int
    end: int
    text: str


class TypewriterInterpolator:
    """Reveal every rendered character over its source word interval."""

    def interpolate(self, words, rendered_words, cue_start, cue_end, cursor=False, cursor_char="_"):
        steps = []
        prefix = ""
        previous_end = cue_start
        for source_word, rendered_word in zip(words, rendered_words):
            word_start = max(cue_start, self._milliseconds(source_word.start))
            word_end = min(cue_end, self._milliseconds(source_word.end))
            if word_end <= word_start or not rendered_word:
                continue
            if prefix and previous_end < word_start:
                steps.append(TypewriterStep(
                    previous_end,
                    word_start,
                    self._with_cursor(prefix, cursor, cursor_char),
                ))
            base = f"{prefix} " if prefix else ""
            boundaries = self._boundaries(word_start, word_end, len(rendered_word))
            for index, character in enumerate(rendered_word, start=1):
                del character
                start, end = boundaries[index - 1:index + 1]
                if end <= start:
                    continue
                steps.append(TypewriterStep(
                    start,
                    end,
                    self._with_cursor(base + rendered_word[:index], cursor, cursor_char),
                ))
            prefix = base + rendered_word
            previous_end = word_end
        if prefix and previous_end < cue_end:
            steps.append(TypewriterStep(
                previous_end,
                cue_end,
                self._with_cursor(prefix, cursor, cursor_char),
            ))
        return tuple(steps)

    @staticmethod
    def _boundaries(start, end, characters):
        return tuple(
            int(math.floor(start + (end - start) * index / characters + 0.5))
            for index in range(characters + 1)
        )

    @staticmethod
    def _milliseconds(seconds):
        return int(math.floor(float(seconds) * 1000.0 + 0.5))

    @staticmethod
    def _with_cursor(text, cursor, cursor_char):
        return f"{text}{cursor_char}" if cursor else text
