from dataclasses import dataclass
import json
import math
from pathlib import Path
import re


REPETITION_IN_SILENCE = "repetition_in_silence"
REPETITION_WITHOUT_SPEECH = "repetition_without_speech"


@dataclass(frozen=True)
class WhisperRepetitionFilter:
    """Drop Whisper segments that repeat earlier text outside real speech.

    Repetition in silence: a segment is discarded when it is too short to
    be spoken (under ``max_seconds_per_word`` per word), it comes after the
    last kept speech or Whisper marked its window as no speech, and its
    words repeat an earlier segment.

    Repetition without speech: a segment is also discarded when it comes
    after the last kept speech, Whisper marked its window as no speech, its
    mean word probability is under ``max_mean_word_probability``, and its
    words (at least ``min_repeated_words``) appear together, in order,
    inside an earlier segment. It does not look at the audio level, so
    background music or noise neither causes nor prevents a discard.
    """

    max_seconds_per_word: float = 0.05
    max_mean_word_probability: float = 0.5
    min_repeated_words: int = 2

    def __post_init__(self):
        value = self.max_seconds_per_word
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("max_seconds_per_word must be a number")
        if not math.isfinite(value) or value <= 0:
            raise ValueError("max_seconds_per_word must be positive")
        value = self.max_mean_word_probability
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("max_mean_word_probability must be a number")
        if not math.isfinite(value) or not 0 < value <= 1:
            raise ValueError(
                "max_mean_word_probability must be in (0, 1]"
            )
        value = self.min_repeated_words
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("min_repeated_words must be an int")
        if value < 1:
            raise ValueError("min_repeated_words must be at least 1")

    def discarded_indexes(self, segments, no_speech_threshold):
        """Return the indexes of the native segments to discard."""
        return tuple(self.discard_reasons(segments, no_speech_threshold))

    def discard_reasons(self, segments, no_speech_threshold):
        """Return {native segment index: reason}, by index, to discard."""
        spoken = self._spoken_indexes(segments)
        reasons = {}
        after_last_speech = True
        for position in reversed(range(len(spoken))):
            segment = segments[spoken[position]]
            reason = self._reason(
                segment,
                [segments[index] for index in spoken[:position]],
                after_last_speech,
                no_speech_threshold,
            )
            if reason is None:
                after_last_speech = False
            else:
                reasons[spoken[position]] = reason
        return dict(sorted(reasons.items()))

    def apply(self, subtitle_path, timing_path, no_speech_threshold):
        """Remove discarded segments from Whisper's SRT and timing JSON.

        Returns the discarded entries. Both files stay untouched when
        nothing is discarded or the SRT does not match the JSON.
        """
        subtitle_path = Path(subtitle_path)
        timing_path = Path(timing_path)
        try:
            data = json.loads(timing_path.read_text(encoding="utf-8"))
            segments = data["segments"]
            reasons = self.discard_reasons(segments, no_speech_threshold)
        except (OSError, KeyError, TypeError, ValueError, AttributeError):
            return ()
        if not reasons:
            return ()

        with subtitle_path.open(encoding="utf-8", newline="") as file:
            content = file.read()
        newline = "\r\n" if "\r\n" in content else "\n"
        blocks = [
            block
            for block in re.split(r"\r?\n\s*\r?\n", content.strip())
            if block.strip()
        ]
        # Whisper writes one SRT cue per segment with words, in order.
        spoken = self._spoken_indexes(segments)
        if len(blocks) != len(spoken):
            return ()
        cue_of_segment = dict(zip(spoken, blocks))
        for index in reasons:
            cue_text = " ".join(cue_of_segment[index].splitlines()[2:])
            if self._normalized(cue_text.split()) != self._segment_words(
                segments[index]
            ):
                return ()

        kept_blocks = [
            block
            for index, block in zip(spoken, blocks)
            if index not in reasons
        ]
        discarded = tuple(
            {"reason": reason, "segment": segments[index]}
            for index, reason in reasons.items()
        )
        kept_segments = [
            segment
            for index, segment in enumerate(segments)
            if index not in reasons
        ]
        data["segments"] = kept_segments
        data["text"] = "".join(
            segment.get("text", "") for segment in kept_segments
        )
        data["discarded_segments"] = [
            *data.get("discarded_segments", []),
            *discarded,
        ]

        with subtitle_path.open("w", encoding="utf-8", newline="") as file:
            file.write(
                "".join(
                    newline.join([str(number), *block.splitlines()[1:]])
                    + newline * 2
                    for number, block in enumerate(kept_blocks, start=1)
                )
            )
        timing_path.write_text(json.dumps(data), encoding="utf-8")
        return discarded

    @staticmethod
    def _spoken_indexes(segments):
        return [
            index
            for index, segment in enumerate(segments)
            if segment.get("words")
        ]

    def _reason(
        self,
        segment,
        earlier_segments,
        after_last_speech,
        no_speech_threshold,
    ):
        if (
            self._too_short(segment)
            and (
                after_last_speech
                or self._no_speech(segment, no_speech_threshold)
            )
            and self._repeats_earlier(segment, earlier_segments)
        ):
            return REPETITION_IN_SILENCE
        if (
            after_last_speech
            and self._no_speech(segment, no_speech_threshold)
            and self._low_confidence(segment)
            and self._repeats_inside_earlier(segment, earlier_segments)
        ):
            return REPETITION_WITHOUT_SPEECH
        return None

    def _too_short(self, segment):
        words = segment["words"]
        duration = float(words[-1]["end"]) - float(words[0]["start"])
        return duration < self.max_seconds_per_word * len(words)

    @staticmethod
    def _no_speech(segment, no_speech_threshold):
        probability = segment.get("no_speech_prob")
        return probability is not None and probability > no_speech_threshold

    @classmethod
    def _repeats_earlier(cls, segment, earlier_segments):
        words = cls._segment_words(segment)
        return bool(words) and any(
            cls._segment_words(earlier) == words
            for earlier in earlier_segments
        )

    def _low_confidence(self, segment):
        probabilities = [
            word.get("probability") for word in segment["words"]
        ]
        if not all(
            isinstance(probability, (int, float))
            and not isinstance(probability, bool)
            for probability in probabilities
        ):
            return False
        mean = sum(probabilities) / len(probabilities)
        return mean < self.max_mean_word_probability

    def _repeats_inside_earlier(self, segment, earlier_segments):
        words = self._segment_words(segment)
        size = len(words)
        return size >= self.min_repeated_words and any(
            earlier[start:start + size] == words
            for earlier in map(self._segment_words, earlier_segments)
            for start in range(len(earlier) - size + 1)
        )

    @classmethod
    def _segment_words(cls, segment):
        return cls._normalized(word["word"] for word in segment["words"])

    @staticmethod
    def _normalized(words):
        # Same word comparison as the ASS word effects: case and
        # punctuation do not count.
        normalized = (
            "".join(
                character
                for character in str(word).casefold()
                if character.isalnum()
            )
            for word in words
        )
        return tuple(word for word in normalized if word)
