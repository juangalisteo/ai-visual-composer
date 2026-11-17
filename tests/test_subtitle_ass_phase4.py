from pathlib import Path
import json
import shutil
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.managers.font_manager import FontManager
from app.modules.video.config.loaders.subtitle_loader import SubtitleConfigLoader
from app.modules.video.ffmpeg.graphs.graph_context import GraphContext
from app.modules.video.ffmpeg.graphs.subtitle_graph_builder import SubtitleGraphBuilder
from app.modules.video.subtitles.ass_subtitle_builder import (
    AssSubtitleBuilder,
    SubtitleRenderBackend,
    SubtitleRenderBackendResolver,
)
from app.modules.video.subtitles.subtitle_render_preparation import (
    SubtitleRenderPreparation,
)
from app.modules.studio.video_audio_srt import (
    StudioVideoAudioSrtPlan,
    StudioVideoAudioSrtService,
)
from app.modules.studio.render_service import StudioRenderService


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
}


def _source(path):
    path.write_text(
        "1\n00:00:00,000 --> 00:00:01,230\nPrimera {linea}\\texto\n"
        "\n2\n00:00:01,230 --> 00:00:02,000\nSegunda\nlinea\n",
        encoding="utf-8",
    )
    return path


def _events(ass_path):
    return [
        line.removeprefix("Dialogue: ")
        for line in ass_path.read_text(encoding="utf-8").splitlines()
        if line.startswith("Dialogue: ")
    ]


def test_absent_or_false_dynamic_keeps_the_static_backend(tmp_path):
    source = _source(tmp_path / "source.srt")
    loader = SubtitleConfigLoader()
    preparation = SubtitleRenderPreparation()

    absent = loader.load_render_style(STYLE)
    false = loader.load_render_style(STYLE | {"dynamic": False})

    assert SubtitleRenderBackendResolver().resolve(absent) is SubtitleRenderBackend.STATIC
    assert SubtitleRenderBackendResolver().resolve(false) is SubtitleRenderBackend.STATIC
    prepared = preparation.prepare(source, false, 1080, 1920, STYLE)
    assert prepared.backend is SubtitleRenderBackend.STATIC
    assert prepared.path == source
    assert prepared.force_style is not None
    prepared.cleanup()
    assert source.exists()


def test_official_static_subtitle_profiles_keep_the_srt_backend():
    profiles = tuple(Path("config/profiles").rglob("*.json"))
    subtitle_profiles = []
    for path in profiles:
        data = json.loads(path.read_text(encoding="utf-8"))
        payload = data.get("subtitle_profile", data)
        if "render_style" in payload:
            subtitle_profiles.append((path, payload["render_style"]))

    static_profiles = [
        (path, style)
        for path, style in subtitle_profiles
        if not style.get("dynamic", False)
    ]

    assert static_profiles
    for path, style in static_profiles:
        config = SubtitleConfigLoader().load_render_style(style)
        assert config.dynamic is False, path
        assert SubtitleRenderBackendResolver().resolve(config) is SubtitleRenderBackend.STATIC, path


def test_true_dynamic_builds_temporary_ass_with_semantically_identical_events(tmp_path):
    source = _source(tmp_path / "source.srt")
    render_style = SubtitleConfigLoader().load_render_style(STYLE | {"dynamic": True})

    prepared = SubtitleRenderPreparation().prepare(
        source,
        render_style,
        1080,
        1920,
        STYLE | {"dynamic": True},
    )
    try:
        assert prepared.backend is SubtitleRenderBackend.DYNAMIC
        assert prepared.path.suffix == ".ass"
        assert prepared.path != source
        assert prepared.force_style is None
        content = prepared.path.read_text(encoding="utf-8")
        assert "PlayResX: 1080" in content
        assert "PlayResY: 1920" in content
        font = FontManager().resolve_name(STYLE["font"])
        assert f"Style: Default,{font},93," in content
        assert _events(prepared.path) == [
            r"0,0:00:00.00,0:00:01.23,Default,,0,0,0,,Primera \{linea\}\\texto",
            r"0,0:00:01.23,0:00:02.00,Default,,0,0,0,,Segunda\Nlinea",
        ]
        assert source.read_text(encoding="utf-8").startswith("1\n")
    finally:
        temporary = prepared.path
        prepared.cleanup()
    assert not temporary.exists()


def test_dynamic_graph_routes_to_ass_without_force_style(tmp_path):
    source = _source(tmp_path / "source.srt")
    ass_path = AssSubtitleBuilder().build(
        source,
        SubtitleConfigLoader().load_render_style(STYLE | {"dynamic": True}),
        1080,
        1920,
        tmp_path / "prepared.ass",
    )
    context = type("Context", (), {
        "subtitle_path": ass_path,
        "subtitle_backend": SubtitleRenderBackend.DYNAMIC,
        "timeline": type("Timeline", (), {"subtitle_path": source})(),
        "fonts_dir": Path("assets/fonts"),
        "subtitle_style": None,
    })()

    result = SubtitleGraphBuilder().build(
        GraphContext(context=context, filter_parts=[], current_stream="[vin]")
    )

    assert "ass='" in result.parts[0]
    assert "force_style=" not in result.parts[0]
    assert "subtitles='" not in result.parts[0]


def test_video_audio_srt_dynamic_backend_uses_ass_and_removes_temporary_file(tmp_path):
    video = tmp_path / "source.mp4"
    audio = tmp_path / "new.wav"
    source = _source(tmp_path / "human.srt")
    video.write_bytes(b"video")
    audio.write_bytes(b"audio")
    rendered_ass = []

    class Runner:
        def run(self, command):
            graph = command[command.index("-filter_complex") + 1]
            ass_name = graph.split("ass='")[1].split("':fontsdir", 1)[0]
            rendered_ass.append(Path(ass_name.replace(r"\:", ":")))
            Path(command[-1]).write_bytes(b"rendered")

    class Validator:
        def validate(self, output_path, expected_duration, profile):
            assert Path(output_path).is_file()
            return expected_duration

    profile = SimpleNamespace(
        width=320,
        height=180,
        fps=30,
        pixel_format="yuv420p",
        audio_sample_rate=48_000,
        codec="libx264",
        preset="medium",
        crf=18,
        audio_codec="aac",
        audio_bitrate="192k",
        audio_channels=2,
        movflags="+faststart",
    )
    probe = Mock()
    probe.inspect.return_value = SimpleNamespace(duration=2.0)
    probe.get_duration.return_value = 2.0
    service = StudioVideoAudioSrtService(probe=probe, runner=Runner(), validator=Validator())
    service.FONTS_DIRECTORY = tmp_path

    _, _, command = service.render(
        StudioVideoAudioSrtPlan(video, audio, source),
        tmp_path / "output.mp4",
        profile,
        subtitle_profile=SimpleNamespace(render_style=STYLE | {"dynamic": True}),
    )

    graph = command[command.index("-filter_complex") + 1]
    assert "ass='" in graph
    assert "force_style=" not in graph
    assert len(rendered_ass) == 1
    assert not rendered_ass[0].exists()


def test_studio_render_command_routes_dynamic_subtitles_to_ass(tmp_path):
    source = _source(tmp_path / "source.srt")
    ass_path = AssSubtitleBuilder().build(
        source,
        SubtitleConfigLoader().load_render_style(STYLE | {"dynamic": True}),
        320,
        180,
        tmp_path / "prepared.ass",
    )
    profile = SimpleNamespace(
        width=320,
        height=180,
        fps=30,
        pixel_format="yuv420p",
        audio_sample_rate=48_000,
        codec="libx264",
        preset="medium",
        crf=18,
        audio_codec="aac",
        audio_bitrate="192k",
        audio_channels=2,
        movflags="+faststart",
    )
    command = StudioRenderService().build_command(
        video_path=tmp_path / "source.mp4",
        subtitle_path=ass_path,
        output_path=tmp_path / "output.mp4",
        source_info=SimpleNamespace(duration=2.0, has_audio=True),
        profile=profile,
        subtitle_backend=SubtitleRenderBackend.DYNAMIC,
    )

    graph = command[command.index("-filter_complex") + 1]
    assert "ass='" in graph
    assert "force_style=" not in graph


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg no disponible")
def test_ffmpeg_libass_smoke_renders_generated_ass(tmp_path):
    source = _source(tmp_path / "source.srt")
    ass_path = AssSubtitleBuilder().build(
        source,
        SubtitleConfigLoader().load_render_style(STYLE | {"dynamic": True}),
        320,
        180,
        tmp_path / "generated.ass",
    )
    output = tmp_path / "smoke.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x180:d=2",
            "-vf", f"ass='{ass_path.resolve().as_posix().replace(':', r'\:')}'",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert output.is_file()
