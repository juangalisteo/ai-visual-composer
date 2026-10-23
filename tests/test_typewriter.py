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
    "font": "gotham", "font_size": 16, "bold": False,
    "primary_colour": "&H00FFFFFF", "secondary_colour": "&H00000000",
    "outline_colour": "&H00000000", "back_colour": "&H00000000",
    "border_style": 1, "outline": 0, "shadow": 1, "alignment": 1,
    "margin_v": 25, "margin_l": 50, "margin_r": 50, "offset": 0.0,
    "dynamic": True, "word_effect": "typewriter",
    "typewriter_cursor": True, "cursor_char": "_",
}


def _timing():
    words = (
        WordTiming("Hola", 0.0, 0.4),
        WordTiming("mundo", 0.5, 1.0),
    )
    return SubtitleTiming(
        source="test",
        segments=(SpeechSegment(start=0.0, end=1.0, words=words),),
    )


def _source(path):
    path.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nHola mundo\n",
        encoding="utf-8",
    )
    return path


def _dialogues(path):
    return [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("Dialogue: ")
    ]


def test_typewriter_reveals_one_character_at_a_time_over_each_word_interval(tmp_path):
    style = SubtitleConfigLoader().load_render_style(STYLE)
    prepared = SubtitleRenderPreparation().prepare(
        _source(tmp_path / "source.srt"), style, 1080, 1920, STYLE, timing=_timing(),
    )
    try:
        dialogues = _dialogues(prepared.path)

        assert len(dialogues) == 10
        assert "0:00:00.00,0:00:00.10" in dialogues[0]
        assert "0:00:00.30,0:00:00.40" in dialogues[3]
        assert "0:00:00.40,0:00:00.50" in dialogues[4]
        assert "0:00:00.50,0:00:00.60" in dialogues[5]
        assert "0:00:00.90,0:00:01.00" in dialogues[-1]
        assert dialogues[0].endswith("H_")
        assert dialogues[3].endswith("Hola_")
        assert dialogues[4].endswith("Hola_")
        assert dialogues[5].endswith("Hola m_")
        assert dialogues[-1].endswith("Hola mundo_")
    finally:
        prepared.cleanup()


def test_typewriter_spreads_the_cue_over_its_words_without_word_timing(tmp_path):
    style = SubtitleConfigLoader().load_render_style(STYLE)
    prepared = SubtitleRenderPreparation().prepare(
        _source(tmp_path / "source.srt"), style, 1080, 1920, STYLE,
    )
    try:
        dialogues = _dialogues(prepared.path)
        assert len(dialogues) == len("Holamundo")
        assert "0:00:00.00,0:00:00.11" in dialogues[0]
        assert dialogues[0].endswith(",H_")
        assert dialogues[3].endswith(",Hola_")
        assert "0:00:00.88,0:00:01.00" in dialogues[-1]
        assert dialogues[-1].endswith(",Hola mundo_")
    finally:
        prepared.cleanup()


def test_typewriter_profiles_resolve_declaratively():
    resolver = SubtitleProfileResolver()

    for component in ProfileComponent:
        key = SubtitleProfileKey(
            component=component,
            platform="instagram",
            family="minimalista",
            profile_id=f"subtitulo_{component.value}_instagram_typewriter",
        )
        profile = resolver.load(key)
        render_style = SubtitleConfigLoader().load_render_style(profile.render_style)

        assert profile.display_name == "Máquina de escribir"
        assert profile.cue_policy["mode"] == "single_line"
        assert profile.render_style["word_effect"] == "typewriter"
        assert render_style.word_effect.name == "typewriter"
        assert render_style.word_effect.parameters == {
            "typewriter_cursor": True,
            "cursor_char": "_",
        }
