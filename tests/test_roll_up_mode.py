import pytest

from app.modules.subtitles.modes.registry import CueModelRegistry
from app.modules.subtitles.modes.roll_up import RollUpModel
from app.modules.subtitles.policies.timing import (
    SpeechSegment,
    SubtitleTiming,
    WordTiming,
)
from app.modules.video.config.loaders.subtitle_loader import SubtitleConfigLoader
from app.modules.video.subtitles.ass_subtitle_builder import AssSubtitleBuilder
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


STYLE = {
    "font": "gotham", "font_size": 10, "bold": False,
    "italic": False, "underline": False, "strikeout": False,
    "primary_colour": "&H00FFFFFF", "secondary_colour": "&H00000000",
    "outline_colour": "&H00000000", "back_colour": "&H00000000",
    "border_style": 1, "outline": 0, "shadow": 1, "alignment": 1,
    "margin_v": 55, "margin_l": 50, "margin_r": 50,
    "scale_x": 100.0, "scale_y": 100.0, "spacing": 0.0,
    "offset": 0.0, "dynamic": True, "cue_effect": "none",
    "word_effect": "none", "scroll_duration_ms": 200,
}


def _policy(**changes):
    policy = {
        "mode": "roll_up",
        "text_case": "original",
        "max_chars_per_line": 8,
        "visible_lines": 3,
        "significant_gap_threshold": 0.35,
        "punctuation": PUNCTUATION,
    }
    policy.update(changes)
    return policy


def _timing(*words):
    return SubtitleTiming(
        source="test",
        segments=(
            SpeechSegment(start=words[0].start, end=words[-1].end, words=words),
        ),
    )


def _write_srt(path, cues):
    path.write_text(
        "\n\n".join(
            f"{index}\n{start} --> {end}\n{text}"
            for index, (start, end, text) in enumerate(cues, start=1)
        ) + "\n",
        encoding="utf-8",
    )
    return path


def _dialogues(path):
    return [
        line for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("Dialogue: ")
    ]


def test_registry_resolves_roll_up_as_a_generic_cue_capability():
    assert CueModelRegistry().resolve("roll_up") is RollUpModel


def test_roll_up_emits_fixed_width_sequential_lines_with_word_timings():
    timing = _timing(
        WordTiming("uno", 0.0, 0.1),
        WordTiming("dos", 0.1, 0.2),
        WordTiming("tres", 0.2, 0.3),
        WordTiming("cuatro", 0.3, 0.4),
    )

    blocks = RollUpModel(_policy()).optimize([], timing=timing)

    assert blocks == [
        "1\n00:00:00,000 --> 00:00:00,200\nuno dos",
        "2\n00:00:00,200 --> 00:00:00,300\ntres",
        "3\n00:00:00,300 --> 00:00:00,400\ncuatro",
    ]


def test_roll_up_preserves_pause_boundaries_and_its_srt_fallback():
    timing = _timing(
        WordTiming("uno", 0.0, 0.1),
        WordTiming("dos", 0.1, 0.2),
        WordTiming("tres", 0.7, 0.8),
        WordTiming("cuatro", 0.8, 0.9),
    )

    timed = RollUpModel(_policy()).optimize([], timing=timing)
    fallback = RollUpModel(_policy()).optimize([
        "1\n00:00:00,000 --> 00:00:01,000\nuno dos tres cuatro"
    ])

    assert "00:00:00,000 --> 00:00:00,200" in timed[0]
    assert "00:00:00,700 --> 00:00:00,800" in timed[1]
    assert [block.splitlines()[2] for block in fallback] == [
        "uno dos", "tres", "cuatro"
    ]
    assert fallback[0].splitlines()[1].endswith("00:00:00,412")
    assert fallback[-1].splitlines()[1].startswith("00:00:00,647")


@pytest.mark.parametrize(
    ("changes", "message"),
    (
        ({"visible_lines": 1}, "visible_lines"),
        ({"visible_lines": 5}, "visible_lines"),
        ({"max_chars_per_line": 0}, "max_chars_per_line"),
        ({"significant_gap_threshold": 0}, "significant_gap_threshold"),
    ),
)
def test_roll_up_validates_its_declared_limits(changes, message):
    with pytest.raises(ValueError, match=message):
        RollUpModel(_policy(**changes))


def test_roll_up_requires_a_positive_declared_scroll_duration():
    with pytest.raises(ValueError, match="scroll_duration_ms"):
        SubtitleConfigLoader().load_render_style(STYLE | {"scroll_duration_ms": 0})


def test_ass_roll_up_keeps_a_three_line_buffer_and_moves_it_upwards(tmp_path):
    source = _write_srt(tmp_path / "source.srt", (
        ("00:00:00,000", "00:00:00,200", "uno"),
        ("00:00:00,200", "00:00:00,400", "dos"),
        ("00:00:00,400", "00:00:00,600", "tres"),
        ("00:00:00,600", "00:00:00,800", "cuatro"),
    ))
    output = tmp_path / "roll_up.ass"
    config = SubtitleConfigLoader().load_render_style(STYLE)

    AssSubtitleBuilder().build(
        source, config, 1080, 1920, output, cue_policy=_policy()
    )
    dialogues = _dialogues(output)

    assert len(dialogues) == 9
    assert all(r"\move(" in dialogue for dialogue in dialogues)
    assert all(",0,200)}" in dialogue for dialogue in dialogues)
    assert sum("uno" in dialogue for dialogue in dialogues) == 3
    assert sum("dos" in dialogue for dialogue in dialogues) == 3
    assert sum("tres" in dialogue for dialogue in dialogues) == 2
    assert sum("cuatro" in dialogue for dialogue in dialogues) == 1
    assert "0:00:00.60,0:00:00.80" in dialogues[-1]


def test_ass_roll_up_resets_the_buffer_after_a_declared_significant_gap(tmp_path):
    source = _write_srt(tmp_path / "paused.srt", (
        ("00:00:00,000", "00:00:00,200", "uno"),
        ("00:00:00,200", "00:00:00,400", "dos"),
        ("00:00:00,900", "00:00:01,100", "tres"),
        ("00:00:01,100", "00:00:01,300", "cuatro"),
    ))
    output = tmp_path / "paused.ass"
    config = SubtitleConfigLoader().load_render_style(STYLE)

    AssSubtitleBuilder().build(
        source, config, 1080, 1920, output, cue_policy=_policy()
    )
    paused_dialogues = [
        dialogue for dialogue in _dialogues(output)
        if "0:00:00.90" in dialogue
    ]

    assert len(paused_dialogues) == 1
    assert "tres" in paused_dialogues[0]
    assert "uno" not in paused_dialogues[0]
    assert "dos" not in paused_dialogues[0]


def test_roll_up_falls_back_to_the_normal_static_dialogue_for_one_line(tmp_path):
    source = _write_srt(tmp_path / "single.srt", (
        ("00:00:00,000", "00:00:00,400", "una linea"),
    ))
    output = tmp_path / "single.ass"
    config = SubtitleConfigLoader().load_render_style(STYLE)

    AssSubtitleBuilder().build(
        source, config, 1080, 1920, output, cue_policy=_policy()
    )

    dialogue = _dialogues(output)[0]
    assert r"\move(" not in dialogue
    assert dialogue.endswith("una linea")


def test_shared_preparation_transports_roll_up_policy_to_dynamic_ass(tmp_path):
    source = _write_srt(tmp_path / "prepared.srt", (
        ("00:00:00,000", "00:00:00,200", "uno"),
        ("00:00:00,200", "00:00:00,400", "dos"),
    ))
    prepared = SubtitleRenderPreparation().prepare(
        source,
        SubtitleConfigLoader().load_render_style(STYLE),
        1080,
        1920,
        STYLE,
        cue_policy=_policy(),
    )
    try:
        assert prepared.path.suffix == ".ass"
        assert r"\move(" in prepared.path.read_text(encoding="utf-8")
    finally:
        prepared.cleanup()


def test_vertical_karaoke_roll_up_profiles_are_discovered_declaratively():
    resolver = SubtitleProfileResolver()

    for component in ProfileComponent:
        descriptors = resolver.discover_profiles_for_family(
            component, "vertical", "karaoke"
        )
        descriptor = next(item for item in descriptors if item.mode == "roll_up")
        profile = resolver.load(descriptor.key)
        render_style = SubtitleConfigLoader().load_render_style(profile.render_style)

        assert profile.display_name == "Desplazamiento vertical"
        assert isinstance(CueModelRegistry().create(profile.cue_policy), RollUpModel)
        assert profile.cue_policy["visible_lines"] == 3
        assert profile.cue_policy["max_chars_per_line"] == 24
        assert render_style.scroll_duration_ms == 200
        assert render_style.dynamic is True
        assert profile.render_style == STYLE | {
            "scroll_duration_ms": 200,
        }
