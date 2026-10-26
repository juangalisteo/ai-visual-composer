import pytest

from app.modules.subtitles.modes.registry import CueModelRegistry
from app.modules.subtitles.modes.rolling_window import RollingWindowModel
from app.modules.subtitles.policies.timing import (
    SpeechSegment,
    SubtitleTiming,
    WordTiming,
)
from app.modules.video.config.loaders.subtitle_loader import SubtitleConfigLoader
from app.shared.profile_identity import ProfileComponent
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


PUNCTUATION = {
    "remove_commas": True, "remove_periods": True,
    "remove_colons": True, "remove_semicolons": True,
    "remove_question_marks": False, "remove_exclamation_marks": False,
    "remove_ellipsis": True, "remove_hyphens": True,
    "remove_em_dashes": True, "remove_double_quotes": True,
    "remove_single_quotes": True, "remove_parentheses": True,
}


def _config(**changes):
    config = {
        "mode": "rolling_window",
        "significant_gap_threshold": 0.35,
        "window_size": 5,
        "max_chars_per_line": 60,
        "punctuation": PUNCTUATION,
    }
    config.update(changes)
    return config


def _timing(*words):
    return SubtitleTiming(
        source="test",
        segments=(
            SpeechSegment(start=words[0].start, end=words[-1].end, words=words),
        ),
    )


def _texts(blocks):
    return [block.splitlines()[2] for block in blocks]


def test_registry_resolves_rolling_window_once():
    assert CueModelRegistry().resolve("rolling_window") is RollingWindowModel


def _cues(blocks):
    return [
        (*block.splitlines()[1].split(" --> "), block.splitlines()[2])
        for block in blocks
    ]


def _assert_no_overlap(cues):
    for (_, end, _), (start, _, _) in zip(cues, cues[1:]):
        assert end <= start


def test_rolling_window_emits_fifo_windows_one_after_another():
    timing = _timing(
        WordTiming("uno", 0.0, 0.1),
        WordTiming("dos", 0.1, 0.2),
        WordTiming("tres", 0.2, 0.3),
        WordTiming("cuatro", 0.3, 0.4),
        WordTiming("cinco", 0.4, 0.5),
        WordTiming("seis", 0.5, 0.6),
    )

    blocks = RollingWindowModel(_config(window_size=3)).optimize([], timing=timing)

    assert _texts(blocks) == [
        "uno dos tres",
        "dos tres cuatro",
        "tres cuatro cinco",
        "cuatro cinco seis",
    ]
    assert "00:00:00,000 --> 00:00:00,100" in blocks[0]
    assert "00:00:00,100 --> 00:00:00,200" in blocks[1]
    assert "00:00:00,300 --> 00:00:00,600" in blocks[3]


def test_rolling_window_timed_cues_do_not_overlap_and_keep_starts_and_texts():
    timing = _timing(
        WordTiming("uno", 0.0, 0.1),
        WordTiming("dos", 0.15, 0.2),
        WordTiming("tres", 0.25, 0.3),
        WordTiming("cuatro", 0.35, 0.4),
        WordTiming("cinco", 1.0, 1.1),
        WordTiming("seis", 1.15, 1.2),
        WordTiming("siete", 1.25, 1.3),
        WordTiming("ocho", 1.35, 1.4),
    )

    cues = _cues(
        RollingWindowModel(_config(window_size=3)).optimize([], timing=timing)
    )

    assert cues == [
        ("00:00:00,000", "00:00:00,150", "uno dos tres"),
        ("00:00:00,150", "00:00:00,400", "dos tres cuatro"),
        ("00:00:01,000", "00:00:01,150", "cinco seis siete"),
        ("00:00:01,150", "00:00:01,400", "seis siete ocho"),
    ]
    _assert_no_overlap(cues)


def test_rolling_window_untimed_cues_do_not_overlap_and_keep_starts_and_texts():
    cues = _cues(RollingWindowModel(_config(window_size=3)).optimize([
        "1\n00:00:00,000 --> 00:00:00,800\nuno dos tres cuatro",
        "2\n00:00:01,000 --> 00:00:01,400\ncinco seis siete ocho",
    ]))

    assert cues == [
        ("00:00:00,000", "00:00:00,200", "uno dos tres"),
        ("00:00:00,200", "00:00:00,800", "dos tres cuatro"),
        ("00:00:01,000", "00:00:01,100", "cinco seis siete"),
        ("00:00:01,100", "00:00:01,400", "seis siete ocho"),
    ]
    _assert_no_overlap(cues)


def test_rolling_window_restarts_after_a_significant_pause_without_crossing_it():
    timing = _timing(
        WordTiming("uno", 0.0, 0.1),
        WordTiming("dos", 0.1, 0.2),
        WordTiming("tres", 0.2, 0.3),
        WordTiming("cuatro", 0.8, 0.9),
        WordTiming("cinco", 0.9, 1.0),
        WordTiming("seis", 1.0, 1.1),
    )

    blocks = RollingWindowModel(_config(window_size=3)).optimize([], timing=timing)

    assert _texts(blocks) == ["uno dos tres", "cuatro cinco seis"]
    assert "00:00:00,000 --> 00:00:00,300" in blocks[0]
    assert "00:00:00,800 --> 00:00:01,100" in blocks[1]


def test_rolling_window_preserves_fallback_timing():
    model = RollingWindowModel(_config(window_size=3))

    assert model.optimize([
        "1\n00:00:00,000 --> 00:00:00,600\nuno dos tres cuatro cinco"
    ]) == [
        "1\n00:00:00,000 --> 00:00:00,120\nuno dos tres",
        "2\n00:00:00,120 --> 00:00:00,240\ndos tres cuatro",
        "3\n00:00:00,240 --> 00:00:00,600\ntres cuatro cinco",
    ]


def test_rolling_window_timed_short_group_is_shown_whole_in_one_cue():
    timing = _timing(
        WordTiming("uno", 0.0, 0.1),
        WordTiming("dos", 0.1, 0.2),
        WordTiming("tres", 0.8, 0.9),
        WordTiming("cuatro", 0.9, 1.0),
        WordTiming("cinco", 1.0, 1.1),
        WordTiming("seis", 1.1, 1.2),
        WordTiming("siete", 1.2, 1.3),
        WordTiming("ocho", 2.0, 2.1),
    )

    cues = _cues(RollingWindowModel(_config()).optimize([], timing=timing))

    assert cues == [
        ("00:00:00,000", "00:00:00,200", "uno dos"),
        ("00:00:00,800", "00:00:01,300", "tres cuatro cinco seis siete"),
        ("00:00:02,000", "00:00:02,100", "ocho"),
    ]
    _assert_no_overlap(cues)


def test_rolling_window_untimed_short_block_is_shown_whole_in_one_cue():
    cues = _cues(RollingWindowModel(_config()).optimize([
        "1\n00:00:00,000 --> 00:00:00,400\nuno dos tres cuatro",
        "2\n00:00:01,000 --> 00:00:01,500\ncinco seis siete ocho nueve",
        "3\n00:00:02,000 --> 00:00:02,300\ndiez",
    ]))

    assert cues == [
        ("00:00:00,000", "00:00:00,400", "uno dos tres cuatro"),
        ("00:00:01,000", "00:00:01,500", "cinco seis siete ocho nueve"),
        ("00:00:02,000", "00:00:02,300", "diez"),
    ]
    _assert_no_overlap(cues)


def test_rolling_window_long_group_is_unchanged_by_short_groups_around_it():
    long_group = (
        WordTiming("uno", 0.0, 0.1),
        WordTiming("dos", 0.15, 0.2),
        WordTiming("tres", 0.25, 0.3),
        WordTiming("cuatro", 0.35, 0.4),
        WordTiming("cinco", 0.45, 0.5),
        WordTiming("seis", 0.55, 0.6),
        WordTiming("siete", 0.65, 0.7),
    )
    expected = [
        ("00:00:00,000", "00:00:00,150", "uno dos tres cuatro cinco"),
        ("00:00:00,150", "00:00:00,250", "dos tres cuatro cinco seis"),
        ("00:00:00,250", "00:00:00,700", "tres cuatro cinco seis siete"),
    ]
    model = RollingWindowModel(_config())

    alone = _cues(model.optimize([], timing=_timing(*long_group)))
    surrounded = _cues(model.optimize([], timing=_timing(
        *long_group,
        WordTiming("ocho", 1.5, 1.6),
        WordTiming("nueve", 1.6, 1.7),
    )))

    assert alone == expected
    assert surrounded == expected + [("00:00:01,500", "00:00:01,700", "ocho nueve")]


@pytest.mark.parametrize(
    "changes, message",
    (
        ({"window_size": 1}, "window_size"),
        ({"significant_gap_threshold": 0}, "significant_gap_threshold"),
        ({"max_chars_per_line": 0}, "max_chars_per_line"),
    ),
)
def test_rolling_window_validates_its_declared_limits(changes, message):
    with pytest.raises(ValueError, match=message):
        RollingWindowModel(_config(**changes))


def test_rolling_window_requires_a_character_limit():
    config = _config()
    del config["max_chars_per_line"]

    with pytest.raises(ValueError, match="max_chars_per_line"):
        RollingWindowModel(config)


WIDE_WORDS = (
    "la", "responsabilidad", "comprende", "transformaciones",
    "extraordinariamente", "profundas", "hoy",
)


def _assert_trimmed_windows(cues, limit):
    texts = [text for _, _, text in cues]
    # Every window fits (a longer word would stay alone) ...
    assert all(len(text) <= limit or " " not in text for text in texts)
    # ... starts with its own word, and the last one reaches the final word,
    # so no word is lost.
    assert [text.split()[0] for text in texts] == list(WIDE_WORDS[:len(texts)])
    assert texts[-1].split()[-1] == WIDE_WORDS[-1]
    _assert_no_overlap(cues)


def test_rolling_window_timed_trims_the_end_of_a_window_that_does_not_fit():
    timing = _timing(*(
        WordTiming(word, index * 0.4, index * 0.4 + 0.3)
        for index, word in enumerate(WIDE_WORDS)
    ))

    cues = _cues(
        RollingWindowModel(_config(max_chars_per_line=29)).optimize([], timing=timing)
    )

    assert cues == [
        ("00:00:00,000", "00:00:00,400", "la responsabilidad comprende"),
        ("00:00:00,400", "00:00:00,800", "responsabilidad comprende"),
        ("00:00:00,800", "00:00:01,200", "comprende transformaciones"),
        ("00:00:01,200", "00:00:01,600", "transformaciones"),
        ("00:00:01,600", "00:00:02,000", "extraordinariamente profundas"),
        ("00:00:02,000", "00:00:02,700", "profundas hoy"),
    ]
    _assert_trimmed_windows(cues, 29)


def test_rolling_window_untimed_trims_the_end_of_a_window_that_does_not_fit():
    cues = _cues(RollingWindowModel(_config(max_chars_per_line=29)).optimize([
        "1\n00:00:00,000 --> 00:00:02,800\n" + " ".join(WIDE_WORDS),
    ]))

    assert [text for _, _, text in cues] == [
        "la responsabilidad comprende",
        "responsabilidad comprende",
        "comprende transformaciones",
        "transformaciones",
        "extraordinariamente profundas",
        "profundas hoy",
    ]
    assert cues[0][:2] == ("00:00:00,000", "00:00:00,400")
    assert cues[-1][:2] == ("00:00:02,000", "00:00:02,800")
    _assert_trimmed_windows(cues, 29)


def test_rolling_window_keeps_a_word_longer_than_the_limit_alone():
    cues = _cues(RollingWindowModel(_config(max_chars_per_line=10)).optimize([
        "1\n00:00:00,000 --> 00:00:01,200\nhoy extraordinariamente bien",
    ]))

    assert [text for _, _, text in cues] == [
        "hoy", "extraordinariamente", "bien",
    ]
    _assert_no_overlap(cues)


def test_vertical_karaoke_rolling_window_profiles_resolve_declaratively():
    resolver = SubtitleProfileResolver()

    for component in ProfileComponent:
        key = SubtitleProfileKey(
            component=component,
            platform="vertical",
            family="karaoke",
            profile_id=f"subtitulo_{component.value}_vertical_rolling_window",
        )
        descriptors = resolver.discover_profiles_for_family(
            component,
            "vertical",
            "karaoke",
        )
        profile = resolver.load(key)
        render_style = SubtitleConfigLoader().load_render_style(profile.render_style)

        assert any(descriptor.key == key for descriptor in descriptors)
        assert profile.display_name == "Ventana deslizante"
        assert profile.cue_policy["mode"] == "rolling_window"
        assert profile.cue_policy["window_size"] == 5
        assert profile.cue_policy["max_chars_per_line"] == 29
        assert render_style.dynamic is False
        assert render_style.cue_effect is None
        assert render_style.word_effect is None
        assert profile.render_style == {
            "font": "unisans", "font_size": 10, "bold": False,
            "italic": False, "underline": False, "strikeout": False,
            "primary_colour": "&H00FFFFFF", "secondary_colour": "&H00000000",
            "outline_colour": "&H80000000", "back_colour": "&H00000000",
            "border_style": 1, "outline": 0, "shadow": 1, "alignment": 2,
            "margin_v": 55, "margin_l": 0, "margin_r": 0, "spacing": 0.0,
            "offset": 0.0, "dynamic": False, "cue_effect": "none",
            "word_effect": "none",
        }
