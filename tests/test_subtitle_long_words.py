"""A word longer than the line limit never stops subtitle generation (F5b D).

Like single_line, the modes that cut lines by characters put such a word
alone in its cue.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.modules.subtitles.modes.roll_up import RollUpModel
from app.modules.subtitles.modes.three_two_words import ThreeTwoWordsModel
from app.modules.subtitles.modes.two_lines import TwoLineModel
from app.modules.subtitles.pipeline.cue_transformer import SubtitleCueTransformer
from app.modules.subtitles.policies.timing import (
    SpeechSegment,
    SubtitleTiming,
    WordTiming,
)


LONG_WORD = "superelectroencefalografistasxx"
WORDS = ("hoy", "hablamos", "de", LONG_WORD, "y", "de", "todo")
SOURCE = "1\n00:00:00,000 --> 00:00:03,000\n" + " ".join(WORDS) + "\n"
TIMING = SubtitleTiming(
    source="test",
    segments=(
        SpeechSegment(
            start=0.0,
            end=2.75,
            words=tuple(
                WordTiming(word, index * 0.4, index * 0.4 + 0.35)
                for index, word in enumerate(WORDS)
            ),
        ),
    ),
)
PUNCTUATION = {
    "remove_commas": False, "remove_periods": False,
    "remove_colons": False, "remove_semicolons": False,
    "remove_question_marks": False, "remove_exclamation_marks": False,
    "remove_ellipsis": False, "remove_hyphens": False,
    "remove_em_dashes": False, "remove_double_quotes": False,
    "remove_single_quotes": False, "remove_parentheses": False,
}
LIMIT = 12


def _profiles():
    return sorted(Path("config/profiles").glob("*/*/*/subtitulos/*.json"))


def _texts(blocks):
    return ["\n".join(block.splitlines()[2:]) for block in blocks]


@pytest.mark.parametrize("timing", (None, TIMING), ids=("sin_tiempos", "con_tiempos"))
@pytest.mark.parametrize("path", _profiles(), ids=lambda path: path.as_posix())
def test_every_profile_shows_a_word_longer_than_any_limit(path, timing):
    cue_policy = json.loads(path.read_text(encoding="utf-8"))["cue_policy"]

    srt = SubtitleCueTransformer(
        SimpleNamespace(cue_policy=cue_policy), 30
    ).transform(SOURCE, timing=timing)

    assert LONG_WORD in srt.lower()


def _three_two_words():
    return ThreeTwoWordsModel({
        "max_chars_per_line": LIMIT, "min_duration": 0.2, "max_duration": 5.0,
        "significant_gap_threshold": 0.35, "punctuation": PUNCTUATION,
    })


def _two_lines():
    return TwoLineModel({
        "max_chars_per_line": LIMIT, "min_duration": 0.2, "max_duration": 5.0,
        "significant_gap_threshold": 0.35, "max_lines": 2,
        "punctuation": PUNCTUATION,
    })


def _roll_up():
    return RollUpModel({
        "max_chars_per_line": LIMIT, "visible_lines": 3,
        "significant_gap_threshold": 0.35, "punctuation": PUNCTUATION,
    })


@pytest.mark.parametrize("timing", (None, TIMING), ids=("sin_tiempos", "con_tiempos"))
@pytest.mark.parametrize(
    "model", (_three_two_words, _two_lines, _roll_up),
    ids=("three_two_words", "two_lines", "roll_up"),
)
def test_a_word_longer_than_the_limit_goes_alone_in_its_cue(model, timing):
    texts = _texts(model().optimize(SOURCE.strip().split("\n\n"), timing=timing))

    assert LONG_WORD in texts
    # No word lost or repeated, and every other cue keeps the limit.
    assert " ".join(texts).split() == list(WORDS)
    for text in texts:
        if text != LONG_WORD:
            assert all(len(line) <= LIMIT for line in text.splitlines())


def test_a_long_word_ending_in_mente_also_goes_alone():
    word = "anticonstitucionalmente"
    blocks = _three_two_words().optimize(
        [f"1\n00:00:00,000 --> 00:00:02,000\nlo dijo {word} ayer"]
    )

    assert _texts(blocks) == ["lo dijo", word, "ayer"]
