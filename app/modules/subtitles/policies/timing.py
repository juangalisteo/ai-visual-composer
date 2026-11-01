from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
import re


@dataclass(frozen=True)
class WordTiming:
    text: str
    start: float
    end: float
    confidence: float | None = None
    source: str = ""

    def __post_init__(self):
        text = " ".join(
            str(self.text).split()
        ).strip()

        if not text:
            raise ValueError(
                "WordTiming.text no puede estar vacío."
            )

        start = float(
            self.start
        )
        end = float(
            self.end
        )

        if start < 0:
            raise ValueError(
                "WordTiming.start no puede ser negativo."
            )

        if end < start:
            raise ValueError(
                "WordTiming.end no puede ser anterior a start."
            )

        object.__setattr__(
            self,
            "text",
            text
        )
        object.__setattr__(
            self,
            "start",
            start
        )
        object.__setattr__(
            self,
            "end",
            end
        )


@dataclass(frozen=True)
class SpeechSegment:
    start: float
    end: float
    words: tuple[WordTiming, ...]

    def __post_init__(self):
        start = float(
            self.start
        )
        end = float(
            self.end
        )

        if start < 0:
            raise ValueError(
                "SpeechSegment.start no puede ser negativo."
            )

        if end < start:
            raise ValueError(
                "SpeechSegment.end no puede ser anterior a start."
            )

        _validate_temporal_order(
            self.words
        )

        if self.words:
            first = self.words[0]
            last = self.words[-1]

            if first.start < start:
                start = first.start

            if last.end > end:
                end = last.end

        object.__setattr__(
            self,
            "start",
            start
        )
        object.__setattr__(
            self,
            "end",
            end
        )


@dataclass(frozen=True)
class SubtitleTiming:
    source: str
    segments: tuple[SpeechSegment, ...]
    duration: float | None = None
    reliability: str = "unknown"
    fallback_reason: str | None = None
    # Ordered ``(start, end)`` silences, in seconds, that the voice backend
    # wrote into the transcribed audio; see ``fit_words_to_voice_pauses``.
    voice_pauses: tuple[tuple[float, float], ...] = ()

    @property
    def words(
        self
    ) -> tuple[WordTiming, ...]:
        return tuple(
            word
            for segment in self.segments
            for word in segment.words
        )

    @property
    def word_count(
        self
    ) -> int:
        return len(
            self.words
        )

    def is_usable(
        self
    ) -> bool:
        return self.word_count > 0


def stretch_zero_duration_cues(
    cues,
    max_extension: float,
    join_words
) -> list:
    """Give a visible duration to timed cues that last zero seconds.

    ``cues`` are ordered ``(start, end, words, payload)`` tuples in seconds;
    the result holds ``(start, end, payload)`` tuples. A cue whose end is
    not after its start (its words have ``end == start``) is stretched up
    to the start of the next cue, at most ``max_extension`` seconds
    (greater than zero); the last cue is stretched by ``max_extension``.

    A cue that still has no room, because the next cue starts at the same
    instant, is not shown on its own, so cues never overlap: its words that
    the next cue does not already show are put in front of it with
    ``join_words(words, payload)``, which returns the next cue's payload.
    The next cue keeps its times. Several such cues in a row are joined in
    order. Other cues are kept unchanged.
    """
    stretched = []
    pending_words = ()

    for position, (start, end, words, payload) in enumerate(cues):
        if pending_words:
            missing_words = tuple(
                word
                for word in pending_words
                if word not in words
            )

            if missing_words:
                payload = join_words(
                    missing_words,
                    payload
                )

        if end <= start:
            end = start + max_extension

            if position + 1 < len(cues):
                end = min(
                    end,
                    cues[position + 1][0]
                )

            if end <= start:
                pending_words += tuple(
                    word
                    for word in words
                    if word not in pending_words
                )
                continue

        pending_words = ()
        stretched.append(
            (start, end, payload)
        )

    return stretched


def text_joiner(format_words):
    """Return a ``join_words`` for text payloads: the formatted words go in
    front of the text, separated by a space."""

    def join_words(words, text):
        prefix = format_words(words)

        return f"{prefix} {text}" if prefix else text

    return join_words


def approximate_word_timings(
    start: float,
    end: float,
    texts
) -> tuple[WordTiming, ...]:
    """Spread a cue's duration over its words, in proportion to the
    characters of each word.

    The words follow one another without gaps: the first starts at
    ``start`` and the last ends at ``end``. Used to render word effects
    when there are no real word times for the cue; the cue keeps its own
    times and text.
    """
    texts = tuple(
        text
        for text in texts
        if str(text).strip()
    )

    if not texts:
        return ()

    lengths = [
        max(1, len(text))
        for text in texts
    ]
    total_length = sum(
        lengths
    )
    duration = end - start
    boundaries = [start]
    cumulative = 0

    for length in lengths[:-1]:
        cumulative += length
        boundaries.append(
            start + duration * cumulative / total_length
        )

    boundaries.append(end)

    return tuple(
        WordTiming(
            text=text,
            start=word_start,
            end=word_end,
            source="approximate"
        )
        for text, word_start, word_end in zip(
            texts,
            boundaries,
            boundaries[1:]
        )
    )


def whisper_timing_path(
    subtitle_path
) -> Path:
    subtitle_path = Path(
        subtitle_path
    )
    return subtitle_path.with_name(
        f"{subtitle_path.stem}_whisper.json"
    )


class WhisperTimingParser:

    def parse(
        self,
        path
    ) -> SubtitleTiming:
        path = Path(
            path
        )

        if not path.exists():
            raise FileNotFoundError(
                f"No existe metadata Whisper: {path}"
            )

        try:
            data = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )
        except json.JSONDecodeError as error:
            raise ValueError(
                "Metadata Whisper inválida."
            ) from error

        raw_segments = data.get(
            "segments",
            []
        )

        if not isinstance(
            raw_segments,
            list
        ):
            raise ValueError(
                "Metadata Whisper sin segments válido."
            )

        segments: list[SpeechSegment] = []

        for raw_segment in raw_segments:
            if not isinstance(
                raw_segment,
                dict
            ):
                continue

            raw_words = raw_segment.get(
                "words",
                []
            )

            if not isinstance(
                raw_words,
                list
            ):
                continue

            words: list[WordTiming] = []

            for raw_word in raw_words:
                if not isinstance(
                    raw_word,
                    dict
                ):
                    continue

                try:
                    words.append(
                        WordTiming(
                            text=raw_word.get(
                                "word",
                                ""
                            ),
                            start=raw_word[
                                "start"
                            ],
                            end=raw_word[
                                "end"
                            ],
                            confidence=raw_word.get(
                                "probability"
                            ),
                            source="whisper"
                        )
                    )
                except (
                    KeyError,
                    TypeError,
                    ValueError
                ) as error:
                    raise ValueError(
                        "Word timestamp Whisper inválido."
                    ) from error

            if not words:
                continue

            segment_start = float(
                raw_segment.get(
                    "start",
                    words[0].start
                )
            )
            segment_end = float(
                raw_segment.get(
                    "end",
                    words[-1].end
                )
            )

            segments.append(
                SpeechSegment(
                    start=segment_start,
                    end=segment_end,
                    words=tuple(words)
                )
            )

        if not segments:
            raise ValueError(
                "Metadata Whisper sin word timestamps usable."
            )

        all_words = tuple(
            word
            for segment in segments
            for word in segment.words
        )
        _validate_temporal_order(
            all_words
        )

        return SubtitleTiming(
            source="whisper",
            segments=tuple(
                segments
            ),
            duration=all_words[-1].end,
            reliability="secondary",
            voice_pauses=_parse_voice_pauses(
                data.get(
                    "voice_pauses",
                    []
                )
            )
        )


class SubtitleTimingResolver:

    def resolve(
        self,
        subtitle_path,
        audio_path=None
    ) -> SubtitleTiming | None:
        del audio_path
        path = whisper_timing_path(subtitle_path)
        if not path.exists():
            return None

        try:
            timing = fit_words_to_voice_pauses(
                WhisperTimingParser().parse(path)
            )
        except (OSError, ValueError):
            return None

        return timing if timing.is_usable() else None


def fit_words_to_voice_pauses(
    timing: SubtitleTiming
) -> SubtitleTiming:
    """Keep the timed words out of the silences the voice backend wrote.

    A word that starts before a pause and ends inside it ends where the pause
    starts; a word that starts inside a pause starts where the pause ends
    (one wholly inside it is left with zero duration there). A word that
    spans the whole pause keeps the side where more of its time lies. Each
    segment then spans its fitted words. Without ``voice_pauses`` the timing
    is returned unchanged.
    """
    if not timing.voice_pauses:
        return timing

    segments = []

    for segment in timing.segments:
        words = tuple(
            _fit_word_to_pauses(
                word,
                timing.voice_pauses
            )
            for word in segment.words
        )

        segments.append(
            SpeechSegment(
                start=words[0].start if words else segment.start,
                end=words[-1].end if words else segment.end,
                words=words
            )
        )

    return replace(
        timing,
        segments=tuple(
            segments
        )
    )


def _fit_word_to_pauses(
    word: WordTiming,
    pauses
) -> WordTiming:
    start = word.start
    end = word.end

    for pause_start, pause_end in pauses:
        if start >= pause_end or end <= pause_start:
            continue

        if start < pause_start and (
            end <= pause_end
            or pause_start - start >= end - pause_end
        ):
            end = pause_start
        else:
            start = pause_end
            end = max(
                end,
                pause_end
            )

    if (start, end) == (word.start, word.end):
        return word

    return replace(
        word,
        start=start,
        end=end
    )


def _parse_voice_pauses(
    raw_pauses
) -> tuple[tuple[float, float], ...]:
    if not isinstance(
        raw_pauses,
        list
    ):
        raise ValueError(
            "Metadata Whisper con voice_pauses inválido."
        )

    pauses = []
    previous_end = None

    for raw_pause in raw_pauses:
        try:
            start = float(
                raw_pause["start"]
            )
            end = float(
                raw_pause["end"]
            )
        except (
            KeyError,
            TypeError,
            ValueError
        ) as error:
            raise ValueError(
                "Metadata Whisper con voice_pauses inválido."
            ) from error

        if (
            start < 0
            or end <= start
            or (previous_end is not None and start < previous_end)
        ):
            raise ValueError(
                "Metadata Whisper con voice_pauses inválido."
            )

        pauses.append(
            (start, end)
        )
        previous_end = end

    return tuple(
        pauses
    )


def parse_srt_blocks(
    blocks
) -> tuple[SpeechSegment, ...]:
    segments: list[SpeechSegment] = []

    for block in blocks:
        lines = str(
            block
        ).strip().splitlines()

        if len(lines) < 3:
            continue

        match = re.match(
            r"(\d{2}:\d{2}:\d{2},\d{3})"
            r"\s*-->\s*"
            r"(\d{2}:\d{2}:\d{2},\d{3})",
            lines[1].strip()
        )

        if not match:
            continue

        text = " ".join(
            " ".join(
                lines[2:]
            ).split()
        ).strip()

        if not text:
            continue

        start = _time_to_seconds(
            match.group(1)
        )
        end = _time_to_seconds(
            match.group(2)
        )

        if end <= start:
            continue

        words = tuple(
            WordTiming(
                text=word,
                start=start,
                end=end,
                source="srt_block"
            )
            for word in text.split()
        )

        segments.append(
            SpeechSegment(
                start=start,
                end=end,
                words=words
            )
        )

    return tuple(
        segments
    )


def count_gaps(
    words,
    threshold
) -> int:
    threshold = float(
        threshold
    )
    count = 0

    for current, following in zip(
        words,
        words[1:]
    ):
        if following.start - current.end >= threshold:
            count += 1

    return count


def _time_to_seconds(
    time_text
) -> float:
    hours, minutes, rest = (
        time_text.split(":")
    )
    seconds, milliseconds = (
        rest.split(",")
    )

    return (
        int(hours) * 3600
        + int(minutes) * 60
        + int(seconds)
        + int(milliseconds) / 1000
    )


def _validate_temporal_order(
    words: tuple[WordTiming, ...]
) -> None:
    previous_end = None

    for word in words:
        if previous_end is not None and word.start < previous_end:
            raise ValueError(
                "Los WordTiming deben estar ordenados y sin solaparse."
            )

        previous_end = word.end
