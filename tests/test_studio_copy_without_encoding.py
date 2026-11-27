"""STUDIO does not encode twice a video that already has the output format (A1).

PRUEBA-GS, fallo 8: MONTAJE encoded the montage and then «RENDER STUDIO»
encoded it again; INTRO / OUTRO encoded the whole video again without
changing anything. With nothing to paint or mix, its streams are copied.
"""

import shutil
import subprocess
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.modules.studio import StudioProfileLoader
from app.modules.studio.render_service import (
    StudioOutputValidator,
    StudioRenderService,
)
from app.shared.media_probe import MediaInfo
from app.shared.profile_identity import OperationalProfileKey
from app.shared.profile_resolver import ProfileResolver
from app.shared.subtitle_profile_identity import (
    ResolvedSubtitleProfile,
    SubtitleProfileKey,
)


KEY = OperationalProfileKey("studio", "vertical", "studio_vertical")


def _profile():
    return StudioProfileLoader().load(ProfileResolver().load_operational(KEY), KEY)


def _matching_info(profile, **changes):
    info = MediaInfo(
        duration=4.0,
        width=profile.width,
        height=profile.height,
        fps=float(profile.fps),
        pixel_format=profile.pixel_format,
        video_codec="h264",
        audio_codec=profile.audio_codec,
        audio_sample_rate=profile.audio_sample_rate,
        audio_channels=profile.audio_channels,
        nominal_fps=float(profile.fps),
        sample_aspect_ratio="1:1",
    )
    return replace(info, **changes)


class _Runner:
    def __init__(self):
        self.commands = []

    def run(self, command):
        self.commands.append(tuple(command))
        Path(command[-1]).write_bytes(b"rendered")


def _render(tmp_path, info, music=False):
    profile = _profile()
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    music_path = None
    if music:
        music_path = tmp_path / "music.mp3"
        music_path.write_bytes(b"music")
    probe = Mock()
    probe.inspect.return_value = info
    validator = Mock()
    validator.validate.return_value = info.duration
    runner = _Runner()
    result = StudioRenderService(
        runner=runner, probe=probe, output_validator=validator
    ).render(
        video_path=source,
        profile_key=KEY,
        profile=profile,
        output_path=tmp_path / "out" / "final.mp4",
        music_path=music_path,
    )
    return result, runner, validator, profile


def test_a_video_with_the_output_format_is_copied(tmp_path):
    profile = _profile()
    result, runner, validator, _ = _render(tmp_path, _matching_info(profile))

    assert runner.commands == [(
        "ffmpeg", "-y", "-i", str(tmp_path / "source.mp4"),
        "-map", "0:v:0", "-map", "0:a:0", "-c", "copy",
        "-movflags", profile.movflags,
        str(tmp_path / "out" / "final.rendering.mp4"),
    )]
    assert result.command == runner.commands[0]
    assert (tmp_path / "out" / "final.mp4").read_bytes() == b"rendered"
    # The copy goes through the same output validation as a render.
    validator.validate.assert_called_once()
    assert validator.validate.call_args.kwargs["expected_duration"] == 4.0


def test_a_sar_not_declared_by_ffprobe_is_square(tmp_path):
    profile = _profile()
    _, runner, _, _ = _render(tmp_path, _matching_info(profile, sample_aspect_ratio=None))

    assert "copy" in runner.commands[0]


@pytest.mark.parametrize(
    "changes",
    (
        {"width": 720, "height": 1280},
        {"nominal_fps": 25.0, "fps": 25.0},
        {"pixel_format": "yuv444p"},
        {"video_codec": "hevc"},
        {"audio_codec": None},
        {"audio_codec": "mp3"},
        {"audio_sample_rate": 44100},
        {"audio_channels": 1},
        {"sample_aspect_ratio": "4:3"},
    ),
)
def test_anything_out_of_the_output_format_is_encoded(tmp_path, changes):
    profile = _profile()
    _, runner, _, _ = _render(tmp_path, _matching_info(profile, **changes))

    assert "copy" not in runner.commands[0]
    assert "-filter_complex" in runner.commands[0]


def test_subtitles_are_always_encoded(tmp_path, monkeypatch):
    from app.modules.studio import render_service
    from app.modules.video.subtitles.ass_subtitle_builder import (
        SubtitleRenderBackend,
    )

    profile = _profile()
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    subtitles = tmp_path / "source.srt"
    subtitles.write_text("1\n00:00:00,000 --> 00:00:01,000\nHola\n", encoding="utf-8")
    monkeypatch.setattr(
        render_service,
        "SubtitleConfigLoader",
        lambda: Mock(load_render_style=Mock(return_value=Mock(offset=0.0))),
    )
    prepared = Mock(
        path=subtitles,
        force_style="Fontsize=10",
        backend=SubtitleRenderBackend.DYNAMIC,
        temporary_path=None,
    )
    monkeypatch.setattr(
        render_service,
        "SubtitleRenderPreparation",
        lambda style_builder: Mock(prepare=Mock(return_value=prepared)),
    )
    probe = Mock()
    probe.inspect.return_value = _matching_info(profile)
    validator = Mock()
    validator.validate.return_value = 4.0
    runner = _Runner()

    StudioRenderService(runner=runner, probe=probe, output_validator=validator).render(
        video_path=source,
        subtitle_path=subtitles,
        profile_key=KEY,
        profile=profile,
        subtitle_profile=ResolvedSubtitleProfile(
            key=SubtitleProfileKey(
                component="studio",
                format="vertical",
                family="test_family",
                profile_id="dummy_profile",
            ),
            path=tmp_path / "dummy_profile.json",
            display_name="dummy_profile",
            cue_policy={},
            render_style={},
        ),
        output_path=tmp_path / "out" / "final.mp4",
    )

    assert "copy" not in runner.commands[0]
    assert "ass=" in " ".join(runner.commands[0])


def test_music_is_always_encoded(tmp_path):
    profile = _profile()
    _, runner, _, _ = _render(tmp_path, _matching_info(profile), music=True)

    assert "copy" not in runner.commands[0]
    assert "amix=" in " ".join(runner.commands[0])


def test_the_contract_checks_are_the_validator_ones():
    profile = _profile()

    assert StudioOutputValidator.contract_mismatches(_matching_info(profile), profile) == []
    assert StudioOutputValidator.contract_mismatches(
        _matching_info(profile, width=720, audio_codec=None), profile
    ) == ["resolución", "stream de audio", "codec de audio"]


def _stream_md5(path, stream):
    return subprocess.run(
        ["ffmpeg", "-v", "error", "-nostdin", "-i", str(path), "-map", f"0:{stream}:0",
         "-c", "copy", "-f", "md5", "-"],
        capture_output=True, check=True, text=True,
    ).stdout.strip()


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="FFmpeg no disponible",
)
def test_real_copy_keeps_the_streams_byte_for_byte(tmp_path):
    profile = _profile()
    source = tmp_path / "source.mp4"
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-nostdin", "-y",
            "-f", "lavfi", "-i",
            f"testsrc2=s={profile.width}x{profile.height}:r={profile.fps}:d=1",
            "-f", "lavfi", "-i",
            f"sine=f=440:r={profile.audio_sample_rate}:d=1",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", profile.pixel_format,
            "-c:a", "aac", "-ac", str(profile.audio_channels),
            "-ar", str(profile.audio_sample_rate),
            str(source),
        ],
        cwd=tmp_path,
        check=True,
    )

    result = StudioRenderService().render(
        video_path=source,
        profile_key=KEY,
        profile=profile,
        output_path=tmp_path / "out" / "final.mp4",
    )

    assert "copy" in result.command
    assert _stream_md5(result.output_path, "v") == _stream_md5(source, "v")
    assert _stream_md5(result.output_path, "a") == _stream_md5(source, "a")
