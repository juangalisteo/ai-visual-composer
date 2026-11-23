"""Optional voice seed: read from the voice document, applied by Piper (I6).

Without ``seed`` everything works as before; with it, Piper gives the same
audio for the same text in every process. An invalid value is a CONFIG error
in Spanish that names the document.
"""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from app.controllers.interaction.common_options import CommonOptions
from app.modules.audio import piper_backend
from app.modules.audio.piper_backend import PiperBackend
from app.modules.audio.tts_backend_registry import TtsBackendRegistry
from app.modules.audio.tts_contracts import (
    TTS_SEED_MAX,
    ResolvedTtsVoice,
    TtsBackendError,
    TtsBackendErrorKind,
    TtsSynthesisRequest,
    TtsVoiceConfigurationError,
)
from app.modules.audio.voice_builder import VoiceBuilder
from app.modules.audio.voice_configuration import load_tts_voice_configuration
from app.modules.standard.execution_coordinator import _generated_script_pacing
from app.shared.config_manager import ConfigManager
from app.shared.operational_error import OperationalError
from tests.test_piper_backend import (
    FakePiperVoice,
    RecordingConfigFactory,
    _request,
    _write_model_pair,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VOICE_CONFIGS_PATH = REPOSITORY_ROOT / "config" / "voice_configs"
DAVEFX_MODEL = (
    REPOSITORY_ROOT
    / "models/audio/piper/es_ES_davefx/es_ES-davefx-medium.onnx"
)
SEED_MESSAGE = (
    f"seed debe ser un número entero entre 0 y {TTS_SEED_MAX} "
    "(sin «seed», la voz no repite el mismo audio); se recibió "
)
INVALID_SEEDS = ("1234", 12.0, True, -1, TTS_SEED_MAX + 1, None, [1])


def _document(**changes):
    document = json.loads(
        (VOICE_CONFIGS_PATH / "piper_davefx.json").read_text(encoding="utf-8")
    )
    document.update(changes)
    return document


def _write_voice_config(root, stem, document):
    voice_configs = root / "config" / "voice_configs"
    voice_configs.mkdir(parents=True, exist_ok=True)
    (voice_configs / f"{stem}.json").write_text(
        json.dumps(document), encoding="utf-8"
    )
    return voice_configs


# --- voice document -------------------------------------------------------


def test_current_voice_documents_declare_no_seed():
    for path in sorted(VOICE_CONFIGS_PATH.glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))

        assert "seed" not in document
        assert load_tts_voice_configuration(document).voice.seed is None


@pytest.mark.parametrize("seed", (0, 1234, TTS_SEED_MAX))
def test_seed_is_read_as_declared_data(seed):
    configuration = load_tts_voice_configuration(_document(seed=seed))

    assert configuration.voice.seed == seed


@pytest.mark.parametrize("seed", INVALID_SEEDS)
def test_invalid_seed_is_rejected_with_spanish_message(seed):
    with pytest.raises(TtsVoiceConfigurationError) as error:
        load_tts_voice_configuration(_document(seed=seed))

    assert str(error.value) == f"{SEED_MESSAGE}{seed!r}."


def test_resolved_voice_has_no_seed_by_default():
    voice = ResolvedTtsVoice(
        voice_id="test_voice",
        backend_key="test_backend",
        backend_voice_id=None,
        language="es-ES",
    )

    assert voice.seed is None


@pytest.mark.parametrize("seed", tuple(seed for seed in INVALID_SEEDS if seed is not None))
def test_resolved_voice_rejects_an_invalid_seed(seed):
    with pytest.raises(TtsVoiceConfigurationError) as error:
        ResolvedTtsVoice(
            voice_id="test_voice",
            backend_key="test_backend",
            backend_voice_id=None,
            language="es-ES",
            seed=seed,
        )

    assert str(error.value) == f"{SEED_MESSAGE}{seed!r}."


# --- CONFIG errors that name the document -----------------------------------


def test_config_manager_names_the_relative_document_with_the_invalid_seed(
    tmp_path, monkeypatch
):
    _write_voice_config(tmp_path, "test_voice_seed", _document(seed="1234"))
    monkeypatch.chdir(tmp_path)

    with pytest.raises(TtsVoiceConfigurationError) as error:
        ConfigManager(voice_config_id="test_voice_seed").get_tts_voice_configuration()

    assert str(error.value) == (
        "en «config/voice_configs/test_voice_seed.json», "
        f"{SEED_MESSAGE}'1234'."
    )


def test_config_manager_reads_a_valid_seed_from_the_selected_document(
    tmp_path, monkeypatch
):
    _write_voice_config(tmp_path, "test_voice_seed", _document(seed=99))
    monkeypatch.chdir(tmp_path)

    configuration = ConfigManager(
        voice_config_id="test_voice_seed"
    ).get_tts_voice_configuration()

    assert configuration.voice.seed == 99


class _NeverCalledBackend:
    backend_key = "piper_onnx"

    def __init__(self):
        self.requests = []

    def synthesize(self, request):
        self.requests.append(request)
        raise AssertionError("No debe sintetizar con una semilla no válida.")


def test_voice_builder_reports_an_invalid_seed_as_config_error_with_path(
    tmp_path, monkeypatch
):
    _write_voice_config(tmp_path, "test_voice_seed", _document(seed=-1))
    monkeypatch.chdir(tmp_path)
    backend = _NeverCalledBackend()
    builder = VoiceBuilder(
        config_manager=ConfigManager(voice_config_id="test_voice_seed"),
        backend_registry=TtsBackendRegistry((backend,)),
        workspace_parent=tmp_path / "workspaces",
    )

    with pytest.raises(OperationalError) as error:
        builder.build("Texto de prueba.", output_path=tmp_path / "voz.mp3")

    context = error.value.context
    assert context.family == "CONFIG"
    assert context.user_message == (
        "La configuración de la voz no es válida: en "
        "«config/voice_configs/test_voice_seed.json», "
        f"{SEED_MESSAGE}-1."
    )
    assert backend.requests == []


def test_topic_script_reports_an_invalid_seed_as_config_error_with_path(
    tmp_path, monkeypatch
):
    _write_voice_config(tmp_path, "test_voice_seed", _document(seed=True))
    monkeypatch.chdir(tmp_path)

    with pytest.raises(OperationalError) as error:
        _generated_script_pacing(ConfigManager(voice_config_id="test_voice_seed"))

    assert error.value.context.family == "CONFIG"
    assert "«config/voice_configs/test_voice_seed.json», seed debe ser" in (
        error.value.context.user_message
    )


def test_voice_menu_reports_an_invalid_seed_as_config_error_with_path(
    tmp_path, monkeypatch
):
    _write_voice_config(tmp_path, "test_voice_seed", _document(seed=12.0))
    monkeypatch.chdir(tmp_path)
    options = CommonOptions(
        SimpleNamespace(write=lambda message: None),
        lambda: pytest.fail("No debe cancelar"),
        Path("config/voice_configs"),
    )

    with pytest.raises(OperationalError) as error:
        options.select_voice_config(selector=lambda items: items[0])

    context = error.value.context
    assert context.family == "CONFIG"
    assert context.user_message == (
        "La configuración de la voz no es válida: en "
        "«config/voice_configs/test_voice_seed.json», "
        f"{SEED_MESSAGE}12.0."
    )
    assert context.resource == "config/voice_configs/test_voice_seed.json"
    assert "config/voice_configs/test_voice_seed.json" in context.recommended_action
    assert isinstance(error.value.__cause__, TtsVoiceConfigurationError)


# --- Piper applies the seed -------------------------------------------------


class _Events:
    def __init__(self):
        self.items = []

    def seed_setter(self, seed):
        self.items.append(("seed", seed))

    def voice_factory(self, model_path, sidecar_path):
        self.items.append(("load", model_path.name))
        return FakePiperVoice()


def _seeded_request(tmp_path, relative, seed):
    request = _request(tmp_path, relative)
    voice = request.voice
    return TtsSynthesisRequest(
        text=request.text,
        voice=ResolvedTtsVoice(
            voice_id=voice.voice_id,
            backend_key=voice.backend_key,
            backend_voice_id=voice.backend_voice_id,
            language=voice.language,
            prosody=voice.prosody,
            backend_options=voice.backend_options,
            seed=seed,
        ),
        workspace=request.workspace,
    )


def _piper(root, events):
    return PiperBackend(
        root,
        piper_voice_factory=events.voice_factory,
        synthesis_config_factory=RecordingConfigFactory(),
        seed_setter=events.seed_setter,
    )


def test_piper_fixes_the_declared_seed_before_loading_the_model(tmp_path):
    relative, _ = _write_model_pair(tmp_path)
    events = _Events()

    _piper(tmp_path, events).synthesize(_seeded_request(tmp_path, relative, 1234))

    assert events.items == [("seed", 1234), ("load", "voice.onnx")]


def test_piper_without_seed_does_not_touch_the_seed(tmp_path):
    relative, _ = _write_model_pair(tmp_path)
    events = _Events()

    _piper(tmp_path, events).synthesize(_request(tmp_path, relative))

    assert events.items == [("load", "voice.onnx")]


def test_piper_fixes_the_seed_again_for_every_request(tmp_path):
    relative, _ = _write_model_pair(tmp_path)
    events = _Events()
    backend = _piper(tmp_path, events)

    backend.synthesize(_seeded_request(tmp_path, relative, 7))
    backend.synthesize(_seeded_request(tmp_path, relative, 8))

    assert events.items == [
        ("seed", 7),
        ("load", "voice.onnx"),
        ("seed", 8),
        ("load", "voice.onnx"),
    ]


def test_seed_failure_is_resource_unavailable_and_loads_nothing(tmp_path):
    relative, _ = _write_model_pair(tmp_path)
    events = _Events()
    cause = RuntimeError("fixture")

    def failing_seed_setter(seed):
        raise cause

    backend = PiperBackend(
        tmp_path,
        piper_voice_factory=events.voice_factory,
        synthesis_config_factory=RecordingConfigFactory(),
        seed_setter=failing_seed_setter,
    )

    with pytest.raises(TtsBackendError) as error:
        backend.synthesize(_seeded_request(tmp_path, relative, 3))

    assert error.value.diagnostic.kind is TtsBackendErrorKind.RESOURCE_UNAVAILABLE
    assert error.value.__cause__ is cause
    assert events.items == []


def test_default_seed_setter_fixes_the_onnxruntime_seed(monkeypatch):
    calls = []
    monkeypatch.setitem(
        sys.modules, "onnxruntime", SimpleNamespace(set_seed=calls.append)
    )

    piper_backend._default_seed_setter(4321)

    assert calls == [4321]


def test_default_backend_uses_the_onnxruntime_seed_setter(tmp_path):
    backend = PiperBackend(tmp_path)

    assert backend._seed_setter is piper_backend._default_seed_setter


# --- real Piper: same audio in two processes ----------------------------------


_SYNTHESIZE_IN_A_NEW_PROCESS = """
import hashlib, sys
from pathlib import Path
from app.modules.audio.piper_backend import PiperBackend
from app.modules.audio.tts_contracts import (
    ResolvedTtsVoice, TtsSynthesisRequest, TtsSynthesisWorkspace,
)
root, workspace, seed = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
result = PiperBackend(root).synthesize(TtsSynthesisRequest(
    text="Tesla no solo cambió el mundo, sino que lo imaginó primero.",
    voice=ResolvedTtsVoice(
        voice_id="test_voice", backend_key="piper_onnx", backend_voice_id=None,
        language="es-ES",
        backend_options={"model": {"onnx_path": sys.argv[4]}},
        seed=seed,
    ),
    workspace=TtsSynthesisWorkspace(workspace_id="seed-test", path=workspace),
))
print(hashlib.sha256(result.staged_audio.path.read_bytes()).hexdigest())
"""


def _audio_hash_in_new_process(tmp_path, name, seed):
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            _SYNTHESIZE_IN_A_NEW_PROCESS,
            str(REPOSITORY_ROOT),
            str(tmp_path / name),
            str(seed),
            DAVEFX_MODEL.relative_to(REPOSITORY_ROOT).as_posix(),
        ],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


@pytest.mark.skipif(
    not DAVEFX_MODEL.is_file(),
    reason="Falta la voz Piper en models/audio/piper/es_ES_davefx/.",
)
def test_real_piper_gives_the_same_audio_in_two_processes_with_the_same_seed(
    tmp_path,
):
    first = _audio_hash_in_new_process(tmp_path, "first", 1234)
    second = _audio_hash_in_new_process(tmp_path, "second", 1234)
    other_seed = _audio_hash_in_new_process(tmp_path, "other", 4321)

    assert first == second
    assert other_seed != first
    assert len(first) == len(hashlib.sha256().hexdigest())
