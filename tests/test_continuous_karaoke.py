import pytest

from app.modules.subtitles.nlp.syllabifier import SyllabifierPolicy
from app.modules.subtitles.policies.timing import (
    SpeechSegment,
    SubtitleTiming,
    WordTiming,
)
from app.modules.video.config.loaders.subtitle_loader import SubtitleConfigLoader
from app.modules.video.subtitles.subtitle_render_preparation import (
    SubtitleRenderPreparation,
)
from app.shared.profile_identity import ProfileComponent
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


PUNCTUATION = {
    "remove_commas": False, "remove_periods": False,
    "remove_colons": False, "remove_semicolons": False,
    "remove_question_marks": False, "remove_exclamation_marks": False,
    "remove_ellipsis": False, "remove_hyphens": False,
    "remove_em_dashes": False, "remove_double_quotes": False,
    "remove_single_quotes": False, "remove_parentheses": False,
}

POLICY = {
    "mode": "single_line", "text_case": "original",
    "max_chars_per_line": 35, "min_duration": 1.0, "max_duration": 4.0,
    "significant_gap_threshold": 0.35, "syllabify": True,
    "punctuation": PUNCTUATION,
}

STYLE = {
    "font": "gotham", "font_size": 10, "bold": True,
    "italic": False, "underline": False, "strikeout": False,
    "primary_colour": "&H0000FFFF", "secondary_colour": "&H00FFFFFF",
    "outline_colour": "&H00000000", "back_colour": "&H00000000",
    "border_style": 1, "outline": 0, "shadow": 1, "alignment": 2,
    "margin_v": 55, "margin_l": 0, "margin_r": 0,
    "scale_x": 100.0, "scale_y": 100.0, "spacing": 0.0,
    "offset": 0.0, "dynamic": True, "cue_effect": "none",
    "word_effect": "continuous_karaoke",
}


def _timing():
    words = (
        WordTiming("HOLA", 0.0, 0.4),
        WordTiming("MUNDO", 0.5, 1.0),
    )
    return SubtitleTiming(
        source="test",
        segments=(SpeechSegment(start=0.0, end=1.0, words=words),),
    )


def _source(path):
    path.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nHOLA MUNDO\n",
        encoding="utf-8",
    )
    return path


def _dialogues(path):
    return [
        line for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("Dialogue: ")
    ]


def test_spanish_syllabifier_preserves_spelling_and_distributes_word_duration():
    syllabifier = SyllabifierPolicy.from_cue_policy(POLICY)

    assert syllabifier.syllables("CANTAR\u00c9") == (
        "CAN", "TA", "R\u00c9"
    )
    assert syllabifier.syllables("M\u00daSICA") == (
        "M\u00da", "SI", "CA"
    )
    assert syllabifier.syllables("\u00bfHOLA!") == ("\u00bfHO", "LA!")
    assert [
        (item.text, item.duration_centiseconds)
        for item in syllabifier.timed_syllables("HOLA", 40)
    ] == [("HO", 20), ("LA", 20)]


def test_continuous_karaoke_emits_one_phrase_with_syllabic_kf_timing(tmp_path):
    style = SubtitleConfigLoader().load_render_style(STYLE)
    prepared = SubtitleRenderPreparation().prepare(
        _source(tmp_path / "source.srt"),
        style,
        1080,
        1920,
        STYLE,
        timing=_timing(),
        cue_policy=POLICY,
    )
    try:
        dialogues = _dialogues(prepared.path)

        assert len(dialogues) == 1
        assert "0:00:00.00,0:00:01.00" in dialogues[0]
        assert r"{\kf20}HO{\kf20}LA{\k10} {\kf30}MUN{\kf20}DO" in dialogues[0]
        assert ",&H0000FFFF,&H00FFFFFF," in prepared.path.read_text(
            encoding="utf-8"
        )
    finally:
        prepared.cleanup()


def test_continuous_karaoke_spreads_the_cue_over_its_words_without_timing(tmp_path):
    style = SubtitleConfigLoader().load_render_style(STYLE)
    prepared = SubtitleRenderPreparation().prepare(
        _source(tmp_path / "source.srt"), style, 1080, 1920, STYLE,
        cue_policy=POLICY,
    )
    try:
        dialogue = _dialogues(prepared.path)

        assert len(dialogue) == 1
        assert "0:00:00.00,0:00:01.00" in dialogue[0]
        assert dialogue[0].endswith(r"{\kf22}HO{\kf22}LA {\kf34}MUN{\kf22}DO")
    finally:
        prepared.cleanup()


def test_continuous_karaoke_requires_the_declared_syllabification_policy(tmp_path):
    style = SubtitleConfigLoader().load_render_style(STYLE)
    with pytest.raises(ValueError, match="syllabify"):
        SubtitleRenderPreparation().prepare(
            _source(tmp_path / "source.srt"), style, 1080, 1920, STYLE,
            timing=_timing(), cue_policy=POLICY | {"syllabify": False},
        )


def test_vertical_karaoke_continuous_profiles_resolve_declaratively():
    resolver = SubtitleProfileResolver()

    for component in ProfileComponent:
        descriptor = next(
            item
            for item in resolver.discover_profiles_for_family(
                component, "vertical", "karaoke"
            )
            if item.profile_id.endswith("continuous_karaoke")
        )
        profile = resolver.load(descriptor.key)
        render_style = SubtitleConfigLoader().load_render_style(profile.render_style)

        assert profile.display_name == "Karaoke continuo"
        assert profile.cue_policy["mode"] == "single_line"
        assert profile.cue_policy["syllabify"] is True
        assert render_style.word_effect.name == "continuous_karaoke"
        assert render_style.word_effect.parameters == {}
        assert profile.render_style == STYLE
