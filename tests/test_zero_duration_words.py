import pytest

from app.modules.subtitles.modes.registry import CueModelRegistry
from app.modules.subtitles.policies.timing import (
    SpeechSegment,
    SubtitleTiming,
    WordTiming,
    stretch_zero_duration_cues,
)


PUNCTUATION = {
    "remove_commas": True, "remove_periods": True,
    "remove_colons": True, "remove_semicolons": True,
    "remove_question_marks": False, "remove_exclamation_marks": False,
    "remove_ellipsis": True, "remove_hyphens": True,
    "remove_em_dashes": True, "remove_double_quotes": True,
    "remove_single_quotes": True, "remove_parentheses": True,
}

GAP = 0.35

MICRO_CUES = {
    "enabled": True,
    "min_frames": 1,
    "min_display_seconds": 0.05,
    "merge_preference": "next",
}

CONFIGS = {
    "acoustic_burst": {"hard_max_chars": 80},
    "cumulative_line": {
        "max_chars_per_line": 60, "min_duration": 0.8, "max_duration": 5.0,
    },
    "roll_up": {"max_chars_per_line": 20, "visible_lines": 3},
    "rolling_window": {"window_size": 5},
    "single_line": {
        "max_chars_per_line": 60, "min_duration": 0.8, "max_duration": 5.0,
    },
    "three_two_words": {
        "max_chars_per_line": 60, "min_duration": 0.2, "max_duration": 4.0,
    },
    "two_lines": {
        "max_chars_per_line": 30, "max_lines": 2, "min_duration": 0.2,
        "max_duration": 6.0,
    },
    "word_by_word": {
        "min_duration": 0.3, "max_duration": 1.2, "render_fps": 30.0,
        "micro_cues": MICRO_CUES,
    },
}

# A zero-duration word in the middle, at the start, at the end and alone
# between pauses.
PHRASES = {
    "middle": (
        ("hoy", 0.0, 0.3), ("vamos", 0.35, 0.6), ("a", 0.6, 0.6),
        ("aprender", 0.65, 1.1), ("algo", 1.15, 1.4), ("nuevo", 1.45, 1.9),
    ),
    "start": (("respira", 0.5, 0.5), ("hondo", 0.55, 0.9), ("ahora", 0.95, 1.3)),
    "end": (("todo", 0.0, 0.3), ("empieza", 0.35, 0.8), ("aqui", 0.85, 0.85)),
    "alone": (("uno", 0.0, 0.3), ("dos", 2.0, 2.0), ("tres", 4.0, 4.3)),
}


def _config(mode, **changes):
    config = {
        "mode": mode,
        "significant_gap_threshold": GAP,
        "punctuation": PUNCTUATION,
        **CONFIGS[mode],
    }
    config.update(changes)
    return config


def _timing(spec):
    words = tuple(WordTiming(text, start, end) for text, start, end in spec)
    return SubtitleTiming(
        source="test",
        segments=(
            SpeechSegment(start=words[0].start, end=words[-1].end, words=words),
        ),
    )


def _ms(value):
    hours, minutes, rest = value.split(":")
    seconds, milliseconds = rest.split(",")
    return (
        int(hours) * 3_600_000 + int(minutes) * 60_000
        + int(seconds) * 1_000 + int(milliseconds)
    )


def _cues(blocks):
    cues = []
    for block in blocks:
        lines = block.splitlines()
        start, end = lines[1].split(" --> ")
        cues.append((_ms(start), _ms(end), " ".join(lines[2:]).lower()))
    return cues


@pytest.mark.parametrize("phrase", sorted(PHRASES))
@pytest.mark.parametrize("mode", sorted(CONFIGS))
def test_zero_duration_word_is_shown_without_overlap(mode, phrase):
    model = CueModelRegistry().create(_config(mode))

    cues = _cues(model.optimize([], timing=_timing(PHRASES[phrase])))

    shown = {word for _, _, text in cues for word in text.split()}
    assert {text for text, _, _ in PHRASES[phrase]} <= shown
    assert all(end > start for start, end, _ in cues)
    assert all(
        previous[1] <= current[0] for previous, current in zip(cues, cues[1:])
    )


@pytest.mark.parametrize(
    "mode", sorted(mode for mode in CONFIGS if mode != "word_by_word")
)
def test_zero_duration_word_alone_is_stretched_up_to_the_gap_threshold(mode):
    model = CueModelRegistry().create(_config(mode))

    cues = _cues(model.optimize([], timing=_timing(PHRASES["alone"])))

    assert (2_000, 2_350, "dos") in cues


@pytest.mark.parametrize(
    "mode", sorted(mode for mode in CONFIGS if mode != "word_by_word")
)
def test_zero_duration_word_in_a_group_keeps_the_group_times(mode):
    model = CueModelRegistry().create(_config(mode))

    cues = _cues(model.optimize([], timing=_timing(PHRASES["middle"])))

    assert cues[0][0] == 0
    assert cues[-1][1] == 1_900


def test_stretch_zero_duration_cues_keeps_positive_cues_unchanged():
    cues = [(0.0, 0.3, "a"), (0.3, 0.9, "b")]

    assert stretch_zero_duration_cues(cues, GAP) == cues


def test_stretch_zero_duration_cues_stops_at_the_next_cue():
    cues = [(1.0, 1.0, "a"), (1.2, 1.5, "b")]

    assert stretch_zero_duration_cues(cues, GAP) == [
        (1.0, 1.2, "a"), (1.2, 1.5, "b"),
    ]


def test_stretch_zero_duration_cues_caps_middle_and_last_cues():
    cues = [(1.0, 1.0, "a"), (3.0, 3.0, "b")]

    assert stretch_zero_duration_cues(cues, GAP) == [
        (1.0, 1.0 + GAP, "a"), (3.0, 3.0 + GAP, "b"),
    ]


def test_stretch_zero_duration_cues_drops_a_cue_with_no_room():
    cues = [(1.0, 1.0, "a"), (1.0, 1.4, "b")]

    assert stretch_zero_duration_cues(cues, GAP) == [(1.0, 1.4, "b")]


@pytest.mark.parametrize("enabled", [True, False])
@pytest.mark.parametrize("phrase", sorted(PHRASES))
def test_word_by_word_accepts_zero_duration_words(phrase, enabled):
    model = CueModelRegistry().create(
        _config("word_by_word", micro_cues={**MICRO_CUES, "enabled": enabled})
    )

    cues = _cues(model.optimize([], timing=_timing(PHRASES[phrase])))

    assert " ".join(text for _, _, text in cues).split() == [
        text for text, _, _ in PHRASES[phrase]
    ]
    assert all(end > start for start, end, _ in cues)


def test_word_by_word_accepts_zero_duration_words_at_the_same_instant():
    model = CueModelRegistry().create(_config("word_by_word"))
    spec = (("uno", 0.0, 0.3), ("dos", 2.0, 2.0), ("tres", 2.0, 2.0),
            ("cuatro", 4.0, 4.3))

    cues = _cues(model.optimize([], timing=_timing(spec)))

    assert cues == [
        (0, 300, "uno"), (2_000, 2_050, "dos tres"), (4_000, 4_300, "cuatro"),
    ]
