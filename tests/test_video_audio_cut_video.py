"""VIDEO + AUDIO | SRT: «Cortar el vídeo donde acaba el audio» (A1, fallo 9).

Decision of the owner: a new option when the audio is shorter, besides
«SIN MÚSICA» and «CON MÚSICA» (none is removed). With PARIS the video went
on 23 s after the voice.
"""

import shutil
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.cli.studio_summary import _audio_tail_label
from app.controllers.interaction.studio.video_audio_srt_selection import (
    StudioVideoAudioSrtSelection,
)
from app.modules.studio import (
    StudioProfileLoader,
    StudioVideoAudioSrtPlan,
    StudioVideoAudioSrtService,
)
from app.shared.media_probe import MediaInfo, MediaProbe
from app.shared.profile_identity import OperationalProfileKey
from app.shared.profile_resolver import ProfileResolver


KEY = OperationalProfileKey("studio", "vertical", "studio_vertical")


def _profile():
    return StudioProfileLoader().load(ProfileResolver().load_operational(KEY), KEY)


def _info(duration):
    return MediaInfo(
        duration=duration,
        width=1080,
        height=1920,
        fps=30.0,
        pixel_format="yuv420p",
        video_codec="h264",
        audio_codec="aac",
        audio_sample_rate=48000,
        audio_channels=2,
    )


def test_the_menu_offers_the_three_options_and_keeps_the_old_ones():
    probe = Mock()
    probe.inspect.return_value = _info(58.2)
    probe.get_duration.return_value = 35.5
    music = Mock()
    selection = StudioVideoAudioSrtSelection(
        Mock(), Mock(), probe, music, audio_tail_margin=lambda: 0.1
    )
    messages = []
    selector = Mock(return_value="cut_video")

    plan = selection.select_audio_tail(
        StudioVideoAudioSrtPlan(Path("PARIS.mp4"), Path("PARIS.mp3")),
        writer=messages.append,
        selector=selector,
    )

    assert messages == [
        "\nAUDIO MÁS CORTO QUE EL VÍDEO\n",
        "1. SIN MÚSICA",
        "2. CON MÚSICA",
        "3. CORTAR EL VÍDEO DONDE ACABA EL AUDIO",
    ]
    selector.assert_called_once_with(("silence", "music", "cut_video"))
    assert plan.audio_tail_mode == "cut_video"
    assert plan.music_path is None
    music.select.assert_not_called()


class _Runner:
    def run(self, command):
        self.command = tuple(command)
        Path(command[-1]).write_bytes(b"rendered")


class _Validator:
    def validate(self, output_path, expected_duration, profile):
        self.expected = expected_duration
        return expected_duration


def _render(tmp_path, video_duration, audio_duration, mode):
    (tmp_path / "v.mp4").write_bytes(b"video")
    (tmp_path / "a.mp3").write_bytes(b"audio")
    probe = Mock()
    probe.inspect.return_value = _info(video_duration)
    probe.get_duration.return_value = audio_duration
    validator = _Validator()
    _, duration, command = StudioVideoAudioSrtService(
        probe=probe, runner=_Runner(), validator=validator
    ).render(
        StudioVideoAudioSrtPlan(
            tmp_path / "v.mp4", tmp_path / "a.mp3", audio_tail_mode=mode
        ),
        tmp_path / "out.mp4",
        _profile(),
    )
    return duration, command, validator


def test_cutting_ends_video_and_audio_where_the_audio_ends(tmp_path):
    duration, command, validator = _render(tmp_path, 58.2, 35.5, "cut_video")

    graph = command[command.index("-filter_complex") + 1]
    assert "trim=duration=35.500000," in graph
    assert "atrim=duration=35.500000" in graph
    assert "58.2" not in graph
    assert "apad" not in graph
    assert "-stream_loop" not in command
    assert command[command.index("-t") + 1] == "35.500000"
    assert duration == validator.expected == 35.5


def test_a_longer_audio_is_never_a_reason_to_cut(tmp_path):
    duration, command, _ = _render(tmp_path, 10.0, 12.0, "cut_video")

    assert command[command.index("-t") + 1] == "10.000000"
    assert duration == 10.0


@pytest.mark.parametrize("mode", ("silence", "music_without_path"))
def test_the_other_options_still_keep_the_video_length(tmp_path, mode):
    if mode == "music_without_path":
        with pytest.raises(ValueError, match="pista musical"):
            _render(tmp_path, 10.0, 4.0, "music")
        return
    duration, command, _ = _render(tmp_path, 10.0, 4.0, mode)

    assert "apad,atrim=duration=10.000000" in command[command.index("-filter_complex") + 1]
    assert duration == 10.0


def test_summary_names_the_cut():
    assert _audio_tail_label("cut_video", 22.7) == "Vídeo cortado donde acaba el audio"


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="FFmpeg no disponible",
)
def test_real_render_lasts_what_the_audio_lasts(tmp_path):
    profile = _profile()
    video = tmp_path / "v.mp4"
    audio = tmp_path / "a.wav"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-nostdin", "-y", "-f", "lavfi", "-i",
         "testsrc2=s=360x640:r=30:d=4", "-f", "lavfi", "-i", "sine=f=220:d=4",
         "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
         "-c:a", "aac", str(video)],
        cwd=tmp_path, check=True,
    )
    subprocess.run(
        ["ffmpeg", "-v", "error", "-nostdin", "-y", "-f", "lavfi", "-i",
         "sine=f=440:r=48000:d=2", str(audio)],
        cwd=tmp_path, check=True,
    )
    profile = profile.__class__(**{**profile.__dict__, "preset": "ultrafast"})

    output, duration, _ = StudioVideoAudioSrtService().render(
        StudioVideoAudioSrtPlan(video, audio, audio_tail_mode="cut_video"),
        tmp_path / "out.mp4",
        profile,
    )

    info = MediaProbe().inspect(output)
    assert abs(info.duration - 2.0) < 0.1
    assert abs(duration - 2.0) < 0.1
    assert (info.width, info.height) == (profile.width, profile.height)
