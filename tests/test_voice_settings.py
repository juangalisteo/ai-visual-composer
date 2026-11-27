"""Working folder of the voice, declared in config/voice.json (T0)."""

import json
import tempfile
from pathlib import Path

import pytest

from app.modules.audio import voice_builder as voice_builder_module
from app.modules.audio.tts_backend_registry import TtsBackendRegistry
from app.modules.audio.tts_contracts import TtsAudioArtifact, TtsSynthesisResult
from app.modules.audio.voice_builder import VoiceBuilder
from app.modules.audio.voice_configuration import load_tts_voice_configuration
from app.modules.audio.voice_settings import voice_workspace_dir
from app.shared.operational_error import OperationalError


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _write(tmp_path, content):
    path = tmp_path / "config" / "voice.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _config_error(path, project_root):
    with pytest.raises(OperationalError) as raised:
        voice_workspace_dir(path, project_root=project_root)
    context = raised.value.context
    assert context.family == "CONFIG"
    assert context.resource == path.as_posix()
    return context


def test_the_project_declares_tmp_voice_inside_the_project_and_ignored_by_git():
    folder = voice_workspace_dir(
        REPOSITORY_ROOT / "config" / "voice.json",
        project_root=REPOSITORY_ROOT,
    )

    assert folder == REPOSITORY_ROOT / "tmp" / "voice"
    gitignore = (REPOSITORY_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "tmp/" in gitignore.splitlines()


def test_declared_folder_is_resolved_against_the_project(tmp_path):
    path = _write(tmp_path, json.dumps({"workspace_dir": " otra/carpeta "}))

    assert voice_workspace_dir(path, project_root=tmp_path) == (
        tmp_path / "otra" / "carpeta"
    )


def test_missing_file_is_a_config_error(tmp_path):
    context = _config_error(tmp_path / "config" / "voice.json", tmp_path)

    assert "Falta el archivo de configuración de la voz" in context.user_message
    assert "config/voice.json" in context.user_message


def test_missing_key_is_a_config_error(tmp_path):
    path = _write(tmp_path, json.dumps({"otra": "tmp/voice"}))

    context = _config_error(path, tmp_path)

    assert context.user_message == (
        f"«{path.as_posix()}» no declara «workspace_dir», la carpeta de "
        "trabajo de la voz."
    )
    assert context.technical_metadata == {"key": "workspace_dir"}


@pytest.mark.parametrize("value", (None, "", "   ", 3, ["tmp/voice"]))
def test_a_value_that_is_not_a_path_is_a_config_error(tmp_path, value):
    path = _write(tmp_path, json.dumps({"workspace_dir": value}))

    context = _config_error(path, tmp_path)

    assert "debe ser una ruta relativa a la carpeta del proyecto" in (
        context.user_message
    )


@pytest.mark.parametrize(
    "value",
    ("../fuera", "tmp/../../fuera", ".", "tmp/.."),
)
def test_a_folder_outside_the_project_or_the_project_itself_is_a_config_error(
    tmp_path, value
):
    path = _write(tmp_path, json.dumps({"workspace_dir": value}))

    context = _config_error(path, tmp_path)

    assert "debe ser una carpeta dentro de la carpeta del proyecto" in (
        context.user_message
    )


def test_an_absolute_folder_is_a_config_error(tmp_path):
    inside = (tmp_path / "tmp" / "voice").as_posix()
    path = _write(tmp_path, json.dumps({"workspace_dir": inside}))

    context = _config_error(path, tmp_path)

    assert "debe ser una carpeta dentro de la carpeta del proyecto" in (
        context.user_message
    )


@pytest.mark.parametrize(
    ("content", "problem"),
    (
        ("{", "no es un JSON válido (línea 1)"),
        ("[]", "debe ser un objeto JSON"),
        ('"tmp/voice"', "debe ser un objeto JSON"),
    ),
)
def test_a_document_that_is_not_a_json_object_is_a_config_error(
    tmp_path, content, problem
):
    path = _write(tmp_path, content)

    context = _config_error(path, tmp_path)

    assert context.user_message == f"«{path.as_posix()}» {problem}."


class _Manager:
    def get_tts_voice_configuration(self):
        return load_tts_voice_configuration(
            json.loads(
                (
                    REPOSITORY_ROOT / "config" / "voice_configs" / "piper_davefx.json"
                ).read_text(encoding="utf-8")
            )
        )


class _Backend:
    backend_key = "piper_onnx"

    def __init__(self):
        self.workspaces = []

    def synthesize(self, request):
        self.workspaces.append(request.workspace.path)
        staged = request.workspace.path / "staged.mp3"
        staged.write_bytes(b"audio")
        return TtsSynthesisResult(
            staged_audio=TtsAudioArtifact(
                path=staged,
                container="mp3",
                codec="mp3",
                sample_rate_hz=44_100,
                channels=1,
            ),
            word_timings=None,
        )


def test_voice_builder_works_in_the_declared_folder_and_not_in_the_system_temp(
    tmp_path, monkeypatch
):
    declared = tmp_path / "proyecto" / "tmp" / "voice"
    system_temp = tmp_path / "temp_del_sistema"
    system_temp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(system_temp))
    monkeypatch.setattr(
        voice_builder_module, "voice_workspace_dir", lambda: declared
    )
    backend = _Backend()

    VoiceBuilder(
        config_manager=_Manager(),
        backend_registry=TtsBackendRegistry((backend,)),
    ).build("Texto de prueba.", output_path=tmp_path / "voz.mp3")

    assert len(backend.workspaces) == 1
    assert backend.workspaces[0].parent == declared
    assert backend.workspaces[0].name.startswith("ai_visual_composer_tts_")
    assert not backend.workspaces[0].exists()
    assert declared.is_dir()
    assert list(system_temp.iterdir()) == []
    assert (tmp_path / "voz.mp3").read_bytes() == b"audio"


def test_voice_builder_without_the_setting_stops_with_config_before_synthesis(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    backend = _Backend()

    with pytest.raises(OperationalError) as raised:
        VoiceBuilder(
            config_manager=_Manager(),
            backend_registry=TtsBackendRegistry((backend,)),
        ).build("Texto de prueba.", output_path=tmp_path / "voz.mp3")

    context = raised.value.context
    assert context.family == "CONFIG"
    assert context.resource == "config/voice.json"
    assert backend.workspaces == []
    assert not (tmp_path / "voz.mp3").exists()
