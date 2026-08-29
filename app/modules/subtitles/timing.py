from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any


EDGE_TTS_TICKS_PER_SECOND = 10_000_000


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
                "WordTiming text cannot be empty."
            )

        start = float(
            self.start
        )
        end = float(
            self.end
        )

        if start < 0:
            raise ValueError(
                "WordTiming start cannot be negative."
            )

        if end < start:
            raise ValueError(
                "WordTiming end cannot be before start."
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
                "SpeechSegment start cannot be negative."
            )

        if end < start:
            raise ValueError(
                "SpeechSegment end cannot be before start."
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


def edge_word_boundaries_path(
    audio_path
) -> Path:
    audio_path = Path(
        audio_path
    )
    return audio_path.with_name(
        f"{audio_path.stem}_word_boundaries.jsonl"
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


class EdgeWordBoundaryParser:

    def parse(
        self,
        path
    ) -> SubtitleTiming:
        path = Path(
            path
        )

        if not path.exists():
            raise FileNotFoundError(
                f"No existe metadata Edge TTS: {path}"
            )

        words: list[WordTiming] = []

        for line in path.read_text(
            encoding="utf-8"
        ).splitlines():
            if not line.strip():
                continue

            try:
                item = json.loads(
                    line
                )
            except json.JSONDecodeError as error:
                raise ValueError(
                    "Metadata Edge TTS inválida."
                ) from error

            if item.get("type") != "WordBoundary":
                continue

            text = item.get(
                "text",
                ""
            )
            offset = item.get(
                "offset"
            )
            duration = item.get(
                "duration"
            )

            if offset is None or duration is None:
                raise ValueError(
                    "WordBoundary sin offset o duration."
                )

            start = (
                float(offset)
                / EDGE_TTS_TICKS_PER_SECOND
            )
            end = (
                start
                + float(duration)
                / EDGE_TTS_TICKS_PER_SECOND
            )

            words.append(
                WordTiming(
                    text=text,
                    start=start,
                    end=end,
                    source="edge_tts"
                )
            )

        _validate_temporal_order(
            tuple(words)
        )

        if not words:
            raise ValueError(
                "Metadata Edge TTS sin WordBoundary usable."
            )

        return SubtitleTiming(
            source="edge_tts",
            segments=(
                SpeechSegment(
                    start=words[0].start,
                    end=words[-1].end,
                    words=tuple(words)
                ),
            ),
            duration=words[-1].end,
            reliability="primary"
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
            reliability="secondary"
        )


class SubtitleTimingResolver:

    def resolve(
        self,
        subtitle_path,
        audio_path=None
    ) -> SubtitleTiming | None:
        candidates: list[tuple[str, Path, object]] = []

        if audio_path is not None:
            candidates.append(
                (
                    "edge_tts",
                    edge_word_boundaries_path(
                        audio_path
                    ),
                    EdgeWordBoundaryParser()
                )
            )

        candidates.append(
            (
                "whisper",
                whisper_timing_path(
                    subtitle_path
                ),
                WhisperTimingParser()
            )
        )

        fallback_reasons = []

        for source, path, parser in candidates:
            if not path.exists():
                fallback_reasons.append(
                    f"{source}:missing"
                )
                continue

            try:
                timing = parser.parse(
                    path
                )
            except (
                OSError,
                ValueError
            ) as error:
                fallback_reasons.append(
                    f"{source}:{error}"
                )
                continue

            if timing.is_usable():
                if fallback_reasons:
                    return SubtitleTiming(
                        source=timing.source,
                        segments=timing.segments,
                        duration=timing.duration,
                        reliability=timing.reliability,
                        fallback_reason="; ".join(
                            fallback_reasons
                        )
                    )

                return timing

            fallback_reasons.append(
                f"{source}:empty"
            )

        return None


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
                source="legacy_srt"
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
                "WordTiming entries must be ordered and non-overlapping."
            )

        previous_end = word.end
