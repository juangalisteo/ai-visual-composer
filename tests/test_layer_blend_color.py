"""Overlays mixed in RGB keep the colour of the picture (A1, PRUEBA-GS fallo 1)."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app.modules.video.ffmpeg.graphs.layer_compositor import LayerCompositor
from app.modules.video.layer_blend_settings import (
    LayerBlendSettings,
    load_layer_blend_settings,
)
from app.shared.operational_error import OperationalError


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SIZE = 64


def _mixed_rgb(base_colour, layer_colour, blend_mode, layer_blend, tmp_path):
    """Mean RGB of one frame: base (yuv420p) + layer mixed by the compositor."""
    compositor = LayerCompositor()
    parts = ["[0:v]format=yuv420p[base]"]
    output_stream, _ = compositor.apply_operation(
        filter_parts=parts,
        current_stream="[base]",
        operation={
            "blend_mode": blend_mode,
            "opacity": 0.15,
            "start_time": 0.0,
            "end_time": 1.0,
        },
        input_index=1,
        operation_index=0,
        source_prefix="ovsrc",
        output_prefix="ov",
        width=SIZE,
        height=SIZE,
        fps=24,
        layer_blend=layer_blend,
        output_pixel_format="yuv420p",
    )
    command = [
        "ffmpeg", "-v", "error", "-nostdin",
        "-f", "lavfi", "-i", f"color=c={base_colour}:s={SIZE}x{SIZE}:r=24:d=1",
        "-f", "lavfi", "-i", f"color=c={layer_colour}:s={SIZE}x{SIZE}:r=24:d=1",
        "-filter_complex", ";".join(parts),
        "-map", output_stream,
        "-frames:v", "1",
        "-pix_fmt", "rgb24",
        "-f", "rawvideo", "-",
    ]
    pixels = subprocess.run(
        command, cwd=tmp_path, capture_output=True, check=True
    ).stdout
    assert len(pixels) == SIZE * SIZE * 3
    return tuple(
        sum(pixels[channel::3]) / (SIZE * SIZE) for channel in range(3)
    )


def _reference_rgb(colour, tmp_path):
    """Mean RGB of the base alone after the same trip through yuv420p."""
    pixels = subprocess.run(
        [
            "ffmpeg", "-v", "error", "-nostdin",
            "-f", "lavfi", "-i", f"color=c={colour}:s={SIZE}x{SIZE}:r=24:d=1",
            "-vf", "format=yuv420p",
            "-frames:v", "1", "-pix_fmt", "rgb24", "-f", "rawvideo", "-",
        ],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    ).stdout
    return tuple(
        sum(pixels[channel::3]) / (SIZE * SIZE) for channel in range(3)
    )


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg no disponible")
@pytest.mark.parametrize("base_colour", ("0x808080", "0x322013"))
@pytest.mark.parametrize("blend_mode", ("screen", "add", "lighten", "overlay"))
def test_a_black_overlay_does_not_change_the_colour(base_colour, blend_mode, tmp_path):
    expected = _reference_rgb(base_colour, tmp_path)

    mixed = _mixed_rgb(
        base_colour,
        "black",
        blend_mode,
        load_layer_blend_settings(REPOSITORY_ROOT / "config" / "video.json"),
        tmp_path,
    )

    if blend_mode == "overlay":
        # With black, «overlay» multiplies every channel by the same factor
        # (its formula): darker, but the same hue.
        ratios = [m / e for m, e in zip(mixed, expected)]
        assert max(ratios) - min(ratios) <= 0.06, (expected, mixed)
        assert all(ratio < 1 for ratio in ratios)
    else:
        shifts = [m - e for m, e in zip(mixed, expected)]
        assert all(abs(shift) <= 1.5 for shift in shifts), (expected, mixed)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg no disponible")
def test_mixing_on_yuv_planes_tints_the_picture(tmp_path):
    """Control: the graph before A1 (blend straight on yuv420p) goes magenta."""
    expected = _reference_rgb("0x808080", tmp_path)
    pixels = subprocess.run(
        [
            "ffmpeg", "-v", "error", "-nostdin",
            "-f", "lavfi", "-i", f"color=c=0x808080:s={SIZE}x{SIZE}:r=24:d=1",
            "-f", "lavfi", "-i", f"color=c=black:s={SIZE}x{SIZE}:r=24:d=1",
            "-filter_complex",
            "[0:v]format=yuv420p[b];[1:v]format=yuv420p[l];"
            "[b][l]blend=all_mode=screen:all_opacity=0.150[o]",
            "-map", "[o]", "-frames:v", "1", "-pix_fmt", "rgb24",
            "-f", "rawvideo", "-",
        ],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    ).stdout
    mixed = tuple(sum(pixels[c::3]) / (SIZE * SIZE) for c in range(3))

    assert mixed[0] - expected[0] > 5 and mixed[2] - expected[2] > 5
    assert mixed[1] < expected[1]


class _ProfileConfigManager:
    def __init__(self, profile):
        self._profile = profile

    def get_profile_config(self):
        return self._profile


@pytest.mark.parametrize("component", ("guion", "imagen", "video"))
def test_the_video_settings_carry_the_declared_mixing(component, monkeypatch):
    from app.modules.video.video_config import VideoConfigLoader
    from app.shared.profile_identity import OperationalProfileKey
    from app.shared.profile_resolver import ProfileResolver

    monkeypatch.chdir(REPOSITORY_ROOT)
    key = OperationalProfileKey(component, "vertical", f"{component}_vertical")
    profile = ProfileResolver().load_operational(key)

    config = VideoConfigLoader(
        subtitle_profile=None,
        config_manager=_ProfileConfigManager(profile),
    ).load(render_subtitles=False, still_images=component != "video")

    assert config.layer_blend == load_layer_blend_settings(
        REPOSITORY_ROOT / "config" / "video.json"
    )


def test_the_project_declares_rgb_mixing():
    settings = load_layer_blend_settings(REPOSITORY_ROOT / "config" / "video.json")

    assert settings == LayerBlendSettings(
        pixel_format="gbrp",
        scale_flags="accurate_rnd+full_chroma_int",
    )


def _write(tmp_path, document):
    path = tmp_path / "config" / "video.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        document if isinstance(document, str) else json.dumps(document),
        encoding="utf-8",
    )
    return path


def _config_error(path):
    with pytest.raises(OperationalError) as raised:
        load_layer_blend_settings(path)
    context = raised.value.context
    assert context.family == "CONFIG"
    assert context.resource == path.as_posix()
    assert context.operation == "Cargar configuración del vídeo"
    return context


def test_missing_file_is_a_config_error_with_its_path(tmp_path):
    path = tmp_path / "config" / "video.json"

    context = _config_error(path)

    assert context.user_message == (
        f"Falta el archivo de configuración «{path.as_posix()}»."
    )


def test_relative_path_is_shown_as_given(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(OperationalError) as raised:
        load_layer_blend_settings()

    assert raised.value.context.user_message == (
        "Falta el archivo de configuración «config/video.json»."
    )


@pytest.mark.parametrize(
    ("document", "message"),
    (
        ("{", "no es un JSON válido (línea 1)"),
        ([], "debe ser un objeto JSON"),
        ({}, "no declara «layer_blend»"),
        ({"layer_blend": []}, "no declara «layer_blend.pixel_format»"),
        (
            {"layer_blend": "pixel_format scale_flags"},
            "no declara «layer_blend.pixel_format»",
        ),
        (
            {"layer_blend": {"scale_flags": "accurate_rnd"}},
            "no declara «layer_blend.pixel_format»",
        ),
        (
            {"layer_blend": {"pixel_format": "gbrp"}},
            "no declara «layer_blend.scale_flags»",
        ),
    ),
)
def test_missing_or_broken_values_are_config_errors(tmp_path, document, message):
    context = _config_error(_write(tmp_path, document))

    assert message in context.user_message


@pytest.mark.parametrize(
    "value",
    (None, "", " gbrp", "gbrp,format=rgb24", "gbrp:x", "gbrp;", "[gbrp]", 3, True),
)
def test_values_that_could_change_the_filter_graph_are_rejected(tmp_path, value):
    path = _write(
        tmp_path,
        {"layer_blend": {"pixel_format": value, "scale_flags": "accurate_rnd"}},
    )

    context = _config_error(path)

    assert context.user_message == (
        f"En «{path.as_posix()}», «layer_blend.pixel_format» debe ser un texto "
        f"de letras, números, «_» o «+»; se recibió {value!r}."
    )
    assert context.technical_metadata == {"key": "layer_blend.pixel_format"}
