import shutil
import subprocess

import pytest

from app.modules.subtitles.effects.physics import KineticPhysicsEngine
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
    "cue_effect": "gravity_drop",
    "word_effect": "none",
    "drop_height_px": 100,
    "bounce_elasticity": 0.30,
}


def _source(path, end="00:00:01,000"):
    path.write_text(
        f"1\n00:00:00,000 --> {end}\nUNO\n",
        encoding="utf-8",
    )
    return path


def _dialogues(path):
    return [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("Dialogue: ")
    ]


def test_gravity_drop_emits_a_quadratic_fall_and_elastic_bounce_at_cue_timings(tmp_path):
    style = SubtitleConfigLoader().load_render_style(STYLE)
    prepared = SubtitleRenderPreparation().prepare(
        _source(tmp_path / "source.srt"), style, 1080, 1920, STYLE,
    )
    try:
        dialogues = _dialogues(prepared.path)

        assert style.cue_effect.name == "gravity_drop"
        assert style.cue_effect.parameters == {
            "drop_height_px": 100,
            "bounce_elasticity": 0.30,
        }
        assert len(dialogues) == 4
        assert "0:00:00.00,0:00:00.35" in dialogues[0]
        assert r"\move(540,886,540,1052.75,0,350)" in dialogues[0]
        assert "0:00:00.35,0:00:00.70" in dialogues[1]
        assert r"\move(540,1052.75,540,1553,0,350)" in dialogues[1]
        assert "0:00:00.70,0:00:00.85" in dialogues[2]
        assert r"\move(540,1553,540,1352.9,0,150)" in dialogues[2]
        assert "0:00:00.85,0:00:01.00" in dialogues[3]
        assert r"\move(540,1352.9,540,1553,0,150)" in dialogues[3]
        assert all(dialogue.endswith("UNO") for dialogue in dialogues)
    finally:
        prepared.cleanup()


def test_gravity_drop_uses_a_static_fallback_when_a_word_cue_is_too_short(tmp_path):
    style = SubtitleConfigLoader().load_render_style(STYLE)
    prepared = SubtitleRenderPreparation().prepare(
        _source(tmp_path / "source.srt", "00:00:00,200"),
        style,
        1080,
        1920,
        STYLE,
    )
    try:
        dialogues = _dialogues(prepared.path)

        assert len(dialogues) == 1
        assert "0:00:00.00,0:00:00.20" in dialogues[0]
        assert r"\move" not in dialogues[0]
        assert dialogues[0].endswith("UNO")
    finally:
        prepared.cleanup()


def test_kinetic_engine_preserves_the_configured_height_and_elasticity():
    segments = KineticPhysicsEngine().gravity_drop(0, 1_000, 1_865, 100, 0.30)

    assert [(segment.start, segment.end) for segment in segments] == [
        (0, 350), (350, 700), (700, 850), (850, 1_000),
    ]
    assert [(segment.from_y, segment.to_y) for segment in segments] == [
        (1765, 1790.0), (1790.0, 1865), (1865, 1835.0), (1835.0, 1865),
    ]


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg no disponible")
def test_ffmpeg_libass_accepts_the_gravity_drop_micro_trajectory(tmp_path):
    style = SubtitleConfigLoader().load_render_style(STYLE)
    prepared = SubtitleRenderPreparation().prepare(
        _source(tmp_path / "source.srt"), style, 320, 180, STYLE,
    )
    output = tmp_path / "gravity_drop.mp4"
    try:
        ass_filter = prepared.path.resolve().as_posix().replace(":", r"\:")
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
    finally:
        prepared.cleanup()


@pytest.mark.parametrize(
    "changes, message",
    (
        ({"drop_height_px": 0}, "drop_height_px"),
        ({"bounce_elasticity": 1.1}, "bounce_elasticity"),
        ({"cue_effect": "unknown"}, "cue effect no soportado"),
        ({"effects": {"fade": {"enabled": True, "in_ms": 1, "out_ms": 1}}}, "no pueden combinarse"),
    ),
)
def test_gravity_drop_validates_its_declarative_contract(changes, message):
    with pytest.raises(ValueError, match=message):
        SubtitleConfigLoader().load_render_style(STYLE | changes)


def test_minimalista_gravity_drop_profiles_resolve_declaratively():
    resolver = SubtitleProfileResolver()

    for component in ProfileComponent:
        key = SubtitleProfileKey(
            component=component,
            platform="vertical",
            family="minimalista",
            profile_id=f"subtitulo_{component.value}_vertical_gravity_drop",
        )
        profile = resolver.load(key)
        render_style = SubtitleConfigLoader().load_render_style(profile.render_style)

        assert profile.display_name == "Caída de palabras"
        assert profile.cue_policy["mode"] == "word_by_word"
        assert profile.render_style["cue_effect"] == "gravity_drop"
        assert render_style.cue_effect.name == "gravity_drop"
        assert render_style.cue_effect.parameters == {
            "drop_height_px": 100,
            "bounce_elasticity": 0.30,
        }
