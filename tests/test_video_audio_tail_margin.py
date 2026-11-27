"""VIDEO + AUDIO | SRT: a few milliseconds of difference are not «shorter audio» (A1).

PRUEBA-GS, fallo 6: with TESEOBARCO the menu asked «AUDIO MÁS CORTO QUE EL
VÍDEO» for 6 ms and padded them. Under the margin of config/studio.json,
nothing is asked and nothing is added.
"""

import json
import tempfile
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
from app.modules.studio.studio_settings import video_audio_tail_margin
from app.shared.media_probe import MediaInfo
from app.shared.operational_error import OperationalError
from app.shared.profile_identity import OperationalProfileKey
from app.shared.profile_resolver import ProfileResolver


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


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


def _selection(video_duration, audio_duration, margin=0.1):
    probe = Mock()
    probe.inspect.return_value = _info(video_duration)
    probe.get_duration.return_value = audio_duration
    margin_reader = Mock(return_value=margin)
    music = Mock()
    music.select.return_value = Path("assets/music/tail.mp3")
    selection = StudioVideoAudioSrtSelection(
        Mock(), Mock(), probe, music, audio_tail_margin=margin_reader
    )
    return selection, margin_reader


@pytest.mark.parametrize("audio_duration", (38.699, 38.6051, 38.705, 40.0))
def test_no_question_when_the_audio_is_not_shorter_than_the_margin(audio_duration):
    selection, _ = _selection(38.705, audio_duration)
    messages = []
    selector = Mock()

    plan = selection.select_audio_tail(
        StudioVideoAudioSrtPlan(Path("v.mp4"), Path("a.mp3")),
        writer=messages.append,
        selector=selector,
    )

    assert messages == []
    selector.assert_not_called()
    assert (plan.video_duration, plan.audio_duration) == (38.705, audio_duration)
    expected_mode = "none" if audio_duration < 38.705 else "silence"
    assert plan.audio_tail_mode == expected_mode
    assert plan.music_path is None


@pytest.mark.parametrize(
    ("video_duration", "audio_duration"),
    # 10.0 - 9.9 is 0.09999999999999964 in floating point: still the margin.
    ((38.705, 38.605), (38.705, 38.6), (38.705, 30.0), (10.0, 9.9)),
)
def test_from_the_margin_on_the_question_is_asked(video_duration, audio_duration):
    selection, margin_reader = _selection(video_duration, audio_duration)
    messages = []

    plan = selection.select_audio_tail(
        StudioVideoAudioSrtPlan(Path("v.mp4"), Path("a.mp3")),
        writer=messages.append,
        selector=Mock(return_value="silence"),
    )

    assert "\nAUDIO MÁS CORTO QUE EL VÍDEO\n" in messages
    assert plan.audio_tail_mode == "silence"
    margin_reader.assert_called_once_with()


def test_a_longer_audio_never_reads_the_margin():
    selection, margin_reader = _selection(10.0, 12.0)

    selection.select_audio_tail(
        StudioVideoAudioSrtPlan(Path("v.mp4"), Path("a.mp3")),
        writer=lambda message: None,
        selector=Mock(),
    )

    margin_reader.assert_not_called()


def test_zero_margin_asks_for_any_difference():
    selection, _ = _selection(10.0, 9.999, margin=0.0)
    selector = Mock(return_value="music")

    plan = selection.select_audio_tail(
        StudioVideoAudioSrtPlan(Path("v.mp4"), Path("a.mp3")),
        writer=lambda message: None,
        selector=selector,
    )

    selector.assert_called_once()
    assert plan.audio_tail_mode == "music"


def test_the_default_margin_comes_from_config_studio(monkeypatch):
    monkeypatch.chdir(REPOSITORY_ROOT)
    probe = Mock()
    probe.inspect.return_value = _info(10.0)
    probe.get_duration.return_value = 9.95
    selection = StudioVideoAudioSrtSelection(Mock(), Mock(), probe, Mock())

    plan = selection.select_audio_tail(
        StudioVideoAudioSrtPlan(Path("v.mp4"), Path("a.mp3")),
        writer=lambda message: None,
        selector=Mock(),
    )

    assert plan.audio_tail_mode == "none"


# --- render -----------------------------------------------------------------


class _Runner:
    def run(self, command):
        self.command = tuple(command)
        Path(command[-1]).write_bytes(b"rendered")


class _Validator:
    def validate(self, output_path, expected_duration, profile):
        self.expected = expected_duration
        return expected_duration


def _profile():
    key = OperationalProfileKey("studio", "vertical", "studio_vertical")
    return StudioProfileLoader().load(ProfileResolver().load_operational(key), key)


def test_render_within_the_margin_adds_nothing_after_the_audio():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "v.mp4").write_bytes(b"video")
        (root / "a.mp3").write_bytes(b"audio")
        probe = Mock()
        probe.inspect.return_value = _info(38.705)
        probe.get_duration.return_value = 38.699
        runner, validator = _Runner(), _Validator()

        _, duration, command = StudioVideoAudioSrtService(
            probe=probe, runner=runner, validator=validator
        ).render(
            StudioVideoAudioSrtPlan(
                root / "v.mp4", root / "a.mp3", audio_tail_mode="none"
            ),
            root / "out.mp4",
            _profile(),
        )

    graph = command[command.index("-filter_complex") + 1]
    assert "apad" not in graph
    assert "-stream_loop" not in command
    assert "atrim=duration=38.705000" in graph
    assert duration == validator.expected == 38.705


def test_render_with_silence_still_pads_a_shorter_audio():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "v.mp4").write_bytes(b"video")
        (root / "a.mp3").write_bytes(b"audio")
        probe = Mock()
        probe.inspect.return_value = _info(10.0)
        probe.get_duration.return_value = 9.0

        _, _, command = StudioVideoAudioSrtService(
            probe=probe, runner=_Runner(), validator=_Validator()
        ).render(
            StudioVideoAudioSrtPlan(root / "v.mp4", root / "a.mp3"),
            root / "out.mp4",
            _profile(),
        )

    assert "apad,atrim=duration=10.000000" in command[command.index("-filter_complex") + 1]


@pytest.mark.parametrize(
    ("mode", "label"),
    (
        ("none", "Sin cambios (el audio dura 0.006 s menos, dentro del margen)"),
        ("music", "Audio + música final"),
        ("silence", "Audio + silencio final"),
    ),
)
def test_summary_says_how_the_shorter_audio_was_treated(mode, label):
    assert _audio_tail_label(mode, 0.006) == label


# --- config/studio.json --------------------------------------------------------


def test_the_project_declares_a_tenth_of_a_second():
    assert video_audio_tail_margin(REPOSITORY_ROOT / "config" / "studio.json") == 0.1


def _write(tmp_path, document):
    path = tmp_path / "config" / "studio.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        document if isinstance(document, str) else json.dumps(document),
        encoding="utf-8",
    )
    return path


def _config_error(path):
    with pytest.raises(OperationalError) as raised:
        video_audio_tail_margin(path)
    context = raised.value.context
    assert context.family == "CONFIG"
    assert context.resource == path.as_posix()
    assert context.operation == "Cargar configuración de STUDIO"
    return context


def test_missing_file_names_its_relative_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(OperationalError) as raised:
        video_audio_tail_margin()

    assert raised.value.context.family == "CONFIG"
    assert raised.value.context.user_message == (
        "Falta el archivo de configuración «config/studio.json»."
    )


@pytest.mark.parametrize(
    ("document", "message"),
    (
        ({}, "no declara «video_audio_srt»."),
        ({"video_audio_srt": {}}, "no declara «video_audio_srt.audio_tail_margin_seconds»."),
    ),
)
def test_missing_keys_are_config_errors(tmp_path, document, message):
    path = _write(tmp_path, document)

    context = _config_error(path)

    assert context.user_message == f"«{path.as_posix()}» {message}"
    assert context.technical_metadata == {
        "key": "video_audio_srt.audio_tail_margin_seconds"
    }


@pytest.mark.parametrize("value", (-0.1, "0.1", True, None, [0.1]))
def test_the_margin_must_be_seconds_zero_or_more(tmp_path, value):
    path = _write(tmp_path, {"video_audio_srt": {"audio_tail_margin_seconds": value}})

    context = _config_error(path)

    assert context.user_message == (
        f"En «{path.as_posix()}», «video_audio_srt.audio_tail_margin_seconds» "
        f"debe ser un número de segundos mayor o igual que 0; se recibió {value!r}."
    )


def test_zero_and_whole_numbers_are_accepted(tmp_path):
    assert video_audio_tail_margin(
        _write(tmp_path, {"video_audio_srt": {"audio_tail_margin_seconds": 0}})
    ) == 0.0
