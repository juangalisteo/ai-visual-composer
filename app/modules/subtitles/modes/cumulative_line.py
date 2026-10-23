from app.modules.subtitles.modes.base import BaseSubtitleModel
from app.modules.subtitles.modes.single_line import SingleLineModel


class CumulativeLineModel(BaseSubtitleModel):
    """Emit additive left-to-right cue events for each semantic clause.

    Each event ends where the next one of its clause starts, so only one
    line is visible at a time; the last event keeps the clause end.
    """

    def __init__(self, config):
        self.segmenter = SingleLineModel(config)

    def optimize(self, blocks, timing=None):
        if timing is not None and timing.is_usable():
            return self._optimize_with_timing(timing)
        return self._optimize_without_timing(blocks)

    def _optimize_with_timing(self, timing):
        optimized = []
        index = 1

        for segment in timing.segments:
            for word_group in self.segmenter._split_words_by_gap(segment.words):
                for clause in self.segmenter._split_timed_words_by_sense(word_group):
                    starts = [word.start for word in clause]
                    ends = starts[1:] + [clause[-1].end]
                    for position, (start, end) in enumerate(
                        zip(starts, ends), start=1
                    ):
                        optimized.append(
                            self._format_block(
                                index=index,
                                start=self.segmenter._seconds_to_time(start),
                                end=self.segmenter._seconds_to_time(end),
                                text=self._format_words(clause[:position]),
                            )
                        )
                        index += 1

        return optimized

    def _optimize_without_timing(self, blocks):
        optimized = []
        index = 1

        for block in blocks:
            parsed = self.segmenter._parse_block(block)
            if parsed is None:
                continue
            start_ms, end_ms, text = parsed
            clauses = self.segmenter._avoid_orphan_words(
                self.segmenter._split_text_by_sense(text)
            )
            clause_ranges = self.segmenter._distribute_time_by_text_length(
                start_ms, end_ms, clauses
            )

            for clause, (clause_start, clause_end) in zip(clauses, clause_ranges):
                words = clause.split()
                word_ranges = self.segmenter._distribute_time_by_text_length(
                    clause_start, clause_end, words
                )
                starts = [word_start for word_start, _ in word_ranges]
                ends = starts[1:] + [clause_end]
                for position, (word_start, word_end) in enumerate(
                    zip(starts, ends), start=1
                ):
                    optimized.append(
                        self._format_block(
                            index=index,
                            start=self.segmenter._ms_to_time(word_start),
                            end=self.segmenter._ms_to_time(word_end),
                            text=self._format_words(words[:position]),
                        )
                    )
                    index += 1

        return optimized

    def _format_words(self, words):
        return self.segmenter.punctuation.apply(" ".join(
            word.text if hasattr(word, "text") else str(word)
            for word in words
        ))

    @staticmethod
    def _format_block(index, start, end, text):
        return f"{index}\n{start} --> {end}\n{text}"
