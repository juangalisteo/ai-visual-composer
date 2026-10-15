"""Adapt neutral TTS word timing to the existing subtitle timing contract."""

from collections.abc import Iterable

from app.modules.audio.tts_contracts import TtsWordTiming
from app.modules.subtitles.policies.timing import (
    SpeechSegment,
    SubtitleTiming,
    WordTiming,
)


class VoiceTimingAdapter:
    """Preserve neutral word timing as one primary subtitle-timing segment."""

    def adapt(
        self,
        word_timings: Iterable[TtsWordTiming] | None,
    ) -> SubtitleTiming | None:
        """Return neutral subtitle timing, or ``None`` when timing is absent."""
        timings = self._validated_timings(word_timings)
        if not timings:
            return None

        words = tuple(self._subtitle_word(timing) for timing in timings)
        segment = SpeechSegment(
            start=words[0].start,
            end=words[-1].end,
            words=words,
        )
        return SubtitleTiming(
            source="tts",
            segments=(segment,),
            duration=segment.end,
            reliability="primary",
        )

    @staticmethod
    def _validated_timings(
        word_timings: Iterable[TtsWordTiming] | None,
    ) -> tuple[TtsWordTiming, ...]:
        if word_timings is None:
            return ()
        timings = tuple(word_timings)
        for timing in timings:
            if not isinstance(timing, TtsWordTiming):
                raise TypeError("word_timings must contain TtsWordTiming values.")
        return timings

    @staticmethod
    def _subtitle_word(timing: object) -> WordTiming:
        if not isinstance(timing, TtsWordTiming):
            raise TypeError("word_timings must contain TtsWordTiming values.")
        return WordTiming(
            text=timing.text,
            start=timing.start_seconds,
            end=timing.end_seconds,
            source="tts",
        )
