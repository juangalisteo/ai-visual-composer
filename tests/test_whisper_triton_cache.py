"""Whisper's Triton cache stays inside the project (A2-L, folder rule)."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.modules.subtitles.io.subtitle_builder import SubtitleBuilder
from app.modules.subtitles.io.whisper_settings import whisper_triton_cache_dir
from app.modules.subtitles.io.whisper_transcription_config import (
    WhisperTranscriptionConfig,
)
from app.shared.operational_error import OperationalError

REAL_CONFIG = Path(__file__).resolve().parents[1] / "config" / "whisper.json"
TRANSCRIPTION = {"model": "test_model", "device": "test_device", "language": "test_language"}


def _settings(tmp_path, **values):
    path = tmp_path / "config" / "whisper.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({**TRANSCRIPTION, **values}), encoding="utf-8")
    return path


def test_the_folder_is_resolved_inside_the_project(tmp_path):
    path = _settings(tmp_path, triton_cache_dir=" test_cache/triton ")

    folder = whisper_triton_cache_dir(path, project_root=tmp_path)

    assert folder == tmp_path / "test_cache" / "triton"
    assert folder.is_absolute()
    assert not folder.exists()


def test_without_a_project_root_the_working_folder_is_the_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = _settings(tmp_path, triton_cache_dir="test_cache/triton")

    assert whisper_triton_cache_dir(path) == tmp_path / "test_cache" / "triton"


def test_a_missing_key_is_a_config_error(tmp_path):
    path = _settings(tmp_path)

    with pytest.raises(OperationalError) as caught:
        whisper_triton_cache_dir(path, project_root=tmp_path)

    context = caught.value.context
    assert context.family == "CONFIG"
    assert context.user_message.endswith("no declara «triton_cache_dir».")
    assert context.technical_metadata == {"key": "triton_cache_dir"}


@pytest.mark.parametrize(
    "value",
    ("", "   ", None, 3, ["x"], "C:/fuera", "/fuera", "C:fuera", "../fuera", "a/../../fuera", ".", "a/.."),
)
def test_a_folder_outside_the_project_or_not_a_path_is_a_config_error(tmp_path, value):
    path = _settings(tmp_path, triton_cache_dir=value)

    with pytest.raises(OperationalError) as caught:
        whisper_triton_cache_dir(path, project_root=tmp_path)

    context = caught.value.context
    assert context.family == "CONFIG"
    assert "«triton_cache_dir» debe ser una carpeta relativa" in context.user_message
    assert "dentro de la carpeta del proyecto" in context.user_message
    assert "models/whisper/_cache/triton" in context.recommended_action


def test_the_project_declares_an_ignored_folder_under_models():
    value = json.loads(REAL_CONFIG.read_text(encoding="utf-8"))["triton_cache_dir"]
    gitignore = (REAL_CONFIG.parents[1] / ".gitignore").read_text(encoding="utf-8")

    assert value == "models/whisper/_cache/triton"
    assert "/models/" in gitignore.splitlines()


def _environment_of_whisper(builder, tmp_path):
    seen = {}
    audio = tmp_path / "voz.mp3"
    audio.write_bytes(b"x")

    def whisper(command, **options):
        seen.update(options["env"])
        folder = Path(command[command.index("--output_dir") + 1])
        (folder / "voz.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nHola\n", encoding="utf-8")

    with patch("app.modules.subtitles.io.subtitle_builder.subprocess.run", side_effect=whisper):
        builder.build(audio_path=audio, output_path=tmp_path / "out" / "voz.srt")
    return seen


def test_whisper_gets_the_folder_as_triton_cache_dir(tmp_path):
    folder = tmp_path / "test_cache" / "triton"
    builder = SubtitleBuilder(
        transcription_config=WhisperTranscriptionConfig(**TRANSCRIPTION),
        triton_cache_dir=folder,
    )

    environment = _environment_of_whisper(builder, tmp_path)

    assert environment["TRITON_CACHE_DIR"] == str(folder)
    assert environment["PYTHONIOENCODING"] == "utf-8"


def test_without_an_injected_folder_it_is_read_from_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _settings(tmp_path, triton_cache_dir="test_cache/triton")

    environment = _environment_of_whisper(SubtitleBuilder(), tmp_path)

    assert environment["TRITON_CACHE_DIR"] == str(tmp_path / "test_cache" / "triton")


def test_a_wrong_folder_stops_before_running_whisper(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _settings(tmp_path, triton_cache_dir="../fuera")
    audio = tmp_path / "voz.mp3"
    audio.write_bytes(b"x")

    with patch("app.modules.subtitles.io.subtitle_builder.subprocess.run") as run, pytest.raises(
        OperationalError
    ):
        SubtitleBuilder().build(audio_path=audio, output_path=tmp_path / "voz.srt")

    run.assert_not_called()
