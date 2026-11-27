"""Without time per word, a block is shared among its words by letters (A1).

PRUEBA-GS, fallo 7: CONVERTIR shared each block equally (mean 0.24 s and up
to 1.1 s away from the voice).
"""

from types import SimpleNamespace

from app.modules.subtitles.modes.letter_timing import (
    distribute_by_letters,
    letter_count,
)
from app.modules.subtitles.modes.rolling_window import RollingWindowModel


def test_each_word_gets_time_in_proportion_to_its_letters():
    assert distribute_by_letters(1000, 2000, ["a", "bbbb"]) == (
        (1000, 1200),
        (1200, 2000),
    )


def test_the_words_follow_each_other_and_fill_the_block():
    words = "Durante siglos hemos buscado respuestas fuera".split()

    ranges = distribute_by_letters(12_345, 15_678, words)

    assert ranges[0][0] == 12_345
    assert ranges[-1][1] == 15_678
    assert all(a[1] == b[0] for a, b in zip(ranges, ranges[1:]))
    durations = [end - start for start, end in ranges]
    assert durations.index(max(durations)) == words.index("respuestas")


def test_only_letters_and_digits_count_and_every_word_weighs_at_least_one():
    assert letter_count("¿qué?") == 3
    assert letter_count("2026,") == 4
    assert letter_count("—") == 1
    assert letter_count(SimpleNamespace(text="ñandú")) == 5


def test_one_word_takes_the_whole_block_and_no_words_take_nothing():
    assert distribute_by_letters(0, 900, ["hola"]) == ((0, 900),)
    assert distribute_by_letters(0, 900, []) == ()


def test_it_is_not_an_equal_share_any_more():
    ranges = distribute_by_letters(0, 1000, ["y", "transformaciones"])

    assert ranges == ((0, 59), (59, 1000))


def test_rolling_window_uses_the_letters_of_its_words():
    assert RollingWindowModel._distribute_word_ranges(0, 1000, ["y", "transformaciones"]) == (
        (0, 59),
        (59, 1000),
    )
