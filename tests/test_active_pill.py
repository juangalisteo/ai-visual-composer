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
    "primary_colour": "&H00000000", "secondary_colour": "&H00FFFFFF",
    "outline_colour": "&H00000000", "back_colour": "&H00000000",
    "border_style": 1, "outline": 0, "shadow": 0, "alignment": 2,
    "margin_v": 55, "margin_l": 0, "margin_r": 0,
    "offset": 0.0, "dynamic": True, "word_effect": "active_pill",
    "pill_colour": "&H0000FFFF", "pill_padding": 6, "pill_radius": 4,
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


def test_active_pill_draws_a_rounded_vector_behind_only_the_active_word(tmp_path):
    style = SubtitleConfigLoader().load_render_style(STYLE)
    prepared = SubtitleRenderPreparation().prepare(
        _source(tmp_path / "source.srt"), style, 1080, 1920, STYLE, timing=_timing(),
    )
    try:
        dialogues = _dialogues(prepared.path)
        pills = [line for line in dialogues if r"\p1" in line]
        text = [line for line in dialogues if r"\p1" not in line]

        assert len(pills) == len(text) == 3
        assert "0:00:00.00,0:00:00.40" in pills[0]
        assert "0:00:00.40,0:00:01.00" in pills[1]
        assert "0:00:01.00,0:00:01.50" in pills[2]
        assert all(r"\an7\pos(0,0)\p1\1c&H0000FFFF" in line for line in pills)
        assert all("}m " in line and " b " in line for line in pills)
        assert r"{\1c&H00FFFFFF}{\1c&H00000000}UNO{\1c&H00FFFFFF} DOS TRES" in text[0]
        assert r"{\1c&H00FFFFFF}UNO {\1c&H00000000}DOS{\1c&H00FFFFFF} TRES" in text[1]
    finally:
        prepared.cleanup()


def test_active_pill_spreads_the_cue_over_its_words_without_word_timing(tmp_path):
    style = SubtitleConfigLoader().load_render_style(STYLE)
    prepared = SubtitleRenderPreparation().prepare(
        _source(tmp_path / "source.srt"), style, 1080, 1920, STYLE,
    )
    try:
        dialogues = _dialogues(prepared.path)
        pills = [line for line in dialogues if r"\p1" in line]
        text = [line for line in dialogues if r"\p1" not in line]

        assert len(pills) == len(text) == 3
        assert "0:00:00.00,0:00:00.45" in pills[0]
        assert "0:00:00.45,0:00:00.90" in pills[1]
        assert "0:00:00.90,0:00:01.50" in pills[2]
        assert r"UNO {\1c&H00000000}DOS{\1c&H00FFFFFF} TRES" in text[1]
    finally:
        prepared.cleanup()


def test_active_pill_profiles_resolve_declaratively():
    resolver = SubtitleProfileResolver()

    for component in ProfileComponent:
        key = SubtitleProfileKey(
            component=component,
            platform="instagram",
            family="minimalista",
            profile_id=f"subtitulo_{component.value}_instagram_active_pill",
        )
        profile = resolver.load(key)
        render_style = SubtitleConfigLoader().load_render_style(profile.render_style)

        assert profile.display_name == "Palabra en recuadro"
        assert profile.cue_policy["mode"] == "single_line"
        assert profile.render_style["word_effect"] == "active_pill"
        assert render_style.word_effect.name == "active_pill"
        assert render_style.word_effect.parameters == {
            "pill_colour": "&H0000FFFF", "pill_padding": 6, "pill_radius": 4,
        }
