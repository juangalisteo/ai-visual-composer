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
    "primary_colour": "&H00FFFFFF", "secondary_colour": "&H0000FFFF",
    "outline_colour": "&H80000000", "back_colour": "&H00000000",
    "border_style": 1, "outline": 0, "shadow": 1, "alignment": 2,
    "margin_v": 55, "offset": 0.0, "dynamic": True,
    "word_effect": "pop_in_sentence", "word_pop_scale": 125,
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


def test_pop_in_sentence_scales_only_the_active_word_over_its_real_interval(tmp_path):
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
        assert r"{\t(0,200,\fscx125\fscy125)\t(200,400,\fscx100\fscy100)}UNO{\fscx100\fscy100} DOS TRES" in dialogues[0]
        assert r"UNO {\t(0,300,\fscx125\fscy125)\t(300,600,\fscx100\fscy100)}DOS{\fscx100\fscy100} TRES" in dialogues[1]
        assert r"UNO DOS {\t(0,250,\fscx125\fscy125)\t(250,500,\fscx100\fscy100)}TRES{\fscx100\fscy100}" in dialogues[2]
    finally:
        prepared.cleanup()


def test_pop_in_sentence_spreads_the_cue_over_its_words_without_word_timing(tmp_path):
    style = SubtitleConfigLoader().load_render_style(STYLE)
    prepared = SubtitleRenderPreparation().prepare(
        _source(tmp_path / "source.srt"), style, 1080, 1920, STYLE,
    )
    try:
        dialogues = _dialogues(prepared.path)
        assert len(dialogues) == 3
        assert "0:00:00.00,0:00:00.45" in dialogues[0]
        assert "0:00:00.90,0:00:01.50" in dialogues[2]
        assert all(r"\fscx125" in line for line in dialogues)
        assert dialogues[2].endswith(
            r"UNO DOS {\t(0,300,\fscx125\fscy125)"
            r"\t(300,600,\fscx100\fscy100)}TRES{\fscx100\fscy100}"
        )
    finally:
        prepared.cleanup()


def test_pop_in_sentence_profiles_resolve_declaratively():
    resolver = SubtitleProfileResolver()

    for component in ProfileComponent:
        key = SubtitleProfileKey(
            component=component,
            platform="vertical",
            family="minimalista",
            profile_id=f"subtitulo_{component.value}_vertical_pop_in_sentence",
        )
        profile = resolver.load(key)
        render_style = SubtitleConfigLoader().load_render_style(profile.render_style)

        assert profile.display_name == "Palabra aumentada"
        assert profile.cue_policy["mode"] == "single_line"
        assert profile.render_style["word_effect"] == "pop_in_sentence"
        assert render_style.word_effect.name == "pop_in_sentence"
        assert render_style.word_effect.parameters == {"word_pop_scale": 125}
