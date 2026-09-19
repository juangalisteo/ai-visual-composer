from copy import deepcopy
from pathlib import Path
import shutil
import subprocess

import pytest

from app.modules.video.config.loaders.subtitle_loader import SubtitleConfigLoader
from app.modules.video.subtitles.ass_subtitle_builder import (
    AssSubtitleBuilder,
    SubtitleRenderBackend,
    SubtitleRenderBackendResolver,
)
from app.modules.video.subtitles.subtitle_render_preparation import (
    SubtitleRenderPreparation,
)


STYLE = {
    "font": "unisans",
    "font_size": 14,
    "bold": True,
    "primary_colour": "&H00FFFFFF",
    "outline_colour": "&H80000000",
    "back_colour": "&H00000000",
    "border_style": 1,
    "outline": 1,
    "shadow": 1,
    "alignment": 2,
    "margin_v": 55,
    "offset": 0.0,
    "dynamic": True,
}


def _source(path, duration="00:00:02,000"):
    path.write_text(
        f"1\n00:00:00,000 --> {duration}\nTexto {{usuario}}\\seguro\n",
        encoding="utf-8",
    )
    return path


def _style(name, **parameters):
    return STYLE | {"effects": {name: {"enabled": True, **parameters}}}


def _dialogue(path):
    return next(
        line.removeprefix("Dialogue: ")
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("Dialogue: ")
    )


def _build(tmp_path, style, duration="00:00:02,000", width=1080, height=1920):
    config = SubtitleConfigLoader().load_render_style(style)
    output = tmp_path / f"effect_{config.cue_effect.name if config.cue_effect else 'none'}.ass"
    AssSubtitleBuilder().build(_source(tmp_path / "source.srt", duration), config, width, height, output)
    return config, output


def test_effect_absence_preserves_static_or_explicit_dynamic_phase4_contract():
    static = SubtitleConfigLoader().load_render_style({key: value for key, value in STYLE.items() if key != "dynamic"})
    disabled = SubtitleConfigLoader().load_render_style(
        {key: value for key, value in STYLE.items() if key != "dynamic"}
        | {"effects": {"fade": {"enabled": False}}}
    )
    dynamic_without_effect = SubtitleConfigLoader().load_render_style(STYLE)

    assert static.cue_effect is None
    assert SubtitleRenderBackendResolver().resolve(static) is SubtitleRenderBackend.STATIC
    assert disabled.cue_effect is None
    assert SubtitleRenderBackendResolver().resolve(disabled) is SubtitleRenderBackend.STATIC
    assert dynamic_without_effect.cue_effect is None
    assert SubtitleRenderBackendResolver().resolve(dynamic_without_effect) is SubtitleRenderBackend.DYNAMIC


def test_effect_configuration_prepares_ass_for_shared_video_and_studio_renderers(tmp_path):
    style = _style("fade", in_ms=100, out_ms=100)
    source = _source(tmp_path / "source.srt")
    prepared = SubtitleRenderPreparation().prepare(
        source,
        SubtitleConfigLoader().load_render_style(style),
        1080,
        1920,
        style,
    )
    try:
        assert prepared.backend is SubtitleRenderBackend.DYNAMIC
        assert prepared.path.suffix == ".ass"
        assert r"\fad(100,100)" in _dialogue(prepared.path)
    finally:
        prepared.cleanup()


@pytest.mark.parametrize(
    ("name", "parameters", "expected"),
    (
        ("fade", {"in_ms": 200, "out_ms": 300}, r"{\fad(200,300)}"),
        ("pop", {"in_ms": 200, "from_scale": 70}, r"{\fscx70\fscy70\t(0,200,\fscx100\fscy100)}"),
        ("zoom", {"in_ms": 300, "from_scale": 80, "to_scale": 125}, r"{\fscx80\fscy80\t(0,300,\fscx125\fscy125)}"),
        ("slide", {"direction": "left", "duration_ms": 250}, r"{\move(-540,1865,540,1865,0,250)}"),
    ),
)
def test_each_supported_cue_effect_emits_controlled_tags_and_preserves_dialogue_times(
    tmp_path, name, parameters, expected
):
    config, output = _build(tmp_path, _style(name, **parameters))
    dialogue = _dialogue(output)

    assert config.cue_effect.name == name
    assert dialogue.startswith("0,0:00:00.00,0:00:02.00,Default,,0,0,0,,")
    assert expected in dialogue
    assert r"\{usuario\}" in dialogue
    assert r"\\seguro" in dialogue


def test_short_cue_clamps_effect_windows_deterministically(tmp_path):
    _, fade = _build(tmp_path, _style("fade", in_ms=300, out_ms=300), "00:00:00,100")
    _, pop = _build(tmp_path, _style("pop", in_ms=300, from_scale=70), "00:00:00,100")
    _, slide = _build(tmp_path, _style("slide", direction="up", duration_ms=300), "00:00:00,100")

    assert r"\fad(50,50)" in _dialogue(fade)
    assert r"\t(0,100," in _dialogue(pop)
    assert r"\move(540,-55,540,1865,0,100)" in _dialogue(slide)


@pytest.mark.parametrize(
    "style, message",
    (
        (_style("unknown", value=1), "no soportado"),
        (STYLE | {"effects": {"fade": {"enabled": True, "in_ms": 20}}}, "requiere out_ms"),
        (STYLE | {"effects": {"pop": {"enabled": True, "in_ms": 0, "from_scale": 70}}}, "> 0"),
        (STYLE | {"effects": {"zoom": {"enabled": True, "in_ms": 20, "from_scale": 0, "to_scale": 100}}}, "entre 1 y 400"),
        (STYLE | {"effects": {"slide": {"enabled": True, "direction": "diagonal", "duration_ms": 20}}}, "left, right, up o down"),
        ({key: value for key, value in _style("fade", in_ms=20, out_ms=20).items() if key != "dynamic"}, "requiere render_style.dynamic=true"),
        (STYLE | {"effects": {"fade": {"enabled": True, "in_ms": 20, "out_ms": 20}, "pop": {"enabled": True, "in_ms": 20, "from_scale": 70}}}, "un efecto por cue"),
    ),
)
def test_invalid_effect_configuration_fails_controlled(style, message):
    with pytest.raises((TypeError, ValueError), match=message):
        SubtitleConfigLoader().load_render_style(style)


@pytest.mark.parametrize("width,height,alignment,direction,expected", (
    (1080, 1920, 2, "left", r"\move(-540,1865,540,1865,0,200)"),
    (1920, 1080, 8, "up", r"\move(960,-1025,960,55,0,200)"),
    (1920, 1080, 3, "right", r"\move(3820,1025,1900,1025,0,200)"),
))
def test_slide_uses_system_resolution_alignment_and_margins(tmp_path, width, height, alignment, direction, expected):
    style = _style("slide", direction=direction, duration_ms=200) | {"alignment": alignment}
    _, output = _build(tmp_path, style, width=width, height=height)
    assert expected in _dialogue(output)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg no disponible")
@pytest.mark.parametrize("name, parameters", (
    ("fade", {"in_ms": 100, "out_ms": 100}),
    ("pop", {"in_ms": 100, "from_scale": 75}),
    ("zoom", {"in_ms": 100, "from_scale": 80, "to_scale": 120}),
    ("slide", {"direction": "left", "duration_ms": 100}),
))
def test_ffmpeg_libass_accepts_each_cue_effect(tmp_path, name, parameters):
    _, ass = _build(tmp_path, _style(name, **parameters), width=320, height=180)
    output = tmp_path / "smoke.mp4"
    ass_filter = ass.resolve().as_posix().replace(":", r"\:")
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x180:d=2",
            "-vf", f"ass='{ass_filter}'", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert output.is_file()
