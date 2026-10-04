import pytest

from app.modules.subtitles.modes.registry import CueModelRegistry
from app.modules.subtitles.modes.two_lines import TwoLineModel
from app.modules.subtitles.policies.timing import (
    SpeechSegment,
    SubtitleTiming,
    WordTiming,
)
from app.modules.video.config.loaders.subtitle_loader import SubtitleConfigLoader
from app.modules.video.subtitles.ass_subtitle_builder import AssSubtitleBuilder


PUNCTUATION = {
    "remove_commas": False,
    "remove_periods": False,
    "remove_colons": False,
    "remove_semicolons": False,
    "remove_question_marks": False,
    "remove_exclamation_marks": False,
    "remove_ellipsis": False,
    "remove_hyphens": False,
    "remove_em_dashes": False,
    "remove_double_quotes": False,
    "remove_single_quotes": False,
    "remove_parentheses": False,
}


def _config(**overrides):
    return {
        "max_chars_per_line": 12,
        "max_lines": 2,
        "balance_ratio_threshold": 0.75,
        "min_duration": 0.2,
        "max_duration": 6.0,
        "significant_gap_threshold": 0.35,
        "punctuation": PUNCTUATION,
    } | overrides


def _cue_lines(block):
    return block.splitlines()[2:]


def test_registry_resolves_two_lines_once():
    assert CueModelRegistry().resolve("two_lines") is TwoLineModel


def test_two_lines_keeps_short_text_on_one_line():
    blocks = TwoLineModel(_config()).optimize([
        "1\n00:00:00,000 --> 00:00:02,000\nuno dos",
    ])

    assert [_cue_lines(block) for block in blocks] == [["uno dos"]]


def test_two_lines_balances_a_cue_within_the_configured_line_limit():
    blocks = TwoLineModel(_config()).optimize([
        "1\n00:00:00,000 --> 00:00:03,000\n"
        "uno dos tres uno dos tres",
    ])

    assert [_cue_lines(block) for block in blocks] == [[
        "uno dos tres",
        "uno dos tres",
    ]]
    assert all(
        len(line) <= 12
        for line in _cue_lines(blocks[0])
    )


def test_two_lines_preserves_word_timing_for_the_balanced_cue():
    timing = SubtitleTiming(
        source="edge_tts",
        segments=(
            SpeechSegment(
                start=0.0,
                end=0.6,
                words=(
                    WordTiming("uno", 0.0, 0.1),
                    WordTiming("dos", 0.1, 0.2),
                    WordTiming("tres", 0.2, 0.3),
                    WordTiming("uno", 0.3, 0.4),
                    WordTiming("dos", 0.4, 0.5),
                    WordTiming("tres", 0.5, 0.6),
                ),
            ),
        ),
    )

    blocks = TwoLineModel(_config()).optimize([], timing=timing)

    assert "00:00:00,000 --> 00:00:00,600" in blocks[0]
    assert _cue_lines(blocks[0]) == ["uno dos tres", "uno dos tres"]


def test_two_lines_reaches_ass_as_one_forced_visual_line_break(tmp_path):
    block = TwoLineModel(_config()).optimize([
        "1\n00:00:00,000 --> 00:00:03,000\n"
        "uno dos tres uno dos tres",
    ])[0]
    source = tmp_path / "two_lines.srt"
    source.write_text(block + "\n", encoding="utf-8")
    style = SubtitleConfigLoader().load_render_style({
        "font": "unisans",
        "font_size": 14,
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
    })
    output = tmp_path / "two_lines.ass"

    AssSubtitleBuilder().build(source, style, 1080, 1920, output)

    assert r"uno dos tres\Nuno dos tres" in output.read_text(encoding="utf-8")


@pytest.mark.parametrize(("field", "value", "message"), (
    ("max_lines", 3, "exactamente 2"),
    ("balance_ratio_threshold", 0.4, "entre 0.5 y 1.0"),
))
def test_two_lines_validates_its_dedicated_contract(field, value, message):
    with pytest.raises(ValueError, match=message):
        TwoLineModel(_config(**{field: value}))
