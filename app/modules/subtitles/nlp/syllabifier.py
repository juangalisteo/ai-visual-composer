from dataclasses import dataclass
import unicodedata


@dataclass(frozen=True)
class TimedSyllable:
    text: str
    duration_centiseconds: int


class SyllabifierPolicy:
    """Spanish syllable segmentation for continuous ASS karaoke rendering."""

    _VOWELS = frozenset("aeiou\u00e1\u00e9\u00ed\u00f3\u00fa\u00fc")
    _WEAK_VOWELS = frozenset("iu\u00fc")
    _ONSET_PAIRS = frozenset((
        "bl", "br", "ch", "cl", "cr", "dr", "fl", "fr", "gl", "gr",
        "kl", "kr", "ll", "pl", "pr", "rr", "tl", "tr",
    ))

    @classmethod
    def from_cue_policy(cls, cue_policy):
        if not isinstance(cue_policy, dict):
            raise TypeError("cue_policy debe ser un diccionario para continuous_karaoke.")
        value = cue_policy.get("syllabify")
        if not isinstance(value, bool):
            raise TypeError("cue_policy.syllabify debe ser booleana.")
        if not value:
            raise ValueError("continuous_karaoke requiere cue_policy.syllabify=true.")
        return cls()

    def syllables(self, text):
        text = str(text)
        start, end = self._letter_bounds(text)
        if start == end:
            return (text,) if text else ()
        prefix = text[:start]
        core = text[start:end]
        suffix = text[end:]
        parts = list(self._split_core(core))
        if not parts:
            return (text,)
        parts[0] = prefix + parts[0]
        parts[-1] += suffix
        return tuple(parts)

    def timed_syllables(self, text, duration_centiseconds):
        duration_centiseconds = int(duration_centiseconds)
        parts = self.syllables(text)
        if not parts:
            return ()
        weights = tuple(max(1, self._letter_count(part)) for part in parts)
        total_weight = sum(weights)
        previous = 0
        timed = []
        for index, (part, weight) in enumerate(zip(parts, weights), start=1):
            boundary = (
                duration_centiseconds
                if index == len(parts)
                else round(duration_centiseconds * sum(weights[:index]) / total_weight)
            )
            timed.append(TimedSyllable(part, boundary - previous))
            previous = boundary
        return tuple(timed)

    def _split_core(self, core):
        nuclei = self._nuclei(core)
        if len(nuclei) <= 1:
            return (core,)
        parts = []
        syllable_start = 0
        for (_, nucleus_end), (next_start, _) in zip(nuclei, nuclei[1:]):
            cluster = core[nucleus_end:next_start]
            split_at = nucleus_end + self._coda_length(cluster)
            parts.append(core[syllable_start:split_at])
            syllable_start = split_at
        parts.append(core[syllable_start:])
        return tuple(part for part in parts if part)

    def _nuclei(self, text):
        nuclei = []
        index = 0
        while index < len(text):
            if not self._is_vowel(text[index]):
                index += 1
                continue
            end = index + 1
            if (
                end + 1 < len(text)
                and self._is_vowel(text[end])
                and self._is_vowel(text[end + 1])
                and self._forms_triphthong(
                    text[index] + text[end] + text[end + 1]
                )
            ):
                end += 2
            elif (
                end < len(text)
                and self._is_vowel(text[end])
                and self._forms_diphthong(text[index] + text[end])
            ):
                end += 1
            nuclei.append((index, end))
            index = end
        return tuple(nuclei)

    def _forms_diphthong(self, pair):
        first, second = (self._normalise_vowel(item) for item in pair)
        return not (self._is_strong(first) and self._is_strong(second)) and not (
            first in "\u00ed\u00fa" or second in "\u00ed\u00fa"
        )

    def _forms_triphthong(self, triple):
        first, middle, last = (self._normalise_vowel(item) for item in triple)
        return (
            first in self._WEAK_VOWELS
            and self._is_strong(middle)
            and last in self._WEAK_VOWELS
        )

    def _coda_length(self, cluster):
        normalized = cluster.casefold()
        length = len(normalized)
        if length <= 1:
            return 0
        if length == 2:
            return 0 if normalized in self._ONSET_PAIRS else 1
        if length == 3:
            return 1 if normalized[-2:] in self._ONSET_PAIRS else 2
        return max(1, length - 2)

    @classmethod
    def _letter_bounds(cls, text):
        start = 0
        end = len(text)
        while start < end and not text[start].isalpha():
            start += 1
        while end > start and not text[end - 1].isalpha():
            end -= 1
        return start, end

    @classmethod
    def _letter_count(cls, text):
        return sum(character.isalpha() for character in text)

    @classmethod
    def _is_vowel(cls, character):
        return cls._normalise_vowel(character) in cls._VOWELS

    @staticmethod
    def _normalise_vowel(character):
        return unicodedata.normalize("NFC", character).casefold()

    @classmethod
    def _is_strong(cls, vowel):
        return vowel in cls._VOWELS - cls._WEAK_VOWELS
