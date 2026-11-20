"""Storyboard scenes cut at the end of sentences, on the voice's times."""

from dataclasses import dataclass


# Marks that close a clause inside a sentence (see ``segment_scenes``).
_CLAUSE_ENDS = (",", ";", ":", "—", "–")
_CLOSING_MARKS = "\"'»”’)"

# Kinds of cut, from the preferred one to the last resort.
_SENTENCE_END = 0
_CLAUSE_END = 1
_WORD_GAP = 2


@dataclass(frozen=True)
class SceneSpan:
    """One scene: its text and where it starts and ends in the audio."""

    text: str
    start: float
    end: float

    @property
    def duration(self):
        return self.end - self.start


@dataclass(frozen=True)
class _Cut:
    position: int
    time: float
    kind: int


def segment_scenes(words, audio_duration, scene_seconds):
    """Group the timed words of a script into scenes.

    ``words`` are ``(WordTiming, closes)`` pairs in reading order, where
    ``closes`` says whether the word closes a sentence or a paragraph.
    ``scene_seconds`` gives ``min``, ``target_min``, ``target_max`` and
    ``max`` in seconds. The scenes cover the whole audio: the first starts
    at 0, the last ends at ``audio_duration`` and each one starts where the
    previous one ends. A cut between two words falls in the middle of the
    silence between them.

    Scenes are cut at the end of a sentence. Only a sentence that alone
    lasts more than ``max`` may also be cut inside: after a comma (or ``;``,
    ``:``, a dash) or, as a last resort, between two words. Among all the
    ways to cut, the chosen one has, in this order of importance: the fewest
    seconds outside ``min``–``max``; the fewest cuts between words, then
    after a comma; and scenes as close as possible to
    ``target_min``–``target_max``. The text of each scene is its words
    joined by spaces.
    """
    words = tuple(words)

    if not words:
        raise ValueError(
            "No hay palabras con tiempo para dividir el guion en escenas."
        )

    audio_duration = float(audio_duration)

    if audio_duration <= 0:
        raise ValueError(
            "La duración del audio debe ser superior a 0."
        )

    boundaries = (
        _Cut(0, 0.0, _SENTENCE_END),
        *_candidate_cuts(words, audio_duration, scene_seconds.max),
        _Cut(len(words), audio_duration, _SENTENCE_END),
    )
    chosen = _best_boundaries(boundaries, scene_seconds)

    return tuple(
        SceneSpan(
            text=" ".join(
                word.text
                for word, _ in words[first.position:last.position]
            ),
            start=first.time,
            end=last.time,
        )
        for first, last in zip(chosen, chosen[1:])
    )


def _candidate_cuts(words, audio_duration, max_seconds):
    """Every sentence end, and every gap between words inside a sentence
    that alone lasts more than ``max_seconds``; in order, with times
    strictly growing between 0 and ``audio_duration``."""

    gaps = [
        _Cut(
            position,
            min(
                audio_duration,
                max(
                    0.0,
                    (words[position - 1][0].end + words[position][0].start)
                    / 2
                )
            ),
            _kind(*words[position - 1]),
        )
        for position in range(1, len(words))
    ]
    limits = [
        0.0,
        *(cut.time for cut in gaps if cut.kind == _SENTENCE_END),
        audio_duration,
    ]
    long_sentences = [
        (start, end)
        for start, end in zip(limits, limits[1:])
        if end - start > max_seconds
    ]
    cuts = []

    for cut in gaps:
        if cut.kind != _SENTENCE_END and not any(
            start < cut.time < end
            for start, end in long_sentences
        ):
            continue

        previous = cuts[-1].time if cuts else 0.0

        if previous < cut.time < audio_duration:
            cuts.append(cut)

    return cuts


def _kind(word, closes):
    if closes:
        return _SENTENCE_END

    if word.text.rstrip(_CLOSING_MARKS).endswith(_CLAUSE_ENDS):
        return _CLAUSE_END

    return _WORD_GAP


def _best_boundaries(boundaries, scene_seconds):
    """The boundaries, first and last included, of the cheapest scenes.

    The cost of a set of scenes is the tuple described in
    ``segment_scenes``; tuples compare in that order of importance.
    """

    best = [((0.0, 0, 0, 0.0), None)]

    for end in boundaries[1:]:
        best.append(min(
            (
                (
                    cost[0] + outside,
                    cost[1] + (end.kind == _WORD_GAP),
                    cost[2] + (end.kind == _CLAUSE_END),
                    cost[3] + distance,
                ),
                previous,
            )
            for previous, (cost, _) in enumerate(best)
            for outside, distance in (
                _scene_cost(
                    end.time - boundaries[previous].time,
                    scene_seconds
                ),
            )
        ))

    chosen = []
    index = len(boundaries) - 1

    while index is not None:
        chosen.append(boundaries[index])
        index = best[index][1]

    return tuple(reversed(chosen))


def _scene_cost(duration, scene_seconds):
    """Seconds outside min–max, and the squared seconds outside the target."""

    outside = (
        max(0.0, scene_seconds.min - duration)
        + max(0.0, duration - scene_seconds.max)
    )
    distance = (
        max(0.0, scene_seconds.target_min - duration)
        + max(0.0, duration - scene_seconds.target_max)
    )
    return outside, distance ** 2
