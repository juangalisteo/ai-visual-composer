"""Chatterbox Multilingual backend in its own process (I6b).

The worker process is simulated: these tests never load torch or the model.
They cover the declared runtime and its CONFIG errors with relative paths,
the request sent to the worker (seed included), joining the segment WAVs with
the declared pauses, the worker's error results, the real process launcher
with a minimal script, and the worker's pure parts.
"""

import json
import os
from pathlib import Path
import sys
import wave

import pytest

from app.modules.audio import external_tts_process
from app.modules.audio.chatterbox_backend import ChatterboxBackend
from app.modules.audio.external_tts_process import (
    ExternalTtsProcess,
    SpeechSegment,
    launch_worker_process,
    split_speech_segments,
)
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
from app.modules.audio.workers import chatterbox_worker
from app.shared.operational_error import OperationalError


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VOICE_DOCUMENT = REPOSITORY_ROOT / "config/voice_configs/chatterbox_multilingual.json"
PYTHON = "test_runtime/env/python.exe"
CHECKPOINT = "test_runtime/weights"
CHECKPOINT_FILES = (
    "ve.pt",
    "t3_mtl23ls_v2.safetensors",
    "s3gen.pt",
    "grapheme_mtl_merged_expanded_v1.json",
    "conds.pt",
)
RATE = 24_000
TEXT = "Primera frase. Segunda frase.\n\nTercera frase."


def _options(**changes):
    options = {
        "runtime": {
            "python_path": PYTHON,
            "cache_dir": "test_runtime/cache",
            "device": "cuda",
        },
        "model": {"checkpoint_dir": CHECKPOINT},
        "segmentation": {"max_characters": 20},
        "synthesis": {"exaggeration": 0.5, "cfg_weight": 0.5},
    }
    options.update(changes)
    return options


def _project(tmp_path):
    python = tmp_path / PYTHON
    python.parent.mkdir(parents=True)
    python.write_bytes(b"python")
    weights = tmp_path / CHECKPOINT
    weights.mkdir(parents=True)
    for name in CHECKPOINT_FILES:
        (weights / name).write_bytes(b"weights")
    return tmp_path


def _request(tmp_path, *, options=None, seed=None, text=TEXT, prosody=None, **voice):
    workspace = tmp_path / "workspace"
    workspace.mkdir(exist_ok=True)
    return TtsSynthesisRequest(
        text=text,
        voice=ResolvedTtsVoice(
            voice_id="test_voice",
            backend_key=voice.get("backend_key", "chatterbox_multilingual"),
            backend_voice_id=voice.get("backend_voice_id"),
            language=voice.get("language", "es-ES"),
            prosody=prosody
            or TtsProsody(sentence_pause_seconds=0.5, paragraph_pause_seconds=0.25),
            backend_options=_options() if options is None else options,
            seed=seed,
        ),
        workspace=TtsSynthesisWorkspace(workspace_id="test_workspace", path=workspace),
    )


def _write_wav(path, frames, rate=RATE, channels=1, width=2):
    with wave.open(str(path), "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(width)
        output.setframerate(rate)
        output.writeframes(b"\x01\x00" * frames * channels * (width // 2))


class FakeWorker:
    """Plays the worker: writes each segment WAV and the result document."""

    def __init__(self, *, result=None, exit_code=0, frames=(1200, 2400, 3600), log=""):
        self.result = {"status": "ok", "sample_rate": RATE} if result is None else result
        self.exit_code = exit_code
        self.frames = frames
        self.log = log
        self.calls = []

    def __call__(self, command, *, env, cwd, log_path, on_line):
        request = json.loads(Path(command[-1]).read_text(encoding="utf-8"))
        self.calls.append({"command": command, "env": env, "cwd": cwd, "request": request})
        log_path.write_text(self.log, encoding="utf-8")
        if self.result.get("status") == "ok":
            for index, segment in enumerate(request["segments"]):
                _write_wav(Path(segment["output"]), self.frames[index])
                on_line(f"AIVC_PROGRESS {index + 1} {len(request['segments'])}")
        if self.result != {}:
            Path(request["result"]).write_text(json.dumps(self.result), encoding="utf-8")
        return self.exit_code


def _backend(root, worker, progress=None):
    return ChatterboxBackend(
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
    worker = FakeWorker()
    progress = []

    result = _backend(root, worker, lambda *step: progress.append(step)).synthesize(
        _request(root)
    )

    assert result.staged_audio.path == root / "workspace" / "chatterbox_audio.wav"
    assert (result.staged_audio.container, result.staged_audio.codec) == ("wav", "pcm_s16le")
    assert (result.staged_audio.sample_rate_hz, result.staged_audio.channels) == (RATE, 1)
    assert result.word_timings is None
    pause_1 = round(0.5 * RATE)
    pause_2 = round(0.25 * RATE)
    with wave.open(str(result.staged_audio.path), "rb") as audio:
        assert audio.getnframes() == 1200 + pause_1 + 2400 + pause_2 + 3600
        assert (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) == (1, 2, RATE)
    assert [(pause.start_seconds, pause.end_seconds) for pause in result.pauses] == [
        (1200 / RATE, (1200 + pause_1) / RATE),
        ((1200 + pause_1 + 2400) / RATE, (1200 + pause_1 + 2400 + pause_2) / RATE),
    ]
    assert progress == [(1, 3), (2, 3), (3, 3)]


def test_worker_receives_the_declared_runtime_model_and_options(tmp_path):
    root = _project(tmp_path)
    worker = FakeWorker()

    _backend(root, worker).synthesize(_request(root))

    call = worker.calls[0]
    workspace = root / "workspace"
    worker_script = (
        REPOSITORY_ROOT / "app/modules/audio/workers/chatterbox_worker.py"
    ).resolve()
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
    assert request["checkpoint_dir"] == os.path.abspath(root / CHECKPOINT)
    assert request["language_id"] == "es"
    assert request["synthesis"] == {"exaggeration": 0.5, "cfg_weight": 0.5}
    assert request["seed"] is None
    assert [segment["text"] for segment in request["segments"]] == [
        "Primera frase.",
        "Segunda frase.",
        "Tercera frase.",
    ]
    assert [Path(segment["output"]).name for segment in request["segments"]] == [
        "segment_001.wav",
        "segment_002.wav",
        "segment_003.wav",
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
    assert env["TRANSFORMERS_OFFLINE"] == "1"
    assert env["HF_HUB_DISABLE_TELEMETRY"] == "1"
    assert env["HF_HOME"] == str(cache / "huggingface")
    assert env["TORCH_HOME"] == str(cache / "torch")
    assert env["XDG_CACHE_HOME"] == str(cache / "xdg")


@pytest.mark.parametrize("seed", (0, 1234))
def test_declared_seed_reaches_the_worker(tmp_path, seed):
    root = _project(tmp_path)
    worker = FakeWorker()

    _backend(root, worker).synthesize(_request(root, seed=seed))

    assert worker.calls[0]["request"]["seed"] == seed


def test_worker_fixes_every_random_source_before_loading():
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

    chatterbox_worker.fix_seed(1234, _Numpy, _Torch)

    assert events == [("numpy", 1234), ("torch", 1234), ("cuda", 1234)]
    assert chatterbox_worker.random.random() == pytest.approx(
        __import__("random").Random(1234).random()
    )


def test_cpu_device_and_optional_synthesis_are_passed_as_declared(tmp_path):
    root = _project(tmp_path)
    worker = FakeWorker()
    options = _options()
    options["runtime"]["device"] = "cpu"
    del options["synthesis"]

    _backend(root, worker).synthesize(_request(root, options=options, language="es"))

    request = worker.calls[0]["request"]
    assert request["device"] == "cpu"
    assert request["synthesis"] == {}
    assert request["language_id"] == "es"


def test_backend_rejects_a_request_of_another_backend(tmp_path):
    root = _project(tmp_path)
    worker = FakeWorker()

    with pytest.raises(TtsBackendError) as error:
        _backend(root, worker).synthesize(_request(root, backend_key="test_backend"))

    assert error.value.diagnostic.kind is TtsBackendErrorKind.CONFIGURATION
    assert worker.calls == []


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
        f"no existe «{PYTHON}» (backend_options.runtime.python_path). "
        "Monta el entorno de la voz (docs/INSTALL.md, apartado 10) o corrige la "
        "ruta en el documento de la voz."
    )


def test_missing_checkpoint_folder_names_its_relative_path(tmp_path):
    def remove(root):
        for name in CHECKPOINT_FILES:
            (root / CHECKPOINT / name).unlink()
        (root / CHECKPOINT).rmdir()

    message = _config_error(tmp_path, prepare=remove)

    assert message.startswith(
        f"no existe «{CHECKPOINT}» (backend_options.model.checkpoint_dir)."
    )


@pytest.mark.parametrize("name", CHECKPOINT_FILES)
def test_missing_checkpoint_file_names_its_relative_path(tmp_path, name):
    message = _config_error(
        tmp_path,
        prepare=lambda root: (root / CHECKPOINT / name).unlink(),
    )

    assert message.startswith(
        f"no existe «{CHECKPOINT}/{name}» (backend_options.model.checkpoint_dir)."
    )


@pytest.mark.parametrize(
    "python_path",
    ("../outside/python.exe", str(Path(__file__).resolve())),
)
def test_runtime_paths_must_stay_inside_the_project(tmp_path, python_path):
    options = _options()
    options["runtime"]["python_path"] = python_path

    message = _config_error(tmp_path, {"options": options})

    assert message.startswith(
        "backend_options.runtime.python_path debe ser una ruta relativa dentro "
        "de la carpeta del proyecto"
    )


def _link_folder(link, target):
    """Directory link like a junction on Windows or a symlink elsewhere."""
    try:
        if os.name == "nt":
            import _winapi

            _winapi.CreateJunction(str(target), str(link))
        else:
            os.symlink(target, link, target_is_directory=True)
    except (ImportError, OSError, AttributeError) as error:
        pytest.skip(f"No se puede crear un enlace de carpeta: {error}")


def test_paths_through_a_linked_folder_inside_the_project_are_accepted(tmp_path):
    outside = tmp_path / "outside"
    project = tmp_path / "project"
    _project(outside)
    project.mkdir()
    _link_folder(project / "test_runtime", outside / "test_runtime")
    worker = FakeWorker()
    try:
        _backend(project, worker).synthesize(_request(project))
    finally:
        # Removes only the link, never the folder it points to.
        if os.name == "nt":
            os.rmdir(project / "test_runtime")
        else:
            os.unlink(project / "test_runtime")

    call = worker.calls[0]
    assert call["command"][0] == os.path.abspath(project / PYTHON)
    assert call["request"]["checkpoint_dir"] == os.path.abspath(project / CHECKPOINT)


@pytest.mark.parametrize("python_path", ("", "   ", None, 3))
def test_runtime_path_must_be_text(tmp_path, python_path):
    options = _options()
    options["runtime"]["python_path"] = python_path

    message = _config_error(tmp_path, {"options": options})

    assert message == (
        "backend_options.runtime.python_path debe ser una ruta relativa a la "
        f"carpeta del proyecto; se recibió {python_path!r}."
    )


@pytest.mark.parametrize("device", ("gpu", "CUDA", None))
def test_device_must_be_cuda_or_cpu(tmp_path, device):
    options = _options()
    options["runtime"]["device"] = device

    message = _config_error(tmp_path, {"options": options})

    assert message == (
        "backend_options.runtime.device debe ser «cuda» o «cpu»; se recibió "
        f"{device!r}."
    )


@pytest.mark.parametrize(
    ("changes", "expected"),
    (
        ({"extra": {}}, "backend_options no admite las claves: extra."),
        ({"runtime": None}, "backend_options.runtime debe ser un objeto"),
        ({"model": []}, "backend_options.model debe ser un objeto"),
        ({"segmentation": None}, "backend_options.segmentation debe ser un objeto"),
        ({"synthesis": []}, "backend_options.synthesis debe ser un objeto"),
        (
            {"model": {"checkpoint_dir": CHECKPOINT, "language_id": "es"}},
            "backend_options.model no admite las claves: language_id.",
        ),
        (
            {"synthesis": {"speed": 1.0}},
            "backend_options.synthesis no admite las claves: speed.",
        ),
        (
            {"segmentation": {"max_characters": 300, "overlap": 1}},
            "backend_options.segmentation no admite las claves: overlap.",
        ),
    ),
)
def test_unknown_or_malformed_option_blocks_are_rejected(tmp_path, changes, expected):
    message = _config_error(tmp_path, {"options": _options(**changes)})

    assert message.startswith(expected)


def test_unknown_runtime_key_is_rejected(tmp_path):
    options = _options()
    options["runtime"]["timeout"] = 30

    message = _config_error(tmp_path, {"options": options})

    assert message.startswith("backend_options.runtime no admite las claves: timeout.")


@pytest.mark.parametrize("value", (-0.1, "0.5", True, None))
def test_synthesis_values_must_be_non_negative_numbers(tmp_path, value):
    message = _config_error(
        tmp_path,
        {"options": _options(synthesis={"cfg_weight": value})},
    )

    assert message == (
        "backend_options.synthesis.cfg_weight debe ser un número mayor o igual "
        f"que 0; se recibió {value!r}."
    )


@pytest.mark.parametrize("value", (0, -5, 1.5, True, "300", None))
def test_max_characters_must_be_a_whole_number_above_zero(tmp_path, value):
    message = _config_error(
        tmp_path,
        {"options": _options(segmentation={"max_characters": value})},
    )

    assert message == (
        "backend_options.segmentation.max_characters debe ser un número entero "
        f"mayor que 0; se recibió {value!r}."
    )


@pytest.mark.parametrize(
    "prosody",
    (TtsProsody(speaking_rate=1.2), TtsProsody(volume_gain_db=3.0)),
)
def test_unsupported_prosody_is_a_config_error(tmp_path, prosody):
    message = _config_error(tmp_path, {"prosody": prosody})

    assert message == (
        "Chatterbox no admite cambiar prosody.speaking_rate ni "
        "prosody.volume_gain_db: deja 1.0 y 0.0."
    )


def test_backend_voice_id_is_a_config_error(tmp_path):
    message = _config_error(tmp_path, {"backend_voice_id": "test_voice"})

    assert message == "Chatterbox usa su voz de serie: quita backend_voice_id."


def test_language_must_be_a_language_tag(tmp_path):
    message = _config_error(tmp_path, {"language": "1-ES"})

    assert message == (
        "language debe ser una etiqueta de idioma como «es-ES»; se recibió '1-ES'."
    )


def test_text_without_sentences_is_a_config_error(tmp_path):
    message = _config_error(tmp_path, {"text": "..."})

    assert message == "el texto no tiene ninguna frase que leer."


def test_voice_builder_reports_a_missing_environment_as_config(tmp_path):
    root = _project(tmp_path)
    (root / PYTHON).unlink()
    document = json.loads(VOICE_DOCUMENT.read_text(encoding="utf-8"))
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
        "La configuración de la voz no es válida: no existe "
        f"«{PYTHON}» (backend_options.runtime.python_path). Monta el entorno de "
        "la voz (docs/INSTALL.md, apartado 10) o corrige la ruta en el "
        "documento de la voz."
    )
    assert worker.calls == []


# --- worker failures --------------------------------------------------------


def _worker_error(tmp_path, worker):
    root = _project(tmp_path)
    with pytest.raises((TtsBackendError, TtsVoiceConfigurationError)) as error:
        _backend(root, worker).synthesize(_request(root))
    return error.value


def test_worker_configuration_error_becomes_a_config_error(tmp_path):
    error = _worker_error(
        tmp_path,
        FakeWorker(
            result={"status": "error", "kind": "configuration", "message": "falta x"},
            exit_code=1,
        ),
    )

    assert isinstance(error, TtsVoiceConfigurationError)
    assert str(error) == "Chatterbox: falta x"


@pytest.mark.parametrize(
    ("kind", "expected"),
    (
        ("resource_unavailable", TtsBackendErrorKind.RESOURCE_UNAVAILABLE),
        ("synthesis", TtsBackendErrorKind.SYNTHESIS),
        ("other", TtsBackendErrorKind.SYNTHESIS),
    ),
)
def test_worker_error_result_keeps_its_kind_and_message(tmp_path, kind, expected):
    error = _worker_error(
        tmp_path,
        FakeWorker(
            result={
                "status": "error",
                "kind": kind,
                "message": "OutOfMemoryError: CUDA out of memory.",
            },
            exit_code=1,
        ),
    )

    assert isinstance(error, TtsBackendError)
    assert error.diagnostic.kind is expected
    assert error.diagnostic.detail == (
        "Chatterbox falló: OutOfMemoryError: CUDA out of memory."
    )


def test_worker_without_result_reports_its_exit_code_and_last_log_line(tmp_path):
    error = _worker_error(
        tmp_path,
        FakeWorker(result={}, exit_code=3, log="Traceback\n  línea\nMemoryError: sin memoria\n\n"),
    )

    assert error.diagnostic.kind is TtsBackendErrorKind.SYNTHESIS
    assert error.diagnostic.detail == (
        "el proceso de Chatterbox terminó (código 3) sin dejar su resultado. "
        "Última línea de su registro: «MemoryError: sin memoria»."
    )


def test_process_that_cannot_start_is_a_resource_error(tmp_path):
    def cannot_start(command, **kwargs):
        raise PermissionError("acceso denegado")

    error = _worker_error(tmp_path, cannot_start)

    assert error.diagnostic.kind is TtsBackendErrorKind.RESOURCE_UNAVAILABLE
    assert error.diagnostic.detail == (
        "no se pudo lanzar el proceso de Chatterbox: acceso denegado"
    )


@pytest.mark.parametrize(
    ("result", "exit_code"),
    (
        ({"status": "ok", "sample_rate": RATE}, 1),
        ({"status": "ok", "sample_rate": 0}, 0),
        ({"status": "ok", "sample_rate": True}, 0),
        ({"status": "ok", "sample_rate": "24000"}, 0),
        ({"status": "done", "sample_rate": RATE}, 0),
    ),
)
def test_inconsistent_ok_result_is_a_synthesis_error(tmp_path, result, exit_code):
    error = _worker_error(tmp_path, FakeWorker(result=result, exit_code=exit_code))

    assert error.diagnostic.kind is TtsBackendErrorKind.SYNTHESIS
    assert error.diagnostic.detail == (
        f"el proceso de Chatterbox terminó (código {exit_code}) con un "
        "resultado no válido."
    )


def test_segment_wav_with_another_format_is_invalid_audio(tmp_path):
    class _WrongRate(FakeWorker):
        def __call__(self, command, **kwargs):
            exit_code = super().__call__(command, **kwargs)
            request = json.loads(Path(command[-1]).read_text(encoding="utf-8"))
            _write_wav(Path(request["segments"][1]["output"]), 100, rate=16_000)
            return exit_code

    error = _worker_error(tmp_path, _WrongRate())

    assert error.diagnostic.kind is TtsBackendErrorKind.AUDIO_INVALID
    assert error.diagnostic.detail == (
        "El audio de una frase no es un WAV mono de 16 bits a 24000 Hz: "
        "segment_002.wav."
    )


def test_missing_segment_wav_is_invalid_audio(tmp_path):
    class _Missing(FakeWorker):
        def __call__(self, command, **kwargs):
            exit_code = super().__call__(command, **kwargs)
            request = json.loads(Path(command[-1]).read_text(encoding="utf-8"))
            Path(request["segments"][2]["output"]).unlink()
            return exit_code

    error = _worker_error(tmp_path, _Missing())

    assert error.diagnostic.kind is TtsBackendErrorKind.AUDIO_INVALID
    assert error.diagnostic.detail == "Falta el audio de una frase: segment_003.wav."


def test_join_rejects_a_mismatched_segment_count(tmp_path):
    with pytest.raises(TtsBackendError) as error:
        external_tts_process.join_segment_wavs(
            segment_paths=(tmp_path / "a.wav",),
            segments=(),
            output_path=tmp_path / "out.wav",
            workspace=tmp_path,
            sample_rate_hz=RATE,
        )

    assert error.value.diagnostic.kind is TtsBackendErrorKind.AUDIO_INVALID


def test_join_rejects_a_segment_outside_the_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.wav"
    _write_wav(outside, 10)

    with pytest.raises(TtsBackendError) as error:
        external_tts_process.join_segment_wavs(
            segment_paths=(outside,),
            segments=(SpeechSegment("Uno.", 0.0),),
            output_path=workspace / "out.wav",
            workspace=workspace,
            sample_rate_hz=RATE,
        )

    assert error.value.diagnostic.detail == "Falta el audio de una frase: outside.wav."


# --- text segments ----------------------------------------------------------


def test_sentences_share_a_segment_up_to_the_character_limit():
    segments = split_speech_segments(
        "Uno dos. Tres cuatro. Cinco seis siete ocho nueve.",
        sentence_pause_seconds=0.2,
        paragraph_pause_seconds=0.4,
        max_characters=20,
    )

    assert segments == (
        SpeechSegment("Uno dos.", 0.2),
        SpeechSegment("Tres cuatro.", 0.2),
        SpeechSegment("Cinco seis siete ocho nueve.", 0.0),
    )
    assert split_speech_segments(
        "Uno dos. Tres. Cuatro cinco seis siete.",
        sentence_pause_seconds=0.2,
        paragraph_pause_seconds=0.4,
        max_characters=20,
    ) == (
        SpeechSegment("Uno dos. Tres.", 0.2),
        SpeechSegment("Cuatro cinco seis siete.", 0.0),
    )


def test_limit_counts_the_joined_text_exactly():
    text = "Uno dos. Tres cuatro."

    assert split_speech_segments(
        text,
        sentence_pause_seconds=0.2,
        paragraph_pause_seconds=0.4,
        max_characters=len(text),
    ) == (SpeechSegment(text, 0.0),)
    assert split_speech_segments(
        text,
        sentence_pause_seconds=0.2,
        paragraph_pause_seconds=0.4,
        max_characters=len(text) - 1,
    ) == (SpeechSegment("Uno dos.", 0.2), SpeechSegment("Tres cuatro.", 0.0))


def test_paragraphs_never_share_a_segment_and_use_the_paragraph_pause():
    segments = split_speech_segments(
        "Uno. Dos.\n  \n\nTres. Cuatro.\r\n\r\nCinco.",
        sentence_pause_seconds=0.2,
        paragraph_pause_seconds=0.4,
        max_characters=300,
    )

    assert segments == (
        SpeechSegment("Uno. Dos.", 0.4),
        SpeechSegment("Tres. Cuatro.", 0.4),
        SpeechSegment("Cinco.", 0.0),
    )


def test_sentence_ends_with_marks_quotes_and_ellipsis_are_cut():
    segments = split_speech_segments(
        "¿Quién lo vio? «Nadie.» ¡Ya! Pensó… y siguió... Fin",
        sentence_pause_seconds=0.1,
        paragraph_pause_seconds=0.3,
        max_characters=1,
    )

    assert [segment.text for segment in segments] == [
        "¿Quién lo vio?",
        "«Nadie.»",
        "¡Ya!",
        "Pensó…",
        "y siguió...",
        "Fin",
    ]
    assert [segment.pause_after_seconds for segment in segments] == [0.1] * 5 + [0.0]


def test_long_sentence_goes_alone_and_line_breaks_become_spaces():
    segments = split_speech_segments(
        "Una frase\nmuy larga que no cabe. Otra.",
        sentence_pause_seconds=0.2,
        paragraph_pause_seconds=0.4,
        max_characters=10,
    )

    assert segments == (
        SpeechSegment("Una frase muy larga que no cabe.", 0.2),
        SpeechSegment("Otra.", 0.0),
    )


def test_pieces_without_letters_join_the_previous_segment():
    segments = split_speech_segments(
        "Hola. !!! Adiós.\n\n... \n\n-- . Fin.",
        sentence_pause_seconds=0.2,
        paragraph_pause_seconds=0.4,
        max_characters=1,
    )

    assert segments == (
        SpeechSegment("Hola. !!!", 0.2),
        SpeechSegment("Adiós. ... -- .", 0.4),
        SpeechSegment("Fin.", 0.0),
    )


def test_text_without_letters_has_no_segments():
    assert split_speech_segments(
        "... !!",
        sentence_pause_seconds=0.2,
        paragraph_pause_seconds=0.4,
        max_characters=300,
    ) == ()


# --- the real process launcher, with a minimal script ------------------------


def test_launcher_streams_stdout_lines_and_logs_stderr(tmp_path):
    script = tmp_path / "test_worker.py"
    script.write_text(
        "import sys\n"
        "print('AIVC_PROGRESS 1 2', flush=True)\n"
        "print('otra línea', flush=True)\n"
        "print('fallo ñ', file=sys.stderr)\n"
        "sys.exit(7)\n",
        encoding="utf-8",
    )
    lines = []

    exit_code = launch_worker_process(
        [sys.executable, "-I", "-X", "utf8", str(script)],
        env=dict(__import__("os").environ),
        cwd=tmp_path,
        log_path=tmp_path / "worker.log",
        on_line=lines.append,
    )

    assert exit_code == 7
    assert lines == ["AIVC_PROGRESS 1 2", "otra línea"]
    log = (tmp_path / "worker.log").read_text(encoding="utf-8")
    assert "fallo ñ" in log
    assert "otra línea" in log


def test_process_reports_only_well_formed_progress_lines(tmp_path):
    progress = []
    process = ExternalTtsProcess(launcher=None, progress=lambda *step: progress.append(step))
    handle = process._line_handler(4)

    for line in ("AIVC_PROGRESS 2 4", "AIVC_PROGRESS x 4", "AIVC_PROGRESS 3", "PROGRESS 1 4", "texto"):
        handle(line)

    assert progress == [(2, 4)]


def test_process_announces_the_model_load(tmp_path, capsys):
    root = _project(tmp_path)

    _backend(root, FakeWorker()).synthesize(_request(root))

    assert "Cargando Chatterbox (cuda) en su propio proceso…" in capsys.readouterr().out


def test_default_progress_prints_spanish_parts(capsys):
    external_tts_process._report_progress(2, 5)

    assert capsys.readouterr().out == "  Parte 2 de 5\n"


def test_default_environment_starts_from_the_parent_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_PARENT_VARIABLE", "sí")
    process = ExternalTtsProcess(launcher=FakeWorker())
    runtime = external_tts_process.ExternalTtsRuntime(
        python_path=tmp_path / "python.exe",
        cache_dir=tmp_path / "cache",
        device="cpu",
    )

    environment = process._environment(runtime)

    assert environment["TEST_PARENT_VARIABLE"] == "sí"
    assert environment["HF_HUB_OFFLINE"] == "1"


# --- the worker script's pure parts ----------------------------------------


def _write_request(tmp_path, **changes):
    request = {
        "protocol": 1,
        "device": "cpu",
        "seed": None,
        "segments": [],
        "result": str(tmp_path / "result.json"),
    }
    request.update(changes)
    path = tmp_path / "request.json"
    path.write_text(json.dumps(request), encoding="utf-8")
    return path


def test_worker_rejects_another_protocol_as_configuration(tmp_path):
    path = _write_request(tmp_path, protocol=2)

    assert chatterbox_worker.main(["chatterbox_worker.py", str(path)]) == 1
    assert json.loads((tmp_path / "result.json").read_text(encoding="utf-8")) == {
        "status": "error",
        "kind": "configuration",
        "message": "el script de la voz espera el protocolo 1 y recibió 2.",
    }


def test_worker_turns_an_unexpected_failure_into_a_synthesis_result(tmp_path, monkeypatch):
    path = _write_request(tmp_path)

    def fail(request):
        raise RuntimeError("CUDA out of memory")

    monkeypatch.setattr(chatterbox_worker, "synthesize", fail)

    assert chatterbox_worker.main(["chatterbox_worker.py", str(path)]) == 1
    assert json.loads((tmp_path / "result.json").read_text(encoding="utf-8")) == {
        "status": "error",
        "kind": "synthesis",
        "message": "RuntimeError: CUDA out of memory",
    }


def test_worker_keeps_the_kind_of_its_own_errors(tmp_path, monkeypatch):
    path = _write_request(tmp_path)

    def fail(request):
        raise chatterbox_worker.WorkerError("resource_unavailable", "sin GPU")

    monkeypatch.setattr(chatterbox_worker, "synthesize", fail)

    assert chatterbox_worker.main(["chatterbox_worker.py", str(path)]) == 1
    assert json.loads((tmp_path / "result.json").read_text(encoding="utf-8")) == {
        "status": "error",
        "kind": "resource_unavailable",
        "message": "sin GPU",
    }


def test_worker_writes_the_ok_result_with_its_timings(tmp_path, monkeypatch):
    path = _write_request(tmp_path)
    monkeypatch.setattr(
        chatterbox_worker,
        "synthesize",
        lambda request: (24_000, {"load_seconds": 1.0, "generation_seconds": 2.0}),
    )

    assert chatterbox_worker.main(["chatterbox_worker.py", str(path)]) == 0
    assert json.loads((tmp_path / "result.json").read_text(encoding="utf-8")) == {
        "status": "ok",
        "sample_rate": 24_000,
        "load_seconds": 1.0,
        "generation_seconds": 2.0,
    }


def test_worker_needs_exactly_one_request_argument(capsys):
    assert chatterbox_worker.main(["chatterbox_worker.py"]) == 2
    assert "Uso: chatterbox_worker.py <request.json>" in capsys.readouterr().err


def test_worker_imports_only_the_standard_library_at_module_level():
    source = Path(chatterbox_worker.__file__).read_text(encoding="utf-8")
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


# --- product composition and voice document --------------------------------


def test_default_registry_registers_chatterbox_without_loading_anything(tmp_path):
    registry = build_default_tts_backend_registry(project_root=tmp_path)

    assert registry.backend_keys == ("piper_onnx", "chatterbox_multilingual")
    backend = registry.resolve("chatterbox_multilingual")
    assert isinstance(backend, ChatterboxBackend)
    assert backend._project_root == tmp_path.resolve()


def test_project_voice_document_declares_the_environment_inside_the_project():
    document = json.loads(VOICE_DOCUMENT.read_text(encoding="utf-8"))
    configuration = load_tts_voice_configuration(document)

    voice = configuration.voice
    assert voice.backend_key == "chatterbox_multilingual"
    assert voice.backend_voice_id is None
    assert voice.seed is None
    assert configuration.pacing is not None
    options = voice.backend_options
    assert options["runtime"]["python_path"] == "models/tts/chatterbox/env/Scripts/python.exe"
    assert options["runtime"]["cache_dir"] == "models/tts/_cache"
    assert options["runtime"]["device"] == "cuda"
    assert options["model"]["checkpoint_dir"] == "models/tts/chatterbox/weights"
    assert options["segmentation"]["max_characters"] == 300
    assert dict(options["synthesis"]) == {"exaggeration": 0.5, "cfg_weight": 0.5}


def test_backend_requires_an_explicit_project_root():
    with pytest.raises(TypeError):
        ChatterboxBackend("  ")
    with pytest.raises(TypeError):
        ChatterboxBackend(object())
