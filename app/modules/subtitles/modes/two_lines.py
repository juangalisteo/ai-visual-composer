"""Balanced two-line subtitle cue capability."""

from app.modules.subtitles.modes.single_line import SingleLineModel
from app.modules.subtitles.modes.three_two_words import ThreeTwoWordsModel
from app.shared.config_contract import require_float, require_int


class TwoLineModel(ThreeTwoWordsModel):
    """Build static one- or two-line cues with balanced visual line lengths."""

    _DEFAULT_BALANCE_RATIO = 0.75

    def __init__(self, config):
        super().__init__(config)
        self.max_lines = require_int(
            config,
            "max_lines",
            "cue_policy.max_lines",
        )
        self.balance_ratio_threshold = (
            require_float(
                config,
                "balance_ratio_threshold",
                "cue_policy.balance_ratio_threshold",
            )
            if "balance_ratio_threshold" in config
            else self._DEFAULT_BALANCE_RATIO
        )

        if self.max_lines != 2:
            raise ValueError(
                "cue_policy.max_lines debe ser exactamente 2 para two_lines."
            )
        if not 0.5 <= self.balance_ratio_threshold <= 1.0:
            raise ValueError(
                "cue_policy.balance_ratio_threshold debe estar entre 0.5 y 1.0."
            )
        if self.fixed_chunk_size is not None:
            raise ValueError(
                "cue_policy.fixed_chunk_size no aplica al modo two_lines."
            )

    def _partition_words(self, words):
        words = tuple(words)
        if not words:
            return []

        chunks = []
        linguistic_group = []
        for word in words:
            linguistic_group.append(word)
            if self._ends_with_boundary_punctuation(word):
                chunks.extend(self._partition_linguistic_group(linguistic_group))
                linguistic_group = []

        if linguistic_group:
            chunks.extend(self._partition_linguistic_group(linguistic_group))
        return chunks

    def _partition_linguistic_group(self, words):
        words = tuple(words)
        chunks = []
        cursor = 0

        while cursor < len(words):
            selected_end = None
            for end in range(len(words), cursor, -1):
                if self._balanced_lines(words[cursor:end]) is not None:
                    selected_end = end
                    break

            chunks.append(words[cursor:selected_end])
            cursor = selected_end

        return chunks

    def _format_words(self, words):
        lines = self._balanced_lines(tuple(words))
        if lines is None:
            raise ValueError(
                "No se puede equilibrar el cue dentro de dos líneas."
            )
        return self.punctuation.apply("\n".join(lines))

    def _balanced_lines(self, words):
        words = tuple(words)
        if not words:
            return None

        text = self._join_words(words)
        # A word longer than the limit goes alone on its line.
        if len(text) <= self.max_chars_per_line or len(words) == 1:
            return (text,)

        candidates = []
        for split_at in range(1, len(words)):
            first_line = self._join_words(words[:split_at])
            second_line = self._join_words(words[split_at:])
            if (
                len(first_line) > self.max_chars_per_line
                or len(second_line) > self.max_chars_per_line
            ):
                continue

            ratio = min(len(first_line), len(second_line)) / max(
                len(first_line), len(second_line)
            )
            if ratio < self.balance_ratio_threshold:
                continue

            candidates.append((
                self._break_penalty(words[:split_at], words[split_at:]),
                -ratio,
                split_at,
                first_line,
                second_line,
            ))

        if not candidates:
            return None

        _, _, _, first_line, second_line = min(candidates)
        return (first_line, second_line)

    @staticmethod
    def _join_words(words):
        return " ".join(
            TwoLineModel._word_text(word)
            for word in words
        )

    @staticmethod
    def _break_penalty(first_words, second_words):
        first = TwoLineModel._normalized_word(first_words[-1])
        second = TwoLineModel._normalized_word(second_words[0])
        penalty = 0
        if first in SingleLineModel.WEAK_ENDS:
            penalty += 2
        if second in SingleLineModel.WEAK_STARTS:
            penalty += 2
        if len(first_words) >= 2:
            ending = " ".join(
                TwoLineModel._normalized_word(word)
                for word in first_words[-2:]
            )
            if ending in SingleLineModel.NATURAL_ENDINGS:
                penalty -= 1
        return penalty

    @staticmethod
    def _normalized_word(word):
        return TwoLineModel._word_text(word).strip().lower().rstrip(
            ".,;:!?…¿¡-—\"'“”‘’«»()[]{}"
        )
