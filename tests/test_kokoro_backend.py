"""Kokoro backend in its own process (I6c).

The worker process is simulated: these tests never load torch or the model.
They cover the options read from the voice document and their CONFIG errors
with relative paths, the request sent to the worker (seed included), joining
the segment WAVs, the worker's error results, the worker itself with fake
``torch``, ``kokoro`` and ``soundfile`` modules, the registry and the two
project voice documents.
"""

import json
import os
from pathlib import Path
import sys
import types
import wave

import pytest

from app.modules.audio.external_tts_process import ExternalTtsProcess
from app.modules.audio.kokoro_backend import KokoroBackend
from app.modules.audio.tts_backend_registry import TtsBackendRegistry
from app.modules.audio.tts_backend_runtime import build_default_tts_backend_registry
from app.modules.audio.tts_contracts import (
    ResolvedTtsVoice,
    TtsBackendError,
    TtsBackendErrorKind,
    TtsProsody,
    TtsSynthesisRequest,
    TtsSynthesisWorkspace,
    TtsVoiceConfigurationError,
)
from app.modules.audio.voice_builder import VoiceBuilder
from app.modules.audio.voice_configuration import load_tts_voice_configuration
from app.modules.audio.workers import kokoro_worker
from app.shared.operational_error import OperationalError


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VOICE_CONFIGS = REPOSITORY_ROOT / "config/voice_configs"
PYTHON = "test_runtime/env/python.exe"
CONFIG_FILE = "test_runtime/weights/config.json"
WEIGHTS_FILE = "test_runtime/weights/model.pth"
VOICE_FILE = "test_runtime/weights/voices/test_voice.pt"
RATE = 24_000
TEXT = "Primera frase. Segunda frase.\n\nTercera frase."
SETUP_HINT = (
    "Monta el entorno de la voz (docs/INSTALL.md, apartado 10) o corrige la "
    "ruta en el documento de la voz."
)


def _options(**changes):
    options = {
        "runtime": {
            "python_path": PYTHON,
            "cache_dir": "test_runtime/cache",
            "cuda_cache_dir": "test_runtime/cache/cuda",
            "temp_dir": "test_tmp/tts",
            "device": "cuda",
        },
        "model": {
            "repo_id": "test_repo/test_model",
            "config_path": CONFIG_FILE,
            "weights_path": WEIGHTS_FILE,
        },
        "voice": {"path": VOICE_FILE, "lang_code": "e"},
        "segmentation": {"max_characters": 20},
        "synthesis": {"speed": 1.0},
    }
    options.update(changes)
    return options


def _project(tmp_path):
    for relative in (PYTHON, CONFIG_FILE, WEIGHTS_FILE, VOICE_FILE):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"test")
    return tmp_path


def _request(tmp_path, *, options=None, seed=None, text=TEXT, prosody=None, **voice):
    workspace = tmp_path / "workspace"
    workspace.mkdir(exist_ok=True)
    return TtsSynthesisRequest(
        text=text,
        voice=ResolvedTtsVoice(
            voice_id="test_voice",
            backend_key=voice.get("backend_key", "kokoro"),
            backend_voice_id=voice.get("backend_voice_id"),
            language="es-ES",
            prosody=prosody
            or TtsProsody(sentence_pause_seconds=0.5, paragraph_pause_seconds=0.25),
            backend_options=_options() if options is None else options,
            seed=seed,
        ),
        workspace=TtsSynthesisWorkspace(workspace_id="test_workspace", path=workspace),
    )


def _write_wav(path, frames, rate=RATE):
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(b"\x01\x00" * frames)


class FakeWorker:
    """Plays the worker: writes each segment WAV and the result document."""

    def __init__(self, *, result=None, exit_code=0, frames=(1200, 2400, 3600)):
        self.result = {"status": "ok", "sample_rate": RATE} if result is None else result
        self.exit_code = exit_code
        self.frames = frames
        self.calls = []

    def __call__(self, command, *, env, cwd, log_path, on_line):
        request = json.loads(Path(command[-1]).read_text(encoding="utf-8"))
        self.calls.append({"command": command, "env": env, "cwd": cwd, "request": request})
        log_path.write_text("", encoding="utf-8")
        if self.result.get("status") == "ok":
            for index, segment in enumerate(request["segments"]):
                _write_wav(Path(segment["output"]), self.frames[index])
                on_line(f"AIVC_PROGRESS {index + 1} {len(request['segments'])}")
        Path(request["result"]).write_text(json.dumps(self.result), encoding="utf-8")
        return self.exit_code


def _backend(root, worker, progress=None):
    return KokoroBackend(
        root,
        process=ExternalTtsProcess(
            launcher=worker,
            progress=progress or (lambda done, total: None),
            base_environment={"KEEP": "1"},
        ),
    )


# --- synthesis through the simulated process --------------------------------


def test_backend_joins_segment_wavs_with_declared_pauses(tmp_path):
    root = _project(tmp_path)
    progress = []

    result = _backend(root, FakeWorker(), lambda *step: progress.append(step)).synthesize(
        _request(root)
    )

    assert result.staged_audio.path == root / "workspace" / "kokoro_audio.wav"
    assert (result.staged_audio.container, result.staged_audio.codec) == ("wav", "pcm_s16le")
    assert (result.staged_audio.sample_rate_hz, result.staged_audio.channels) == (RATE, 1)
    assert result.word_timings is None
    pause_1 = round(0.5 * RATE)
    pause_2 = round(0.25 * RATE)
    with wave.open(str(result.staged_audio.path), "rb") as audio:
        assert audio.getnframes() == 1200 + pause_1 + 2400 + pause_2 + 3600
    assert [(pause.start_seconds, pause.end_seconds) for pause in result.pauses] == [
        (1200 / RATE, (1200 + pause_1) / RATE),
        ((1200 + pause_1 + 2400) / RATE, (1200 + pause_1 + 2400 + pause_2) / RATE),
    ]
    assert progress == [(1, 3), (2, 3), (3, 3)]


def test_zero_sentence_pause_joins_segments_without_silence(tmp_path):
    root = _project(tmp_path)
    prosody = TtsProsody(sentence_pause_seconds=0.0, paragraph_pause_seconds=0.25)

    result = _backend(root, FakeWorker()).synthesize(_request(root, prosody=prosody))

    pause = round(0.25 * RATE)
    with wave.open(str(result.staged_audio.path), "rb") as audio:
        assert audio.getnframes() == 1200 + 2400 + pause + 3600
    assert len(result.pauses) == 1


def test_worker_receives_the_declared_runtime_model_voice_and_speed(tmp_path):
    root = _project(tmp_path)
    worker = FakeWorker()

    _backend(root, worker).synthesize(_request(root))

    call = worker.calls[0]
    workspace = root / "workspace"
    worker_script = (REPOSITORY_ROOT / "app/modules/audio/workers/kokoro_worker.py").resolve()
    assert call["command"] == [
        os.path.abspath(root / PYTHON),
        "-I",
        "-X",
        "utf8",
        str(worker_script),
        str(workspace / "tts_request.json"),
    ]
    assert call["cwd"] == workspace
    request = call["request"]
    assert request["protocol"] == 1
    assert request["device"] == "cuda"
    assert request["repo_id"] == "test_repo/test_model"
    assert request["config_path"] == os.path.abspath(root / CONFIG_FILE)
    assert request["weights_path"] == os.path.abspath(root / WEIGHTS_FILE)
    assert request["voice_path"] == os.path.abspath(root / VOICE_FILE)
    assert request["lang_code"] == "e"
    assert request["speed"] == 1.0
    assert request["seed"] is None
    assert [segment["text"] for segment in request["segments"]] == [
        "Primera frase.",
        "Segunda frase.",
        "Tercera frase.",
    ]
    assert request["result"] == str(workspace / "tts_result.json")


def test_worker_environment_never_downloads_and_keeps_caches_in_the_project(tmp_path):
    root = _project(tmp_path)
    worker = FakeWorker()

    _backend(root, worker).synthesize(_request(root))

    env = worker.calls[0]["env"]
    cache = Path(os.path.abspath(root / "test_runtime/cache"))
    assert env["KEEP"] == "1"
    assert env["HF_HUB_OFFLINE"] == "1"
    assert env["HF_HOME"] == str(cache / "huggingface")
    assert env["TORCH_HOME"] == str(cache / "torch")
    assert env["CUDA_CACHE_PATH"] == str(cache / "cuda")
    temp = os.path.abspath(root / "test_tmp/tts")
    assert (env["TEMP"], env["TMP"], env["TMPDIR"]) == (temp, temp, temp)


@pytest.mark.parametrize("seed", (0, 1234))
def test_declared_seed_reaches_the_worker(tmp_path, seed):
    root = _project(tmp_path)
    worker = FakeWorker()

    _backend(root, worker).synthesize(_request(root, seed=seed))

    assert worker.calls[0]["request"]["seed"] == seed


def test_cpu_device_lang_code_and_speed_are_passed_as_declared(tmp_path):
    root = _project(tmp_path)
    worker = FakeWorker()
    options = _options(
        voice={"path": VOICE_FILE, "lang_code": "  es "},
        synthesis={"speed": 2},
    )
    options["runtime"]["device"] = "cpu"

    _backend(root, worker).synthesize(_request(root, options=options))

    request = worker.calls[0]["request"]
    assert request["device"] == "cpu"
    assert request["lang_code"] == "es"
    assert request["speed"] == 2.0
    assert isinstance(request["speed"], float)


def test_backend_rejects_a_request_of_another_backend(tmp_path):
    root = _project(tmp_path)
    worker = FakeWorker()

    with pytest.raises(TtsBackendError) as error:
        _backend(root, worker).synthesize(_request(root, backend_key="test_backend"))

    assert error.value.diagnostic.kind is TtsBackendErrorKind.CONFIGURATION
    assert error.value.diagnostic.detail == "La solicitud pertenece a otro backend TTS."
    assert worker.calls == []


def test_backend_rejects_a_request_that_is_not_a_synthesis_request(tmp_path):
    with pytest.raises(TtsBackendError) as error:
        _backend(_project(tmp_path), FakeWorker()).synthesize(object())

    assert error.value.diagnostic.kind is TtsBackendErrorKind.CONFIGURATION
    assert error.value.diagnostic.detail == "La solicitud técnica de Kokoro no es válida."


# --- CONFIG errors with the relative path -----------------------------------


def _config_error(tmp_path, request_changes=None, prepare=None):
    root = _project(tmp_path)
    if prepare is not None:
        prepare(root)
    worker = FakeWorker()
    with pytest.raises(TtsVoiceConfigurationError) as error:
        _backend(root, worker).synthesize(_request(root, **(request_changes or {})))
    assert worker.calls == []
    return str(error.value)


def test_missing_python_names_its_relative_path(tmp_path):
    message = _config_error(tmp_path, prepare=lambda root: (root / PYTHON).unlink())

    assert message == (
        f"no existe «{PYTHON}» (backend_options.runtime.python_path). {SETUP_HINT}"
    )


@pytest.mark.parametrize(
    ("relative", "label"),
    (
        (CONFIG_FILE, "backend_options.model.config_path"),
        (WEIGHTS_FILE, "backend_options.model.weights_path"),
        (VOICE_FILE, "backend_options.voice.path"),
    ),
)
def test_missing_model_or_voice_file_names_its_relative_path(tmp_path, relative, label):
    message = _config_error(tmp_path, prepare=lambda root: (root / relative).unlink())

    assert message == f"no existe «{relative}» ({label}). {SETUP_HINT}"


def test_a_folder_is_not_accepted_as_the_voice_file(tmp_path):
    def replace_with_folder(root):
        (root / VOICE_FILE).unlink()
        (root / VOICE_FILE).mkdir()

    message = _config_error(tmp_path, prepare=replace_with_folder)

    assert message == f"no existe «{VOICE_FILE}» (backend_options.voice.path). {SETUP_HINT}"


@pytest.mark.parametrize(
    "voice_path",
    ("../outside/voice.pt", str(Path(__file__).resolve())),
)
def test_voice_path_must_stay_inside_the_project(tmp_path, voice_path):
    message = _config_error(
        tmp_path,
        {"options": _options(voice={"path": voice_path, "lang_code": "e"})},
    )

    assert message.startswith(
        "backend_options.voice.path debe ser una ruta relativa dentro de la "
        "carpeta del proyecto"
    )


@pytest.mark.parametrize(
    ("block", "name", "label"),
    (
        ("model", "repo_id", "backend_options.model.repo_id"),
        ("voice", "lang_code", "backend_options.voice.lang_code"),
    ),
)
@pytest.mark.parametrize("value", ("", "   ", None, 3))
def test_repo_id_and_lang_code_must_be_text(tmp_path, block, name, label, value):
    options = _options()
    options[block][name] = value

    message = _config_error(tmp_path, {"options": options})

    assert message == f"{label} debe ser un texto no vacío; se recibió {value!r}."


@pytest.mark.parametrize(
    "value",
    (0, 0.0, -1, -0.5, True, "1", None),
)
def test_speed_must_be_a_number_above_zero(tmp_path, value):
    message = _config_error(
        tmp_path,
        {"options": _options(synthesis={"speed": value})},
    )

    assert message == (
        f"backend_options.synthesis.speed debe ser un número mayor que 0; se recibió {value!r}."
    )


@pytest.mark.parametrize(
    ("changes", "expected"),
    (
        ({"extra": {}}, "backend_options no admite las claves: extra."),
        (
            {"model": {"checkpoint_dir": "x"}},
            "backend_options.model no admite las claves: checkpoint_dir.",
        ),
        (
            {"voice": {"path": VOICE_FILE, "lang_code": "e", "name": "x"}},
            "backend_options.voice no admite las claves: name.",
        ),
        (
            {"synthesis": {"speed": 1.0, "exaggeration": 0.5}},
            "backend_options.synthesis no admite las claves: exaggeration.",
        ),
        ({"model": None}, "backend_options.model debe ser un objeto; se recibió None."),
        ({"voice": "x"}, "backend_options.voice debe ser un objeto; se recibió 'x'."),
        ({"synthesis": None}, "backend_options.synthesis debe ser un objeto; se recibió None."),
    ),
)
def test_unknown_or_malformed_option_blocks_are_rejected(tmp_path, changes, expected):
    message = _config_error(tmp_path, {"options": _options(**changes)})

    assert message.startswith(expected)


def test_missing_synthesis_block_is_a_config_error(tmp_path):
    options = _options()
    del options["synthesis"]

    message = _config_error(tmp_path, {"options": options})

    assert message == "backend_options.synthesis debe ser un objeto; se recibió None."


@pytest.mark.parametrize(
    "prosody",
    (
        TtsProsody(speaking_rate=1.2),
        TtsProsody(volume_gain_db=2.0),
    ),
)
def test_unsupported_prosody_is_a_config_error(tmp_path, prosody):
    message = _config_error(tmp_path, {"prosody": prosody})

    assert message == (
        "Kokoro no admite cambiar prosody.speaking_rate ni prosody.volume_gain_db: "
        "deja 1.0 y 0.0 (la velocidad se declara en backend_options.synthesis.speed)."
    )


def test_backend_voice_id_is_a_config_error(tmp_path):
    message = _config_error(tmp_path, {"backend_voice_id": "em_alex"})

    assert message == (
        "Kokoro lee la voz de backend_options.voice.path: quita backend_voice_id."
    )


def test_text_without_sentences_is_a_config_error(tmp_path):
    message = _config_error(tmp_path, {"text": "..."})

    assert message == "el texto no tiene ninguna frase que leer."


def test_voice_builder_reports_a_missing_voice_file_as_config(tmp_path):
    root = _project(tmp_path)
    (root / VOICE_FILE).unlink()
    document = json.loads((VOICE_CONFIGS / "kokoro_alex.json").read_text(encoding="utf-8"))
    document["backend_options"] = _options()
    configuration = load_tts_voice_configuration(document)
    worker = FakeWorker()

    class _Manager:
        def get_tts_voice_configuration(self):
            return configuration

    builder = VoiceBuilder(
        config_manager=_Manager(),
        backend_registry=TtsBackendRegistry((_backend(root, worker),)),
        workspace_parent=tmp_path / "workspaces",
    )
    with pytest.raises(OperationalError) as error:
        builder.build("Texto de prueba.", output_path=tmp_path / "voz.mp3")

    context = error.value.context
    assert context.family == "CONFIG"
    assert context.user_message == (
        "La configuración de la voz «Kokoro Alex (rápida, GPU)» no es válida: "
        f"no existe «{VOICE_FILE}» (backend_options.voice.path). {SETUP_HINT}"
    )
    assert worker.calls == []


# --- worker failures --------------------------------------------------------


def _worker_error(tmp_path, worker):
    root = _project(tmp_path)
    with pytest.raises((TtsBackendError, TtsVoiceConfigurationError)) as error:
        _backend(root, worker).synthesize(_request(root))
    return error.value


def test_worker_configuration_error_names_kokoro(tmp_path):
    error = _worker_error(
        tmp_path,
        FakeWorker(
            result={"status": "error", "kind": "configuration", "message": "falta x"},
            exit_code=1,
        ),
    )

    assert isinstance(error, TtsVoiceConfigurationError)
    assert str(error) == "Kokoro: falta x"


def test_worker_synthesis_error_names_kokoro(tmp_path):
    error = _worker_error(
        tmp_path,
        FakeWorker(
            result={"status": "error", "kind": "synthesis", "message": "parte larga"},
            exit_code=1,
        ),
    )

    assert error.diagnostic.kind is TtsBackendErrorKind.SYNTHESIS
    assert error.diagnostic.detail == "Kokoro falló: parte larga"


# --- the worker itself, with fake torch, kokoro and soundfile ---------------


class _FakeTensorAudio(list):
    """Audio a fake pipeline yields (any sequence of samples)."""


def _fake_modules(monkeypatch, *, cuda=True, results=None, events=None):
    """Install fake ``torch``, ``soundfile`` and ``kokoro`` modules."""
    events = [] if events is None else events
    written = []

    torch = types.ModuleType("torch")
    torch.cuda = types.SimpleNamespace(
        is_available=lambda: cuda,
        manual_seed_all=lambda value: events.append(("cuda", value)),
    )
    torch.manual_seed = lambda value: events.append(("torch", value))

    soundfile = types.ModuleType("soundfile")

    def write(path, audio, rate, subtype):
        written.append((path, list(audio), rate, subtype))

    soundfile.write = write

    class KModel:
        def __init__(self, *, repo_id, config, model):
            events.append(("model", repo_id, config, model))

        def to(self, device):
            events.append(("to", device))
            return self

        def eval(self):
            return self

    class KPipeline:
        def __init__(self, *, lang_code, repo_id, model):
            events.append(("pipeline", lang_code, repo_id, isinstance(model, KModel)))

        def __call__(self, text, *, voice, speed):
            events.append(("read", text, voice, speed))
            yield from (results or {}).get(
                text,
                [types.SimpleNamespace(phonemes="abc", audio=_FakeTensorAudio([0.5, -0.5]))],
            )

    kokoro = types.ModuleType("kokoro")
    kokoro.KModel = KModel
    kokoro.KPipeline = KPipeline
    pipeline = types.ModuleType("kokoro.pipeline")
    pipeline.ALIASES = {"es": "e"}
    pipeline.LANG_CODES = {"e": "es", "f": "fr-fr"}
    for name, module in (
        ("torch", torch),
        ("soundfile", soundfile),
        ("kokoro", kokoro),
        ("kokoro.pipeline", pipeline),
    ):
        monkeypatch.setitem(sys.modules, name, module)
    return events, written


def _worker_request(tmp_path, **changes):
    request = {
        "protocol": 1,
        "device": "cuda",
        "seed": None,
        "repo_id": "test_repo/test_model",
        "config_path": "config.json",
        "weights_path": "model.pth",
        "voice_path": "voice.pt",
        "lang_code": "es",
        "speed": 1.25,
        "segments": [
            {"text": "Primera.", "output": str(tmp_path / "segment_001.wav")},
            {"text": "Segunda.", "output": str(tmp_path / "segment_002.wav")},
        ],
        "result": str(tmp_path / "result.json"),
    }
    request.update(changes)
    return request


def test_worker_loads_the_declared_files_and_writes_one_wav_per_segment(
    tmp_path, monkeypatch, capsys
):
    np = pytest.importorskip("numpy")
    events, written = _fake_modules(
        monkeypatch,
        results={
            "Primera.": [
                types.SimpleNamespace(phonemes="a", audio=_FakeTensorAudio([0.25])),
                types.SimpleNamespace(phonemes="b", audio=None),
                types.SimpleNamespace(phonemes="c", audio=_FakeTensorAudio([0.5, 1.0])),
            ],
        },
    )

    sample_rate, timings = kokoro_worker.synthesize(_worker_request(tmp_path))

    assert sample_rate == 24_000
    assert set(timings) == {"load_seconds", "generation_seconds"}
    assert events == [
        ("model", "test_repo/test_model", "config.json", "model.pth"),
        ("to", "cuda"),
        ("pipeline", "e", "test_repo/test_model", True),
        ("read", "Primera.", "voice.pt", 1.25),
        ("read", "Segunda.", "voice.pt", 1.25),
    ]
    assert [(Path(path).name, rate, subtype) for path, _, rate, subtype in written] == [
        ("segment_001.wav", 24_000, "PCM_16"),
        ("segment_002.wav", 24_000, "PCM_16"),
    ]
    assert written[0][1] == [0.25, 0.5, 1.0]
    assert written[1][1] == [0.5, -0.5]
    assert all(
        isinstance(sample, np.float32) for _, audio, _, _ in written for sample in audio
    )
    assert capsys.readouterr().out.splitlines() == [
        "AIVC_PROGRESS 1 2",
        "AIVC_PROGRESS 2 2",
    ]


def test_worker_fixes_the_seed_before_loading_the_model(tmp_path, monkeypatch):
    pytest.importorskip("numpy")
    events, _ = _fake_modules(monkeypatch)

    kokoro_worker.synthesize(_worker_request(tmp_path, seed=1234))

    assert events[:3] == [("torch", 1234), ("cuda", 1234), ("model", "test_repo/test_model", "config.json", "model.pth")]


def test_worker_without_seed_does_not_touch_the_random_sources(tmp_path, monkeypatch):
    pytest.importorskip("numpy")
    events, _ = _fake_modules(monkeypatch)

    kokoro_worker.synthesize(_worker_request(tmp_path))

    assert not [event for event in events if event[0] in {"torch", "cuda"}]


def test_worker_without_cuda_stops_before_loading(tmp_path, monkeypatch):
    pytest.importorskip("numpy")
    events, written = _fake_modules(monkeypatch, cuda=False)

    with pytest.raises(kokoro_worker.WorkerError) as error:
        kokoro_worker.synthesize(_worker_request(tmp_path, seed=1))

    assert error.value.kind == "resource_unavailable"
    assert error.value.message == "la GPU (CUDA) no está disponible en el entorno de la voz."
    assert events == []
    assert written == []


def test_worker_runs_on_cpu_without_cuda(tmp_path, monkeypatch):
    pytest.importorskip("numpy")
    events, written = _fake_modules(monkeypatch, cuda=False)

    kokoro_worker.synthesize(_worker_request(tmp_path, device="cpu"))

    assert ("to", "cpu") in events
    assert len(written) == 2


def test_worker_rejects_an_unknown_lang_code_before_loading(tmp_path, monkeypatch):
    pytest.importorskip("numpy")
    events, _ = _fake_modules(monkeypatch)

    with pytest.raises(kokoro_worker.WorkerError) as error:
        kokoro_worker.synthesize(_worker_request(tmp_path, lang_code="xx"))

    assert error.value.kind == "configuration"
    assert error.value.message == (
        "backend_options.voice.lang_code 'xx' no es un idioma de Kokoro. "
        "Valores válidos: e, f."
    )
    assert events == []


def test_worker_stops_on_a_part_that_kokoro_would_cut(tmp_path, monkeypatch):
    pytest.importorskip("numpy")
    _, written = _fake_modules(
        monkeypatch,
        results={
            "Segunda.": [
                types.SimpleNamespace(phonemes="x" * 510, audio=_FakeTensorAudio([0.1])),
            ],
        },
    )

    with pytest.raises(kokoro_worker.WorkerError) as error:
        kokoro_worker.synthesize(_worker_request(tmp_path))

    assert error.value.kind == "synthesis"
    assert error.value.message == (
        "la parte 2 del texto es demasiado larga para Kokoro (más de 509 fonemas) "
        "y se cortaría. Baja backend_options.segmentation.max_characters o parte "
        "esa frase."
    )
    assert len(written) == 1


def test_worker_reports_a_part_without_audio(tmp_path, monkeypatch):
    pytest.importorskip("numpy")
    _fake_modules(
        monkeypatch,
        results={"Primera.": [types.SimpleNamespace(phonemes="", audio=None)]},
    )

    with pytest.raises(kokoro_worker.WorkerError) as error:
        kokoro_worker.synthesize(_worker_request(tmp_path))

    assert error.value.kind == "synthesis"
    assert error.value.message == "Kokoro no generó audio para la parte 1 del texto."


@pytest.mark.parametrize(
    ("value", "expected"),
    (("e", "e"), ("E", "e"), (" es ", "e"), ("f", "f")),
)
def test_lang_code_accepts_kokoro_codes_and_aliases(value, expected):
    assert kokoro_worker.resolve_lang_code(value, {"es": "e"}, {"e": "es", "f": "fr"}) == expected


@pytest.mark.parametrize("length", (0, 1, 509))
def test_parts_under_the_phoneme_limit_pass(length):
    kokoro_worker.check_phonemes("x" * length, 1)


def test_part_without_phonemes_passes():
    kokoro_worker.check_phonemes(None, 1)


def test_worker_fixes_every_random_source():
    events = []

    class _Random:
        @staticmethod
        def seed(value):
            events.append(("numpy", value))

    class _Cuda:
        @staticmethod
        def is_available():
            return True

        @staticmethod
        def manual_seed_all(value):
            events.append(("cuda", value))

    class _Torch:
        cuda = _Cuda

        @staticmethod
        def manual_seed(value):
            events.append(("torch", value))

    class _Numpy:
        random = _Random

    kokoro_worker.fix_seed(1234, _Numpy, _Torch)

    assert events == [("numpy", 1234), ("torch", 1234), ("cuda", 1234)]
    assert kokoro_worker.random.random() == pytest.approx(
        __import__("random").Random(1234).random()
    )


def _write_request(tmp_path, **changes):
    path = tmp_path / "request.json"
    path.write_text(json.dumps(_worker_request(tmp_path, **changes)), encoding="utf-8")
    return path


def _result(tmp_path):
    return json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))


def test_worker_rejects_another_protocol_as_configuration(tmp_path):
    path = _write_request(tmp_path, protocol=2)

    assert kokoro_worker.main(["kokoro_worker.py", str(path)]) == 1
    assert _result(tmp_path) == {
        "status": "error",
        "kind": "configuration",
        "message": "el script de la voz espera el protocolo 1 y recibió 2.",
    }


def test_worker_turns_an_unexpected_failure_into_a_synthesis_result(tmp_path, monkeypatch):
    path = _write_request(tmp_path)

    def fail(request):
        raise RuntimeError("CUDA out of memory")

    monkeypatch.setattr(kokoro_worker, "synthesize", fail)

    assert kokoro_worker.main(["kokoro_worker.py", str(path)]) == 1
    assert _result(tmp_path) == {
        "status": "error",
        "kind": "synthesis",
        "message": "RuntimeError: CUDA out of memory",
    }


def test_worker_keeps_the_kind_of_its_own_errors(tmp_path, monkeypatch):
    path = _write_request(tmp_path)

    def fail(request):
        raise kokoro_worker.WorkerError("configuration", "idioma no válido")

    monkeypatch.setattr(kokoro_worker, "synthesize", fail)

    assert kokoro_worker.main(["kokoro_worker.py", str(path)]) == 1
    assert _result(tmp_path) == {
        "status": "error",
        "kind": "configuration",
        "message": "idioma no válido",
    }


def test_worker_writes_the_ok_result_with_its_timings(tmp_path, monkeypatch):
    path = _write_request(tmp_path)
    monkeypatch.setattr(
        kokoro_worker,
        "synthesize",
        lambda request: (24_000, {"load_seconds": 1.0, "generation_seconds": 2.0}),
    )

    assert kokoro_worker.main(["kokoro_worker.py", str(path)]) == 0
    assert _result(tmp_path) == {
        "status": "ok",
        "sample_rate": 24_000,
        "load_seconds": 1.0,
        "generation_seconds": 2.0,
    }


def test_worker_needs_exactly_one_request_argument(capsys):
    assert kokoro_worker.main(["kokoro_worker.py"]) == 2
    assert "Uso: kokoro_worker.py <request.json>" in capsys.readouterr().err


def test_worker_imports_only_the_standard_library_at_module_level():
    source = Path(kokoro_worker.__file__).read_text(encoding="utf-8")
    top_level_imports = [
        line
        for line in source.splitlines()
        if line.startswith(("import ", "from "))
    ]

    assert top_level_imports == [
        "import json",
        "from pathlib import Path",
        "import random",
        "import sys",
        "import time",
        "import traceback",
    ]


# --- product composition and voice documents --------------------------------


def test_default_registry_resolves_kokoro_without_loading_anything(tmp_path):
    registry = build_default_tts_backend_registry(project_root=tmp_path)

    backend = registry.resolve("kokoro")
    assert isinstance(backend, KokoroBackend)
    assert backend._project_root == tmp_path.resolve()


@pytest.mark.parametrize(
    ("stem", "voice_file", "display_name", "pacing"),
    (
        ("kokoro_alex", "em_alex.pt", "Kokoro Alex (rápida, GPU)", (14.42, 2.87)),
        ("kokoro_dora", "ef_dora.pt", "Kokoro Dora (rápida, GPU)", (14.40, 2.86)),
    ),
)
def test_project_voice_documents_declare_everything_inside_the_project(
    stem, voice_file, display_name, pacing
):
    document = json.loads((VOICE_CONFIGS / f"{stem}.json").read_text(encoding="utf-8"))
    configuration = load_tts_voice_configuration(document)

    voice = configuration.voice
    assert configuration.display_name == display_name
    assert voice.backend_key == "kokoro"
    assert voice.backend_voice_id is None
    assert voice.seed is None
    assert (voice.prosody.speaking_rate, voice.prosody.volume_gain_db) == (1.0, 0.0)
    assert (voice.prosody.sentence_pause_seconds, voice.prosody.paragraph_pause_seconds) == (0.0, 0.35)
    assert (
        configuration.pacing.letters_per_second,
        configuration.pacing.words_per_second,
    ) == pacing
    options = voice.backend_options
    assert dict(options["runtime"]) == {
        "python_path": "models/tts/kokoro/env/Scripts/python.exe",
        "cache_dir": "models/tts/_cache",
        "cuda_cache_dir": "models/tts/_cache/cuda",
        "temp_dir": "tmp/tts",
        "device": "cuda",
    }
    assert dict(options["model"]) == {
        "repo_id": "hexgrad/Kokoro-82M",
        "config_path": "models/tts/kokoro/weights/config.json",
        "weights_path": "models/tts/kokoro/weights/kokoro-v1_0.pth",
    }
    assert dict(options["voice"]) == {
        "path": f"models/tts/kokoro/weights/voices/{voice_file}",
        "lang_code": "e",
    }
    assert dict(options["segmentation"]) == {"max_characters": 400}
    assert dict(options["synthesis"]) == {"speed": 1.0}


def test_backend_requires_an_explicit_project_root():
    with pytest.raises(TypeError):
        KokoroBackend("  ")
    with pytest.raises(TypeError):
        KokoroBackend(object())
