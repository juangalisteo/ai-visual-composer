from pathlib import Path
import shutil
import subprocess

import pytest

from app.modules.subtitles.models.word_by_word_model import WordByWordModel
from app.modules.video.config.loaders.subtitle_loader import SubtitleConfigLoader
from app.modules.video.subtitles.ass_subtitle_builder import (
    AssSubtitleBuilder,
    SubtitleRenderBackend,
    SubtitleRenderBackendResolver,
)
from app.modules.video.subtitles.subtitle_render_preparation import SubtitleRenderPreparation


STYLE = {
    "font": "unisans", "font_size": 14, "bold": True,
    "primary_colour": "&H00FFFFFF", "outline_colour": "&H80000000",
    "back_colour": "&H00000000", "border_style": 1, "outline": 1,
    "shadow": 1, "alignment": 2, "margin_v": 55, "offset": 0.0,
    "dynamic": True,
}


def _style(name, **parameters):
    return STYLE | {"word_effects": {name: {"enabled": True, **parameters}}}


def _source(path, text="Hola", end="00:00:01,234"):
    path.write_text(
        f"1\n00:00:00,000 --> {end}\n{text}\n",
        encoding="utf-8",
    )
    return path


def _build(tmp_path, style, text="Hola", end="00:00:01,234"):
    config = SubtitleConfigLoader().load_render_style(style)
    output = tmp_path / f"{config.word_effect.name}_{end[-3:]}.ass"
    AssSubtitleBuilder().build(_source(tmp_path / "source.srt", text, end), config, 1080, 1920, output)
    return config, output


def _dialogue(path):
    return next(line for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("Dialogue: "))


def test_word_effect_absence_keeps_static_and_disabled_keeps_srt():
    base = {key: value for key, value in STYLE.items() if key != "dynamic"}
    disabled = base | {"word_effects": {"karaoke": {"enabled": False}}}
    for style in (base, disabled):
        config = SubtitleConfigLoader().load_render_style(style)
        assert config.word_effect is None
        assert SubtitleRenderBackendResolver().resolve(config) is SubtitleRenderBackend.STATIC


@pytest.mark.parametrize(("name", "parameters", "expected"), (
    ("karaoke", {}, r"{\kf124}"),
    ("highlight", {"active_colour": "&H0000FFFF"}, r"{\1c&H0000FFFF}"),
    ("progressive_reveal", {"reveal_ms": 250}, r"{\1a&HFF&\t(0,250,\1a&H00&)}"),
))
def test_word_effects_use_final_word_cue_timing_and_preserve_text(tmp_path, name, parameters, expected):
    config, output = _build(tmp_path, _style(name, **parameters), text="Árbol{\\}世界")
    dialogue = _dialogue(output)

    assert config.word_effect.name == name
    assert SubtitleRenderBackendResolver().resolve(config) is SubtitleRenderBackend.DYNAMIC
    assert "0:00:00.00,0:00:01.23" in dialogue
    assert expected in dialogue
    assert r"Árbol\{\\\}世界" in dialogue


def test_karaoke_centisecond_rounding_is_deterministic_and_nonzero(tmp_path):
    _, tiny = _build(tmp_path, _style("karaoke"), end="00:00:00,001")
    _, exact = _build(tmp_path, _style("karaoke"), end="00:00:00,010")
    _, fraction = _build(tmp_path, _style("karaoke"), end="00:00:00,011")

    assert r"\kf1" in _dialogue(tiny)
    assert r"\kf1" in _dialogue(exact)
    assert r"\kf2" in _dialogue(fraction)


def test_word_effect_requires_single_final_word_without_resegmenting_original_or_line(tmp_path):
    config = SubtitleConfigLoader().load_render_style(_style("karaoke"))
    for text in ("Original humano completo", "Linea unica"):
        with pytest.raises(ValueError, match="una sola palabra"):
            AssSubtitleBuilder().build(_source(tmp_path / "source.srt", text), config, 1080, 1920, tmp_path / "output.ass")


@pytest.mark.parametrize("style, message", (
    ({key: value for key, value in _style("karaoke").items() if key != "dynamic"}, "requiere render_style.dynamic=true"),
    (STYLE | {"word_effects": {"unknown": {"enabled": True}}}, "no soportado"),
    (STYLE | {"word_effects": {"highlight": {"enabled": True}}}, "requiere active_colour"),
    (STYLE | {"word_effects": {"highlight": {"enabled": True, "active_colour": "yellow"}}}, "formato ASS"),
    (STYLE | {"word_effects": {"progressive_reveal": {"enabled": True, "reveal_ms": 0}}}, "> 0"),
    (_style("karaoke") | {"effects": {"fade": {"enabled": True, "in_ms": 1, "out_ms": 1}}}, "no pueden combinarse"),
))
def test_invalid_or_ambiguous_word_effects_fail_controlled(style, message):
    with pytest.raises((TypeError, ValueError), match=message):
        SubtitleConfigLoader().load_render_style(style)


def test_existing_word_by_word_algorithm_remains_upstream_and_uses_its_own_timing():
    config = {
        "min_duration": 0.1, "max_duration": 2.0,
        "punctuation": {
            "remove_commas": False, "remove_periods": False,
            "remove_colons": False, "remove_semicolons": False,
            "remove_question_marks": False, "remove_exclamation_marks": False,
            "remove_ellipsis": False, "remove_hyphens": False,
            "remove_em_dashes": False, "remove_double_quotes": False,
            "remove_single_quotes": False, "remove_parentheses": False,
        },
        "significant_gap_threshold": 0.4, "render_fps": 30,
        "micro_cues": {"enabled": False, "min_frames": 1, "min_display_seconds": 0.05, "merge_preference": "next"},
    }
    rendered = WordByWordModel(config).optimize([
        "1\n00:00:00,000 --> 00:00:01,000\nuno dos"
    ])
    assert rendered == [
        "1\n00:00:00,000 --> 00:00:00,500\nuno",
        "2\n00:00:00,500 --> 00:00:01,000\ndos",
    ]


def test_shared_preparation_routes_valid_word_effect_to_ass(tmp_path):
    style = _style("progressive_reveal", reveal_ms=100)
    source = _source(tmp_path / "word.srt")
    prepared = SubtitleRenderPreparation().prepare(
        source, SubtitleConfigLoader().load_render_style(style), 1080, 1920, style
    )
    try:
        assert prepared.backend is SubtitleRenderBackend.DYNAMIC
        assert prepared.path.suffix == ".ass"
        assert r"\1a&HFF&" in _dialogue(prepared.path)
    finally:
        prepared.cleanup()


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg no disponible")
@pytest.mark.parametrize(("name", "parameters"), (
    ("karaoke", {}),
    ("highlight", {"active_colour": "&H0000FFFF"}),
    ("progressive_reveal", {"reveal_ms": 100}),
))
def test_ffmpeg_libass_accepts_word_effects(tmp_path, name, parameters):
    _, ass = _build(tmp_path, _style(name, **parameters))
    output = tmp_path / "smoke.mp4"
    ass_filter = ass.resolve().as_posix().replace(":", r"\:")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x180:d=2",
         "-vf", f"ass='{ass_filter}'", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(output)],
        check=True, capture_output=True, text=True,
    )
    assert output.is_file()
