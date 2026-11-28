"""Whisper's Triton and CUDA caches stay inside the project (A2-L, A3; folder rule)."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.modules.subtitles.io.subtitle_builder import SubtitleBuilder
from app.modules.subtitles.io.whisper_settings import (
    whisper_cuda_cache_dir,
    whisper_triton_cache_dir,
)
from app.modules.subtitles.io.whisper_transcription_config import (
    WhisperTranscriptionConfig,
)
from app.shared.operational_error import OperationalError

REAL_CONFIG = Path(__file__).resolve().parents[1] / "config" / "whisper.json"
TRANSCRIPTION = {"model": "test_model", "device": "test_device", "language": "test_language"}

# (key, reader, the value of the project, which the CONFIG error gives as example)
FOLDERS = (
    ("triton_cache_dir", whisper_triton_cache_dir, "models/whisper/_cache/triton"),
    ("cuda_cache_dir", whisper_cuda_cache_dir, "models/whisper/_cache/cuda"),
)
FOLDER_IDS = [key for key, _, _ in FOLDERS]


def _settings(tmp_path, **values):
    path = tmp_path / "config" / "whisper.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({**TRANSCRIPTION, **values}), encoding="utf-8")
    return path


@pytest.mark.parametrize(("key", "reader", "example"), FOLDERS, ids=FOLDER_IDS)
def test_the_folder_is_resolved_inside_the_project(tmp_path, key, reader, example):
    path = _settings(tmp_path, **{key: " test_cache/folder "})

    folder = reader(path, project_root=tmp_path)

    assert folder == tmp_path / "test_cache" / "folder"
    assert folder.is_absolute()
    assert not folder.exists()


@pytest.mark.parametrize(("key", "reader", "example"), FOLDERS, ids=FOLDER_IDS)
def test_without_a_project_root_the_working_folder_is_the_project(
    tmp_path, monkeypatch, key, reader, example
):
    monkeypatch.chdir(tmp_path)
    path = _settings(tmp_path, **{key: "test_cache/folder"})

    assert reader(path) == tmp_path / "test_cache" / "folder"


@pytest.mark.parametrize(("key", "reader", "example"), FOLDERS, ids=FOLDER_IDS)
def test_a_missing_key_is_a_config_error(tmp_path, key, reader, example):
    other = {other_key: "test_cache/other" for other_key, _, _ in FOLDERS if other_key != key}
    path = _settings(tmp_path, **other)

    with pytest.raises(OperationalError) as caught:
        reader(path, project_root=tmp_path)

    context = caught.value.context
    assert context.family == "CONFIG"
    assert context.user_message.endswith(f"no declara «{key}».")
    assert context.technical_metadata == {"key": key}


@pytest.mark.parametrize(("key", "reader", "example"), FOLDERS, ids=FOLDER_IDS)
@pytest.mark.parametrize(
    "value",
    ("", "   ", None, 3, ["x"], "C:/fuera", "/fuera", "C:fuera", "../fuera", "a/../../fuera", ".", "a/.."),
)
def test_a_folder_outside_the_project_or_not_a_path_is_a_config_error(
    tmp_path, key, reader, example, value
):
    path = _settings(tmp_path, **{key: value})

    with pytest.raises(OperationalError) as caught:
        reader(path, project_root=tmp_path)

    context = caught.value.context
    assert context.family == "CONFIG"
    assert f"«{key}» debe ser una carpeta relativa" in context.user_message
    assert "dentro de la carpeta del proyecto" in context.user_message
    assert f"una carpeta del proyecto que Git ignore, por ejemplo {example}." in (
        context.recommended_action
    )
    assert context.technical_metadata == {"key": key}


@pytest.mark.parametrize(("key", "reader", "example"), FOLDERS, ids=FOLDER_IDS)
def test_the_project_declares_an_ignored_folder_under_models(key, reader, example):
    value = json.loads(REAL_CONFIG.read_text(encoding="utf-8"))[key]
    gitignore = (REAL_CONFIG.parents[1] / ".gitignore").read_text(encoding="utf-8")

    assert value == example
    assert "/models/" in gitignore.splitlines()


def _environment_of_whisper(builder, tmp_path, seen_folders=()):
    seen = {}
    audio = tmp_path / "voz.mp3"
    audio.write_bytes(b"x")

    def whisper(command, **options):
        seen.update(options["env"])
        seen["__existing__"] = [folder.is_dir() for folder in seen_folders]
        folder = Path(command[command.index("--output_dir") + 1])
        (folder / "voz.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nHola\n", encoding="utf-8")

    with patch("app.modules.subtitles.io.subtitle_builder.subprocess.run", side_effect=whisper):
        builder.build(audio_path=audio, output_path=tmp_path / "out" / "voz.srt")
    return seen


def test_whisper_gets_the_folders_as_triton_cache_dir_and_cuda_cache_path(tmp_path):
    triton = tmp_path / "test_cache" / "triton"
    cuda = tmp_path / "test_cache" / "cuda"
    builder = SubtitleBuilder(
        transcription_config=WhisperTranscriptionConfig(**TRANSCRIPTION),
        triton_cache_dir=triton,
        cuda_cache_dir=cuda,
    )

    environment = _environment_of_whisper(builder, tmp_path, seen_folders=(cuda, triton))

    assert environment["TRITON_CACHE_DIR"] == str(triton)
    assert environment["CUDA_CACHE_PATH"] == str(cuda)
    assert environment["PYTHONIOENCODING"] == "utf-8"
    # CUDA does not create its folder (it then keeps no cache): it exists
    # before Whisper starts. Triton creates its own.
    assert environment["__existing__"] == [True, False]


@pytest.mark.real_whisper_cuda_cache
def test_without_injected_folders_they_are_read_from_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _settings(tmp_path, triton_cache_dir="test_cache/triton", cuda_cache_dir="test_cache/cuda")

    environment = _environment_of_whisper(SubtitleBuilder(), tmp_path)

    assert environment["TRITON_CACHE_DIR"] == str(tmp_path / "test_cache" / "triton")
    assert environment["CUDA_CACHE_PATH"] == str(tmp_path / "test_cache" / "cuda")
    assert (tmp_path / "test_cache" / "cuda").is_dir()


@pytest.mark.real_whisper_cuda_cache
@pytest.mark.parametrize("key", FOLDER_IDS)
def test_a_wrong_folder_stops_before_running_whisper(tmp_path, monkeypatch, key):
    monkeypatch.chdir(tmp_path)
    _settings(
        tmp_path,
        **{
            "triton_cache_dir": "test_cache/triton",
            "cuda_cache_dir": "test_cache/cuda",
            key: "../fuera",
        },
    )
    audio = tmp_path / "voz.mp3"
    audio.write_bytes(b"x")

    with patch("app.modules.subtitles.io.subtitle_builder.subprocess.run") as run, pytest.raises(
        OperationalError
    ) as caught:
        SubtitleBuilder().build(audio_path=audio, output_path=tmp_path / "voz.srt")

    run.assert_not_called()
    assert caught.value.context.family == "CONFIG"
    assert caught.value.context.technical_metadata == {"key": key}
    assert not (tmp_path.parent / "fuera").exists()


def test_a_cuda_folder_that_cannot_be_created_stops_before_running_whisper(tmp_path):
    blocker = tmp_path / "test_cache"
    blocker.write_text("not a folder", encoding="utf-8")
    cuda = blocker / "cuda"
    builder = SubtitleBuilder(
        transcription_config=WhisperTranscriptionConfig(**TRANSCRIPTION),
        triton_cache_dir=tmp_path / "triton",
        cuda_cache_dir=cuda,
    )
    audio = tmp_path / "voz.mp3"
    audio.write_bytes(b"x")

    with patch("app.modules.subtitles.io.subtitle_builder.subprocess.run") as run, pytest.raises(
        OperationalError
    ) as caught:
        builder.build(audio_path=audio, output_path=tmp_path / "out" / "voz.srt")

    run.assert_not_called()
    context = caught.value.context
    assert context.family == "FILESYSTEM"
    assert context.user_message == "No se pudo crear la carpeta de la caché de CUDA de Whisper."
    assert "«cuda_cache_dir» en config/whisper.json" in context.recommended_action
    assert context.resource == str(cuda)
