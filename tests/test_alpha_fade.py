import pytest

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
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


STYLE = {
    "font": "unisans",
    "font_size": 10,
    "bold": False,
    "primary_colour": "&H00FFFFFF",
    "outline_colour": "&H80000000",
    "back_colour": "&H00000000",
    "border_style": 1,
    "outline": 0,
    "shadow": 1,
    "alignment": 2,
    "margin_v": 55,
    "offset": 0.0,
    "dynamic": True,
    "word_effect": "alpha_fade",
    "fade_duration_ms": 150,
}


def _timing():
    words = (
        WordTiming("UNO", 0.0, 0.4),
        WordTiming("DOS", 0.4, 1.0),
        WordTiming("TRES", 1.0, 1.5),
    )
    return SubtitleTiming(
        source="test",
        segments=(SpeechSegment(start=0.0, end=1.5, words=words),),
    )


def _source(path):
    path.write_text(
        "1\n00:00:00,000 --> 00:00:01,500\nUNO DOS TRES\n",
        encoding="utf-8",
    )
    return path


def _dialogues(path):
    return [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("Dialogue: ")
    ]


def test_alpha_fade_reveals_each_word_at_its_real_timing_with_the_declared_ramp(tmp_path):
    style = SubtitleConfigLoader().load_render_style(STYLE)
    prepared = SubtitleRenderPreparation().prepare(
        _source(tmp_path / "source.srt"), style, 1080, 1920, STYLE, timing=_timing(),
    )
    try:
        dialogues = _dialogues(prepared.path)

        assert len(dialogues) == 3
        assert "0:00:00.00,0:00:00.40" in dialogues[0]
        assert "0:00:00.40,0:00:01.00" in dialogues[1]
        assert "0:00:01.00,0:00:01.50" in dialogues[2]
        assert (
            r"{\1a&HFF&\t(0,150,\1a&H00&)}UNO{\1a&H00&} "
            r"{\1a&HFF&}DOS{\1a&H00&} {\1a&HFF&}TRES{\1a&H00&}"
        ) in dialogues[0]
        assert (
            r"UNO {\1a&HFF&\t(0,150,\1a&H00&)}DOS{\1a&H00&} "
            r"{\1a&HFF&}TRES{\1a&H00&}"
        ) in dialogues[1]
        assert (
            r"UNO DOS {\1a&HFF&\t(0,150,\1a&H00&)}TRES{\1a&H00&}"
        ) in dialogues[2]
    finally:
        prepared.cleanup()


def test_alpha_fade_spreads_the_cue_over_its_words_without_word_timing(tmp_path):
    style = SubtitleConfigLoader().load_render_style(STYLE)
    prepared = SubtitleRenderPreparation().prepare(
        _source(tmp_path / "source.srt"), style, 1080, 1920, STYLE,
    )
    try:
        dialogues = _dialogues(prepared.path)

        assert len(dialogues) == 3
        assert "0:00:00.00,0:00:00.45" in dialogues[0]
        assert "0:00:00.45,0:00:00.90" in dialogues[1]
        assert "0:00:00.90,0:00:01.50" in dialogues[2]
        assert dialogues[2].endswith(
            r"UNO DOS {\1a&HFF&\t(0,150,\1a&H00&)}TRES{\1a&H00&}"
        )
    finally:
        prepared.cleanup()


def test_alpha_fade_requires_a_positive_fade_duration():
    invalid = dict(STYLE, fade_duration_ms=0)

    with pytest.raises(ValueError, match="fade_duration_ms"):
        SubtitleConfigLoader().load_render_style(invalid)


def test_minimalista_alpha_fade_profiles_resolve_declaratively():
    resolver = SubtitleProfileResolver()

    for component in ProfileComponent:
        key = SubtitleProfileKey(
            component=component,
            format="vertical",
            family="minimalista",
            profile_id=f"subtitulo_{component.value}_vertical_alpha_fade",
        )
        profile = resolver.load(key)
        render_style = SubtitleConfigLoader().load_render_style(profile.render_style)

        assert profile.display_name == "Revelado progresivo"
        assert profile.cue_policy["mode"] == "single_line"
        assert profile.render_style["word_effect"] == "alpha_fade"
        assert render_style.word_effect.name == "alpha_fade"
        assert render_style.word_effect.parameters == {"fade_duration_ms": 150}
        assert {
            field: profile.render_style[field]
            for field in (
                "font", "font_size", "bold", "primary_colour",
                "outline_colour", "back_colour", "border_style", "outline",
                "shadow", "alignment", "margin_v", "offset",
            )
        } == {
            "font": "unisans", "font_size": 10, "bold": False,
            "primary_colour": "&H00FFFFFF", "outline_colour": "&H80000000",
            "back_colour": "&H00000000", "border_style": 1, "outline": 0,
            "shadow": 1, "alignment": 2, "margin_v": 55, "offset": 0.0,
        }
