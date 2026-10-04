from app.modules.subtitles.modes.registry import CueModelRegistry
from app.modules.subtitles.modes.three_two_words import ThreeTwoWordsModel
from app.modules.subtitles.policies.timing import (
    SpeechSegment,
    SubtitleTiming,
    WordTiming,
)


PUNCTUATION = {
    "remove_commas": False,
    "remove_periods": False,
    "remove_colons": False,
    "remove_semicolons": False,
    "remove_question_marks": False,
    "remove_exclamation_marks": False,
    "remove_ellipsis": False,
    "remove_hyphens": False,
    "remove_em_dashes": False,
    "remove_double_quotes": False,
    "remove_single_quotes": False,
    "remove_parentheses": False,
}


def _config(max_chars=60, fixed_chunk_size=None):
    config = {
        "max_chars_per_line": max_chars,
        "min_duration": 0.2,
        "max_duration": 4.0,
        "significant_gap_threshold": 0.35,
        "punctuation": PUNCTUATION,
    }
    if fixed_chunk_size is not None:
        config["fixed_chunk_size"] = fixed_chunk_size
    return config


def _text(block):
    return block.splitlines()[2]


def test_registry_resolves_three_two_words_once():
    assert CueModelRegistry().resolve("three_two_words") is ThreeTwoWordsModel


def test_three_two_words_uses_three_two_pattern_without_changing_words():
    model = ThreeTwoWordsModel(_config())

    blocks = model.optimize([
        "1\n00:00:00,000 --> 00:00:05,000\n"
        "uno dos tres cuatro cinco seis siete ocho nueve diez",
    ])

    assert [_text(block) for block in blocks] == [
        "uno dos tres",
        "cuatro cinco",
        "seis siete ocho",
        "nueve diez",
    ]
    assert all("\n" not in _text(block) for block in blocks)


def test_three_two_words_reduces_groups_to_honor_max_chars():
    model = ThreeTwoWordsModel(_config(max_chars=11))

    blocks = model.optimize([
        "1\n00:00:00,000 --> 00:00:05,000\n"
        "uno dos tres cuatro cinco",
    ])

    assert [_text(block) for block in blocks] == [
        "uno dos",
        "tres cuatro",
        "cinco",
    ]
    assert all(len(_text(block)) <= 11 for block in blocks)


def test_three_two_words_redistributes_final_orphan_when_possible():
    model = ThreeTwoWordsModel(_config())

    blocks = model.optimize([
        "1\n00:00:00,000 --> 00:00:04,000\n"
        "uno dos tres cuatro cinco seis",
    ])

    assert [_text(block) for block in blocks] == [
        "uno dos tres",
        "cuatro cinco seis",
    ]
    assert all(len(_text(block).split()) > 1 for block in blocks)


def test_three_two_words_uses_terminal_punctuation_as_hard_boundaries():
    model = ThreeTwoWordsModel(_config())

    blocks = model.optimize([
        "1\n00:00:00,000 --> 00:00:04,000\n"
        "Hola, mundo! Esto; sigue. Ahora?",
    ])

    assert [_text(block) for block in blocks] == [
        "Hola,",
        "mundo!",
        "Esto;",
        "sigue.",
        "Ahora?",
    ]


def test_three_two_words_uses_word_timing_and_preserves_significant_pause():
    model = ThreeTwoWordsModel(_config())
    timing = SubtitleTiming(
        source="edge_tts",
        segments=(
            SpeechSegment(
                start=0.0,
                end=1.5,
                words=(
                    WordTiming("uno", 0.0, 0.1),
                    WordTiming("dos", 0.11, 0.2),
                    WordTiming("tres", 0.21, 0.3),
                    WordTiming("cuatro", 1.0, 1.1),
                    WordTiming("cinco", 1.11, 1.2),
                ),
            ),
        ),
    )

    blocks = model.optimize([], timing=timing)

    assert [_text(block) for block in blocks] == [
        "uno dos tres",
        "cuatro cinco",
    ]
    assert "00:00:00,000 --> 00:00:00,300" in blocks[0]
    assert "00:00:01,000 --> 00:00:01,200" in blocks[1]


def test_three_two_words_falls_back_to_existing_time_distribution_without_timing():
    model = ThreeTwoWordsModel(_config())

    blocks = model.optimize([
        "1\n00:00:00,000 --> 00:00:06,000\n"
        "uno dos tres cuatro cinco seis",
    ])

    assert [_text(block) for block in blocks] == [
        "uno dos tres",
        "cuatro cinco seis",
    ]
    assert "00:00:00,000 -->" in blocks[0]
    assert blocks[-1].splitlines()[1].endswith("00:00:06,000")


def test_three_two_words_uses_fixed_chunk_size_without_orphan_redistribution():
    model = ThreeTwoWordsModel(_config(fixed_chunk_size=2))

    blocks = model.optimize([
        "1\n00:00:00,000 --> 00:00:05,000\n"
        "uno dos tres cuatro cinco",
    ])

    assert [_text(block) for block in blocks] == [
        "uno dos",
        "tres cuatro",
        "cinco",
    ]


def test_three_two_words_uses_fixed_chunk_size_with_word_timings():
    model = ThreeTwoWordsModel(_config(fixed_chunk_size=2))
    timing = SubtitleTiming(
        source="edge_tts",
        segments=(
            SpeechSegment(
                start=0.0,
                end=0.5,
                words=(
                    WordTiming("uno", 0.0, 0.1),
                    WordTiming("dos", 0.11, 0.2),
                    WordTiming("tres", 0.21, 0.3),
                    WordTiming("cuatro", 0.31, 0.4),
                    WordTiming("cinco", 0.41, 0.5),
                ),
            ),
        ),
    )

    blocks = model.optimize([], timing=timing)

    assert [_text(block) for block in blocks] == [
        "uno dos",
        "tres cuatro",
        "cinco",
    ]
    assert "00:00:00,000 --> 00:00:00,200" in blocks[0]
    assert "00:00:00,210 --> 00:00:00,400" in blocks[1]
    assert "00:00:00,410 --> 00:00:00,500" in blocks[2]
