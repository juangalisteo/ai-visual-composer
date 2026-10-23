from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.modules.subtitles.policies.timing import (
    WordTiming,
    stretch_zero_duration_cues,
)


@dataclass(frozen=True)
class SubtitleCue:
    text: str
    start: float
    end: float
    words: tuple[WordTiming, ...]

    def __post_init__(self):
        text = " ".join(
            str(self.text).split()
        ).strip()

        if not text:
            raise ValueError(
                "SubtitleCue text cannot be empty."
            )

        start = float(
            self.start
        )
        end = float(
            self.end
        )

        if start < 0:
            raise ValueError(
                "SubtitleCue start cannot be negative."
            )

        if end <= start:
            raise ValueError(
                "SubtitleCue end must be after start."
            )

        if not self.words:
            raise ValueError(
                "SubtitleCue must contain at least one source word."
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
class MicroCueStats:
    detected: int = 0
    merged: int = 0
    extended: int = 0


@dataclass(frozen=True)
class MicroCueResult:
    cues: tuple[SubtitleCue, ...]
    stats: MicroCueStats


class MicroCuePolicy:

    def __init__(
        self,
        enabled=True,
        fps=30,
        min_frames=1,
        min_display_seconds=0.05,
        significant_gap_threshold=0.35,
        merge_preference="next"
    ):
        self.enabled = bool(
            enabled
        )
        self.fps = float(
            fps
        )
        self.min_frames = float(
            min_frames
        )
        self.min_display_seconds = float(
            min_display_seconds
        )
        self.significant_gap_threshold = float(
            significant_gap_threshold
        )
        self.merge_preference = str(
            merge_preference
        ).strip().lower()

        if self.fps <= 0:
            raise ValueError(
                "MicroCuePolicy fps must be greater than zero."
            )

        if self.min_frames <= 0:
            raise ValueError(
                "MicroCuePolicy min_frames must be greater than zero."
            )

        if self.min_display_seconds <= 0:
            raise ValueError(
                "MicroCuePolicy min_display_seconds must be greater than zero."
            )

        if self.significant_gap_threshold <= 0:
            raise ValueError(
                "MicroCuePolicy significant_gap_threshold must be greater than zero."
            )

        if self.merge_preference not in {
            "next",
            "previous"
        }:
            raise ValueError(
                "MicroCuePolicy merge_preference must be next or previous."
            )

    @property
    def minimum_visual_duration(
        self
    ) -> float:
        technical_minimum = (
            self.min_frames
            / self.fps
        )

        return max(
            technical_minimum,
            self.min_display_seconds
        )

    def apply(
        self,
        words: tuple[WordTiming, ...],
        formatter: Callable[[str], str]
    ) -> MicroCueResult:
        prepared_words = tuple(
            word
            for word in words
            if formatter(word.text)
        )

        if not prepared_words:
            return MicroCueResult(
                cues=(),
                stats=MicroCueStats()
            )

        if not self.enabled:
            return MicroCueResult(
                cues=tuple(
                    SubtitleCue(
                        text=" ".join(
                            formatter(
                                word.text
                            )
                            for word in cue_words
                        ),
                        start=start,
                        end=end,
                        words=cue_words
                    )
                    for start, end, cue_words in stretch_zero_duration_cues(
                        tuple(
                            (word.start, word.end, (word,), (word,))
                            for word in prepared_words
                        ),
                        self.significant_gap_threshold,
                        lambda missing_words, cue_words: (
                            missing_words + cue_words
                        )
                    )
                ),
                stats=MicroCueStats()
            )

        cues: list[SubtitleCue] = []
        detected = 0
        merged = 0
        extended = 0
        index = 0

        while index < len(prepared_words):
            word = prepared_words[index]

            if not self._is_micro(
                word
            ):
                cues.append(
                    self._cue_from_words(
                        (word,),
                        formatter
                    )
                )
                index += 1
                continue

            detected += 1

            word_group = [
                word
            ]
            next_index = index + 1

            while (
                next_index < len(prepared_words)
                and self._can_merge(
                    word_group[-1],
                    prepared_words[next_index]
                )
                and self._group_duration(
                    word_group
                ) < self.minimum_visual_duration
            ):
                if self._is_micro(
                    prepared_words[next_index]
                ):
                    detected += 1

                word_group.append(
                    prepared_words[next_index]
                )
                next_index += 1

            if len(word_group) > 1:
                cues.append(
                    self._cue_from_words(
                        tuple(
                            word_group
                        ),
                        formatter
                    )
                )
                merged += self._micro_count(
                    word_group
                )
                index = next_index
                continue

            if (
                self.merge_preference == "previous"
                and cues
                and self._can_append_to_previous(
                    cues[-1],
                    word
                )
            ):
                cues[-1] = self._append_to_previous(
                    cues[-1],
                    word,
                    formatter
                )
                merged += 1
                index += 1
                continue

            if (
                self.merge_preference == "next"
                and cues
                and index + 1 >= len(prepared_words)
                and self._can_append_to_previous(
                    cues[-1],
                    word
                )
            ):
                cues[-1] = self._append_to_previous(
                    cues[-1],
                    word,
                    formatter
                )
                merged += 1
                index += 1
                continue

            cues.append(
                self._extended_cue(
                    word,
                    formatter
                )
            )
            extended += 1
            index += 1

        return MicroCueResult(
            cues=tuple(
                cues
            ),
            stats=MicroCueStats(
                detected=detected,
                merged=merged,
                extended=extended
            )
        )

    def _is_micro(
        self,
        word: WordTiming
    ) -> bool:
        return (
            word.end
            - word.start
        ) < self.minimum_visual_duration

    def _can_merge(
        self,
        left: WordTiming,
        right: WordTiming
    ) -> bool:
        gap = (
            right.start
            - left.end
        )

        return (
            gap >= 0
            and gap < self.significant_gap_threshold
        )

    def _can_append_to_previous(
        self,
        previous: SubtitleCue,
        word: WordTiming
    ) -> bool:
        gap = (
            word.start
            - previous.end
        )

        return (
            gap >= 0
            and gap < self.significant_gap_threshold
        )

    def _append_to_previous(
        self,
        previous: SubtitleCue,
        word: WordTiming,
        formatter: Callable[[str], str]
    ) -> SubtitleCue:
        words = previous.words + (
            word,
        )

        return self._cue_from_words(
            words,
            formatter
        )

    def _extended_cue(
        self,
        word: WordTiming,
        formatter: Callable[[str], str]
    ) -> SubtitleCue:
        return SubtitleCue(
            text=formatter(
                word.text
            ),
            start=word.start,
            end=max(
                word.end,
                word.start
                + self.minimum_visual_duration
            ),
            words=(
                word,
            )
        )

    def _cue_from_words(
        self,
        words: tuple[WordTiming, ...],
        formatter: Callable[[str], str]
    ) -> SubtitleCue:
        text = " ".join(
            formatter(
                word.text
            )
            for word in words
        )

        start = words[0].start
        end = words[-1].end

        # Words that all last zero seconds get the minimum visual duration.
        if end <= start:
            end = start + self.minimum_visual_duration

        return SubtitleCue(
            text=text,
            start=start,
            end=end,
            words=words
        )

    def _group_duration(
        self,
        words: list[WordTiming]
    ) -> float:
        return (
            words[-1].end
            - words[0].start
        )

    def _micro_count(
        self,
        words: list[WordTiming]
    ) -> int:
        return sum(
            1
            for word in words
            if self._is_micro(
                word
            )
        )
