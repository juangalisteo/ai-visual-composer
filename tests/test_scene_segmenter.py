import pytest

from app.modules.storyboard.scene_segmenter import segment_scenes
from app.modules.subtitles.policies.timing import WordTiming
from app.shared.format_catalog import SceneSeconds


SECONDS = SceneSeconds(min=5.0, target_min=6.0, target_max=8.0, max=9.0)


def _sentences(*sentences):
    """Timed words of ``(text, start, end)`` sentences: each word takes an
    equal share of its sentence, and the last word closes it."""
    words = []

    for text, start, end in sentences:
        texts = text.split()
        share = (end - start) / len(texts)
        words.extend(
            (
                WordTiming(
                    text=word,
                    start=start + share * index,
                    end=start + share * (index + 1),
                ),
                index == len(texts) - 1,
            )
            for index, word in enumerate(texts)
        )

    return words


def _summary(scenes):
    return [
        (scene.text, round(scene.start, 3), round(scene.end, 3))
        for scene in scenes
    ]


def test_short_sentences_join_into_scenes_cut_in_the_silence_between_them():
    words = _sentences(
        ("Uno dos tres.", 0.0, 3.0),
        ("Cuatro cinco seis.", 3.4, 6.4),
        ("Siete ocho nueve.", 6.8, 9.8),
        ("Diez once doce.", 10.2, 13.2),
    )

    scenes = segment_scenes(words, 13.5, SECONDS)

    assert _summary(scenes) == [
        ("Uno dos tres. Cuatro cinco seis.", 0.0, 6.6),
        ("Siete ocho nueve. Diez once doce.", 6.6, 13.5),
    ]


def test_a_sentence_longer_than_max_is_cut_after_the_comma_that_balances_it():
    words = _sentences(
        ("a b c, d e f g, h i j k l m n.", 0.0, 14.0),
    )

    scenes = segment_scenes(words, 14.0, SECONDS)

    assert _summary(scenes) == [
        ("a b c, d e f g,", 0.0, 7.0),
        ("h i j k l m n.", 7.0, 14.0),
    ]


def test_a_sentence_longer_than_max_without_commas_is_cut_between_words():
    words = _sentences(
        ("a b c d e f g h i j k l.", 0.0, 12.0),
    )

    scenes = segment_scenes(words, 12.0, SECONDS)

    assert _summary(scenes) == [
        ("a b c d e f", 0.0, 6.0),
        ("g h i j k l.", 6.0, 12.0),
    ]


def test_a_comma_is_preferred_to_a_better_balanced_cut_between_words():
    words = _sentences(
        ("a b c d e, f g h i j k l m n.", 0.0, 14.0),
    )

    scenes = segment_scenes(words, 14.0, SECONDS)

    assert [scene.text for scene in scenes] == [
        "a b c d e,",
        "f g h i j k l m n.",
    ]


def test_a_long_sentence_is_cut_as_few_times_as_possible():
    words = _sentences(
        ("a b c d e f, g h i, j k l, m n o p q r.", 0.0, 18.0),
    )

    scenes = segment_scenes(words, 18.0, SECONDS)

    assert [scene.text for scene in scenes] == [
        "a b c d e f, g h i,",
        "j k l, m n o p q r.",
    ]


def test_a_very_short_sentence_joins_its_neighbour_beyond_max():
    words = _sentences(
        ("Uno dos.", 0.0, 2.0),
        ("Tres cuatro cinco seis siete ocho.", 2.4, 10.5),
    )

    scenes = segment_scenes(words, 10.5, SECONDS)

    assert _summary(scenes) == [
        ("Uno dos. Tres cuatro cinco seis siete ocho.", 0.0, 10.5),
    ]


def test_a_sentence_within_max_is_never_cut_inside():
    words = _sentences(
        ("a b c d, e f g h.", 0.0, 8.5),
        ("i j k l.", 8.9, 12.9),
    )

    scenes = segment_scenes(words, 12.9, SECONDS)

    assert _summary(scenes) == [
        ("a b c d, e f g h.", 0.0, 8.7),
        ("i j k l.", 8.7, 12.9),
    ]


def test_the_last_scene_ends_with_the_audio_and_keeps_a_short_last_sentence():
    words = _sentences(
        ("Primera frase larga de prueba.", 0.5, 7.0),
        ("Segunda frase larga de prueba.", 7.4, 14.0),
        ("Final.", 14.4, 15.2),
    )

    scenes = segment_scenes(words, 16.0, SECONDS)

    assert _summary(scenes) == [
        ("Primera frase larga de prueba.", 0.0, 7.2),
        ("Segunda frase larga de prueba. Final.", 7.2, 16.0),
    ]


def test_a_single_sentence_is_one_scene_over_the_whole_audio():
    words = _sentences(
        ("Una sola frase corta.", 0.3, 3.0),
    )

    scenes = segment_scenes(words, 3.4, SECONDS)

    assert _summary(scenes) == [
        ("Una sola frase corta.", 0.0, 3.4),
    ]
    assert scenes[0].duration == pytest.approx(3.4)


def test_scenes_cover_the_audio_without_gaps_and_keep_every_word():
    words = _sentences(
        *(
            (f"Frase número {number} con varias palabras.", start, start + 2.6)
            for number, start in enumerate(
                (0.0, 3.0, 6.0, 9.0, 12.0, 15.0, 18.0, 21.0, 24.0),
                start=1,
            )
        )
    )

    scenes = segment_scenes(words, 27.0, SECONDS)

    assert scenes[0].start == 0.0
    assert scenes[-1].end == 27.0
    assert all(
        previous.end == current.start
        for previous, current in zip(scenes, scenes[1:])
    )
    assert " ".join(scene.text for scene in scenes) == " ".join(
        word.text for word, _ in words
    )
    assert all(scene.text.endswith(".") for scene in scenes)
    assert all(
        SECONDS.min <= scene.duration <= SECONDS.max
        for scene in scenes
    )


def test_without_words_or_audio_there_are_no_scenes():
    with pytest.raises(ValueError, match="palabras"):
        segment_scenes((), 10.0, SECONDS)

    with pytest.raises(ValueError, match="audio"):
        segment_scenes(_sentences(("Hola.", 0.0, 1.0)), 0.0, SECONDS)


def _project_seconds(profile_format):
    from pathlib import Path

    from app.shared.format_catalog import FormatCatalog

    return FormatCatalog(
        Path(__file__).resolve().parents[1] / "config" / "formats.json"
    ).scene_seconds(profile_format)


@pytest.mark.parametrize("profile_format", ("vertical", "horizontal"))
def test_project_scenes_last_about_six_seconds_and_never_more_than_eight(
    profile_format,
):
    # T0 (owner decision): 4 · 5–7 · 8 in both formats. A 50 s script of
    # sentences of 2.2–3.4 s with 0.4 s pauses.
    seconds = _project_seconds(profile_format)
    lengths = (2.6, 3.4, 2.2, 3.0, 2.8, 3.2, 2.4, 3.4, 2.2, 3.0, 2.6, 3.2,
               2.8, 2.4, 3.0, 2.6)
    sentences = []
    start = 0.0
    for number, length in enumerate(lengths, start=1):
        sentences.append((f"Frase {number} con palabras.", start, start + length))
        start += length + 0.4
    audio = start

    scenes = segment_scenes(_sentences(*sentences), audio, seconds)

    assert (seconds.min, seconds.target_min, seconds.target_max, seconds.max) == (
        4.0,
        5.0,
        7.0,
        8.0,
    )
    assert all(scene.text.endswith(".") for scene in scenes)
    assert all(4.0 <= scene.duration <= 8.0 for scene in scenes)
    assert all(5.0 <= scene.duration <= 7.0 for scene in scenes[:-1])
    assert 5.5 <= audio / len(scenes) <= 6.5


def test_project_scenes_cut_a_nine_second_sentence_after_its_comma():
    # With the old 10 s maximum this sentence was a single scene.
    words = _sentences(
        ("uno dos tres cuatro, cinco seis siete ocho nueve.", 0.0, 9.0),
    )

    scenes = segment_scenes(words, 9.0, _project_seconds("vertical"))

    assert [scene.text for scene in scenes] == [
        "uno dos tres cuatro,",
        "cinco seis siete ocho nueve.",
    ]
    assert all(scene.duration <= 8.0 for scene in scenes)
