from pathlib import Path

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
    "font": "oswald", "font_size": 22, "bold": True,
    "primary_colour": "&H0000FFFF", "secondary_colour": "&H00FFFFFF",
    "outline_colour": "&H80000000", "back_colour": "&H00000000",
    "border_style": 1, "outline": 0, "shadow": 1, "alignment": 2,
    "margin_v": 55, "offset": 0.0, "dynamic": True,
    "word_effect": "highlight_in_sentence",
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


def test_highlight_in_sentence_emits_one_full_phrase_per_active_word_interval(tmp_path):
    source = _source(tmp_path / "source.srt")
    style = SubtitleConfigLoader().load_render_style(STYLE)

    prepared = SubtitleRenderPreparation().prepare(
        source, style, 1080, 1920, STYLE, timing=_timing(),
    )
    try:
        dialogues = _dialogues(prepared.path)
        assert len(dialogues) == 3
        assert "0:00:00.00,0:00:00.40" in dialogues[0]
        assert "0:00:00.40,0:00:01.00" in dialogues[1]
        assert "0:00:01.00,0:00:01.50" in dialogues[2]
        assert r"{\1c&H00FFFFFF}{\1c&H0000FFFF}UNO{\1c&H00FFFFFF} DOS TRES" in dialogues[0]
        assert r"{\1c&H00FFFFFF}UNO {\1c&H0000FFFF}DOS{\1c&H00FFFFFF} TRES" in dialogues[1]
        assert r"{\1c&H00FFFFFF}UNO DOS {\1c&H0000FFFF}TRES{\1c&H00FFFFFF}" in dialogues[2]
    finally:
        prepared.cleanup()


def test_highlight_in_sentence_spreads_the_cue_over_its_words_without_word_timing(tmp_path):
    source = _source(tmp_path / "source.srt")
    style = SubtitleConfigLoader().load_render_style(STYLE)

    prepared = SubtitleRenderPreparation().prepare(
        source, style, 1080, 1920, STYLE,
    )
    try:
        dialogues = _dialogues(prepared.path)
        assert len(dialogues) == 3
        assert "0:00:00.00,0:00:00.45" in dialogues[0]
        assert "0:00:00.45,0:00:00.90" in dialogues[1]
        assert "0:00:00.90,0:00:01.50" in dialogues[2]
        assert dialogues[1].endswith(
            r"UNO {\1c&H0000FFFF}DOS{\1c&H00FFFFFF} TRES"
        )
    finally:
        prepared.cleanup()


def test_minimalista_highlight_profiles_resolve_declaratively():
    resolver = SubtitleProfileResolver()

    for component in ProfileComponent:
        key = SubtitleProfileKey(
            component=component,
            format="vertical",
            family="minimalista",
            profile_id=(
                f"subtitulo_{component.value}_vertical_highlight_in_sentence"
            ),
        )
        profile = resolver.load(key)
        render_style = SubtitleConfigLoader().load_render_style(profile.render_style)

        assert profile.display_name == "Palabra en color"
        assert profile.cue_policy["mode"] == "single_line"
        assert profile.render_style["word_effect"] == "highlight_in_sentence"
        assert profile.render_style["primary_colour"] == "&H0000FFFF"
        assert profile.render_style["secondary_colour"] == "&H00FFFFFF"
        assert render_style.word_effect.name == "highlight_in_sentence"
