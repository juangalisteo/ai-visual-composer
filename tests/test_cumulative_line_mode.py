import json
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from app.managers.font_manager import FontManager
from app.modules.subtitles.modes.cumulative_line import CumulativeLineModel
from app.modules.subtitles.modes.registry import CueModelRegistry
from app.modules.subtitles.policies.timing import (
    SpeechSegment,
    SubtitleTiming,
    WordTiming,
)
from app.modules.video.config.loaders.subtitle_loader import SubtitleConfigLoader
from app.modules.video.subtitles.subtitle_style_builder import SubtitleStyleBuilder
from app.shared.profile_identity import ProfileComponent
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


PUNCTUATION = {
    "remove_commas": False, "remove_periods": False,
    "remove_colons": False, "remove_semicolons": False,
    "remove_question_marks": False, "remove_exclamation_marks": False,
    "remove_ellipsis": False, "remove_hyphens": False,
    "remove_em_dashes": False, "remove_double_quotes": False,
    "remove_single_quotes": False, "remove_parentheses": False,
}


def _config(**changes):
    config = {
        "mode": "cumulative_line",
        "max_chars_per_line": 60,
        "min_duration": 0.8,
        "max_duration": 5.0,
        "significant_gap_threshold": 0.35,
        "punctuation": PUNCTUATION,
    }
    config.update(changes)
    return config


def _timing(*words):
    return SubtitleTiming(
        source="tts",
        segments=(
            SpeechSegment(start=words[0].start, end=words[-1].end, words=words),
        ),
    )


def _texts(blocks):
    return [block.splitlines()[2] for block in blocks]


def test_registry_resolves_cumulative_line_once():
    assert CueModelRegistry().resolve("cumulative_line") is CumulativeLineModel


def test_cumulative_line_adds_each_word_and_clears_after_a_pause():
    timing = _timing(
        WordTiming("uno", 0.0, 0.1),
        WordTiming("dos", 0.2, 0.3),
        WordTiming("tres", 0.4, 0.5),
        WordTiming("cuatro", 1.0, 1.1),
        WordTiming("cinco", 1.2, 1.3),
    )

    blocks = CumulativeLineModel(_config()).optimize([], timing=timing)

    assert _texts(blocks) == [
        "uno", "uno dos", "uno dos tres", "cuatro", "cuatro cinco",
    ]
    assert "00:00:00,000 --> 00:00:00,200" in blocks[0]
    assert "00:00:00,400 --> 00:00:00,500" in blocks[2]
    assert "00:00:01,000 --> 00:00:01,200" in blocks[3]


def _cues(blocks):
    return [
        (*block.splitlines()[1].split(" --> "), block.splitlines()[2])
        for block in blocks
    ]


def _assert_no_overlap(cues):
    for (_, end, _), (start, _, _) in zip(cues, cues[1:]):
        assert end <= start


def test_cumulative_line_timed_cues_do_not_overlap_and_keep_starts_and_texts():
    timing = _timing(
        WordTiming("uno", 0.0, 0.1),
        WordTiming("dos", 0.2, 0.3),
        WordTiming("tres", 0.4, 0.5),
        WordTiming("cuatro", 1.0, 1.1),
        WordTiming("cinco", 1.2, 1.3),
    )

    cues = _cues(CumulativeLineModel(_config()).optimize([], timing=timing))

    assert cues == [
        ("00:00:00,000", "00:00:00,200", "uno"),
        ("00:00:00,200", "00:00:00,400", "uno dos"),
        ("00:00:00,400", "00:00:00,500", "uno dos tres"),
        ("00:00:01,000", "00:00:01,200", "cuatro"),
        ("00:00:01,200", "00:00:01,300", "cuatro cinco"),
    ]
    _assert_no_overlap(cues)


def test_cumulative_line_untimed_cues_do_not_overlap_and_keep_starts_and_texts():
    cues = _cues(CumulativeLineModel(_config()).optimize([
        "1\n00:00:00,000 --> 00:00:00,900\nuno dos tres",
        "2\n00:00:01,000 --> 00:00:01,600\ncuatro cinco",
    ]))

    assert cues == [
        ("00:00:00,000", "00:00:00,300", "uno"),
        ("00:00:00,300", "00:00:00,600", "uno dos"),
        ("00:00:00,600", "00:00:00,900", "uno dos tres"),
        ("00:00:01,000", "00:00:01,300", "cuatro"),
        ("00:00:01,300", "00:00:01,600", "cuatro cinco"),
    ]
    _assert_no_overlap(cues)


def test_cumulative_line_restarts_when_the_semantic_line_reaches_its_limit():
    timing = _timing(
        WordTiming("aa", 0.0, 0.1),
        WordTiming("bb", 0.11, 0.2),
        WordTiming("cc", 0.21, 0.3),
        WordTiming("dd", 0.31, 0.4),
    )

    blocks = CumulativeLineModel(_config(max_chars_per_line=8)).optimize(
        [], timing=timing
    )

    assert _texts(blocks) == ["aa", "aa bb", "cc", "cc dd"]
    assert all(len(text) <= 8 for text in _texts(blocks))


def test_vertical_minimalista_cumulative_profiles_resolve_declaratively():
    resolver = SubtitleProfileResolver()

    for component in ProfileComponent:
        key = SubtitleProfileKey(
            component=component,
            platform="vertical",
            family="minimalista",
            profile_id=(
                f"subtitulo_{component.value}_vertical_cumulative_line"
            ),
        )
        profile = resolver.load(key)

        assert profile.display_name == "Palabra por palabra"
        assert profile.cue_policy["mode"] == "cumulative_line"
        assert profile.render_style["alignment"] == 2


def test_studio_cumulative_uses_static_scale_defaults_without_force_style_overrides():
    profile = SubtitleProfileResolver().load(
        SubtitleProfileKey(
            component=ProfileComponent.STUDIO,
            platform="vertical",
            family="minimalista",
            profile_id="subtitulo_studio_vertical_cumulative_line",
        )
    )

    force_style = SubtitleStyleBuilder().build(profile.render_style)

    assert "ScaleX=" not in force_style
    assert "ScaleY=" not in force_style


def _static_scaled_profiles():
    """Subtitle profiles rendered through force_style that declare a scale."""
    return [
        path
        for path in sorted(Path("config/profiles").glob("*/*/*/subtitulos/*.json"))
        if not SubtitleConfigLoader().load_render_style(
            json.loads(path.read_text(encoding="utf-8"))["render_style"]
        ).dynamic
        and {"scale_x", "scale_y"}
        & json.loads(path.read_text(encoding="utf-8"))["render_style"].keys()
    ]


def test_static_force_style_writes_scale_as_the_fraction_libass_expects():
    style = SubtitleStyleBuilder().build(
        {"font": "Arial", "scale_x": 100.0, "scale_y": 110.5}
    )

    assert "ScaleX=1," in style
    assert style.endswith("ScaleY=1.105")


def test_static_scaled_profiles_are_discovered():
    # F5b: GUION, IMAGEN and VIDEO Vertical "Palabra por palabra".
    assert len(_static_scaled_profiles()) == 3


def _text_box(tmp_path, render_style):
    font = FontManager().resolve_path(render_style["font"])
    fonts = tmp_path / "fonts"
    fonts.mkdir(exist_ok=True)
    shutil.copy(font, fonts / font.name)
    (tmp_path / "t.srt").write_text(
        "1\n00:00:00,000 --> 00:00:02,000\nHOY VAMOS\n", encoding="utf-8"
    )
    force_style = SubtitleStyleBuilder().build(render_style)
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
            "-i", "color=c=black:s=1080x1920:d=2",
            "-vf", f"subtitles=t.srt:fontsdir=fonts:force_style='{force_style}'",
            "-ss", "1", "-frames:v", "1", "-update", "1", "frame.png",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    with Image.open(tmp_path / "frame.png") as frame:
        return frame.convert("L").point(lambda value: 255 if value > 100 else 0).getbbox()


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg no disponible")
@pytest.mark.parametrize(
    "path", _static_scaled_profiles(), ids=lambda path: path.as_posix()
)
def test_static_scale_100_renders_the_text_at_its_normal_size(tmp_path, path):
    render_style = json.loads(path.read_text(encoding="utf-8"))["render_style"]
    unscaled = {
        key: value
        for key, value in render_style.items()
        if key not in ("scale_x", "scale_y")
    }

    scaled_box = _text_box(tmp_path, render_style)

    assert scaled_box is not None
    assert scaled_box == _text_box(tmp_path, unscaled)
