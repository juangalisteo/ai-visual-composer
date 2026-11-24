"""VOZ menu order and the stop-with-a-clear-error rule when a voice fails (I6b).

The menu lists the voices by the ``menu_order`` each document declares
(presentation only), then the rest by file name. When the selected voice
fails, the program stops with a Spanish error that names the voice, says what
happened and what to do; it never switches to another voice.
"""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.controllers.interaction.common_options import CommonOptions
from app.controllers.run_controller import RunController
from app.modules.audio.piper_backend import PiperBackend
from app.modules.audio.tts_backend_registry import TtsBackendRegistry
from app.modules.audio.tts_contracts import (
    TtsBackendDiagnostic,
    TtsBackendError,
    TtsBackendErrorKind,
    TtsVoiceConfigurationError,
)
from app.modules.audio.voice_builder import VoiceBuilder
from app.modules.audio.voice_configuration import load_tts_voice_configuration
from app.shared.operational_error import OperationalError
from tests.test_execution_request import _operational_key
from tests.test_menu_helpers import MenuAnswers
from tests.test_piper_backend import _request, _write_model_pair


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VOICE_CONFIGS_PATH = REPOSITORY_ROOT / "config" / "voice_configs"
MENU_ORDER_MESSAGE = (
    "menu_order debe ser un número entero mayor que 0 (la posición de la voz "
    "en el menú VOZ); se recibió "
)
CURRENT_MENU = [
    "\nVOZ\n",
    "1. Chatterbox (natural, GPU)",
    "2. Piper Carlfm (rápida, CPU)",
    "3. Piper Davefx (rápida, CPU)",
]


def _document(display_name, *, backend_key="test_backend", **changes):
    document = {
        "kind": "tts_voice",
        "voice_id": f"test_{display_name.casefold().replace(' ', '_')}",
        "display_name": display_name,
        "backend_key": backend_key,
        "language": "es-ES",
        "prosody": {"speaking_rate": 1.0, "volume_gain_db": 0.0},
        "backend_options": {},
    }
    document.update(changes)
    return document


def _write_documents(folder, documents):
    folder.mkdir(parents=True, exist_ok=True)
    for stem, document in documents.items():
        (folder / f"{stem}.json").write_text(json.dumps(document), encoding="utf-8")
    return folder


# --- menu_order in the voice document ---------------------------------------


@pytest.mark.parametrize("value", (1, 7))
def test_menu_order_is_read_as_declared_presentation_data(value):
    configuration = load_tts_voice_configuration(
        _document("Voz de prueba", menu_order=value)
    )

    assert configuration.menu_order == value


def test_menu_order_is_optional():
    assert load_tts_voice_configuration(_document("Voz de prueba")).menu_order is None


@pytest.mark.parametrize("value", (0, -1, 1.5, True, "1", None))
def test_invalid_menu_order_is_a_spanish_configuration_error(value):
    with pytest.raises(TtsVoiceConfigurationError) as error:
        load_tts_voice_configuration(_document("Voz de prueba", menu_order=value))

    assert str(error.value) == f"{MENU_ORDER_MESSAGE}{value!r}."


def test_menu_order_does_not_change_the_technical_voice():
    plain = load_tts_voice_configuration(_document("Voz de prueba"))
    ordered = load_tts_voice_configuration(_document("Voz de prueba", menu_order=4))

    assert plain.voice == ordered.voice


# --- VOZ menu order ---------------------------------------------------------


def test_menu_lists_declared_order_first_then_the_rest_by_file_name(tmp_path):
    folder = _write_documents(
        tmp_path / "voice_configs",
        {
            "alpha": _document("Tercera", menu_order=3),
            "beta": _document("Sin orden B"),
            "gamma": _document("Primera", menu_order=1),
            "delta": _document("Sin orden D"),
            "omega": _document("Tercera bis", menu_order=3),
            "zeta": _document("Segunda", menu_order=2),
        },
    )
    terminal = MenuAnswers("Sin orden B")

    selected = CommonOptions(
        terminal,
        lambda: pytest.fail("No debe cancelar"),
        folder,
    ).select_voice_config()

    assert selected == "beta"
    assert terminal.messages == [
        "\nVOZ\n",
        "1. Primera",
        "2. Segunda",
        "3. Tercera",
        "4. Tercera bis",
        "5. Sin orden B",
        "6. Sin orden D",
    ]


def test_menu_returns_the_file_of_the_chosen_position(tmp_path):
    folder = _write_documents(
        tmp_path / "voice_configs",
        {
            "a_last": _document("Última", menu_order=9),
            "z_first": _document("Primera", menu_order=1),
        },
    )
    chosen = []

    def selector(items):
        chosen.append(tuple(path.stem for path in items))
        return items[0]

    selected = CommonOptions(
        SimpleNamespace(write=lambda message: None),
        lambda: pytest.fail("No debe cancelar"),
        folder,
    ).select_voice_config(selector=selector)

    assert chosen == [("z_first", "a_last")]
    assert selected == "z_first"


def test_menu_reports_an_invalid_menu_order_as_config_error_with_path(
    tmp_path, monkeypatch
):
    _write_documents(
        tmp_path / "config" / "voice_configs",
        {"test_voice": _document("Voz de prueba", menu_order=0)},
    )
    monkeypatch.chdir(tmp_path)

    with pytest.raises(OperationalError) as error:
        CommonOptions(
            SimpleNamespace(write=lambda message: None),
            lambda: pytest.fail("No debe cancelar"),
            Path("config/voice_configs"),
        ).select_voice_config(selector=lambda items: items[0])

    context = error.value.context
    assert context.family == "CONFIG"
    assert context.user_message == (
        "La configuración de la voz no es válida: en "
        "«config/voice_configs/test_voice.json», "
        f"{MENU_ORDER_MESSAGE}0."
    )


def test_project_voices_declare_chatterbox_carlfm_and_davefx_in_that_order():
    orders = {
        path.stem: json.loads(path.read_text(encoding="utf-8")).get("menu_order")
        for path in VOICE_CONFIGS_PATH.glob("*.json")
    }

    assert orders == {
        "chatterbox_multilingual": 1,
        "piper_carlfm": 2,
        "piper_davefx": 3,
    }


@pytest.mark.parametrize(
    ("visual_pipeline", "pipeline_mode"),
    (
        ("script", "full"),
        ("script", "audio"),
        ("image", "full"),
        ("video", "full"),
    ),
)
def test_voice_menu_is_the_same_wherever_a_voice_is_chosen(
    visual_pipeline, pipeline_mode
):
    terminal = MenuAnswers("Chatterbox (natural, GPU)")
    controller = RunController(terminal=terminal)
    controller.select_visual_pipeline = Mock(return_value=visual_pipeline)
    controller.select_pipeline_mode = Mock(return_value=pipeline_mode)
    controller.select_script_destination = Mock(return_value="video")
    controller.select_profile = Mock(
        return_value={"profile_key": _operational_key(), "subtitle_profile_key": None}
    )
    controller.select_music_category = Mock(return_value=None)
    controller.select_overlays_mode = Mock(return_value="off")
    controller.select_intro_outro = Mock(return_value=None)
    controller.ask_project_name = Mock(return_value="Proyecto")
    controller.ask_clear_output = Mock(return_value=False)

    request = controller.run()

    assert request.route.voice_config_id == "chatterbox_multilingual"
    assert [message.strip("\n") for message in terminal.messages[-4:]] == [
        line.strip("\n") for line in CURRENT_MENU
    ]


# --- a failing voice stops the program; no other voice is tried -------------


class _FailingBackend:
    backend_key = "test_failing_backend"

    def __init__(self, error):
        self.error = error
        self.requests = []

    def synthesize(self, request):
        self.requests.append(request)
        raise self.error


class _RecordingBackend:
    backend_key = "test_other_backend"

    def __init__(self):
        self.requests = []

    def synthesize(self, request):
        self.requests.append(request)
        raise AssertionError("No debe probar otra voz.")


class _Manager:
    def __init__(self, configuration):
        self.configuration = configuration

    def get_tts_voice_configuration(self):
        return self.configuration


def _fail(tmp_path, error):
    configuration = load_tts_voice_configuration(
        _document("Voz de prueba", backend_key="test_failing_backend")
    )
    failing = _FailingBackend(error)
    other = _RecordingBackend()
    builder = VoiceBuilder(
        config_manager=_Manager(configuration),
        backend_registry=TtsBackendRegistry((other, failing)),
        workspace_parent=tmp_path / "workspaces",
    )
    output_path = tmp_path / "voz.mp3"
    with pytest.raises(OperationalError) as caught:
        builder.build("Texto de prueba.", output_path=output_path)
    assert len(failing.requests) == 1
    assert other.requests == []
    assert not output_path.exists()
    assert builder.last_pauses == ()
    assert list((tmp_path / "workspaces").iterdir()) == []
    return caught.value.context


ACTION = (
    "Elige otra voz en el menú VOZ y vuelve a lanzar la operación, o revisa la "
    "instalación de esta voz (docs/INSTALL.md, apartado 10). El programa no "
    "cambia de voz por su cuenta."
)


def test_backend_failure_names_the_voice_what_happened_and_what_to_do(tmp_path):
    context = _fail(
        tmp_path,
        TtsBackendError(
            TtsBackendDiagnostic(
                kind=TtsBackendErrorKind.SYNTHESIS,
                detail="Chatterbox falló: OutOfMemoryError: CUDA out of memory.",
            )
        ),
    )

    assert context.family == "AUDIO"
    assert context.user_message == (
        "No se pudo generar la voz «Voz de prueba»: Chatterbox falló: "
        "OutOfMemoryError: CUDA out of memory."
    )
    assert context.recommended_action == ACTION
    assert context.technical_metadata["backend_key"] == "test_failing_backend"
    assert context.technical_metadata["backend_error_kind"] == "synthesis"


def test_detail_without_final_period_gets_one(tmp_path):
    context = _fail(
        tmp_path,
        TtsBackendError(
            TtsBackendDiagnostic(
                kind=TtsBackendErrorKind.RESOURCE_UNAVAILABLE,
                detail="no se pudo lanzar el proceso de Chatterbox: acceso denegado",
            )
        ),
    )

    assert context.user_message == (
        "No se pudo generar la voz «Voz de prueba»: no se pudo lanzar el proceso "
        "de Chatterbox: acceso denegado."
    )


def test_unexpected_failure_still_names_the_voice(tmp_path):
    context = _fail(tmp_path, RuntimeError("detalle interno"))

    assert context.family == "AUDIO"
    assert context.user_message == "No se pudo generar la voz «Voz de prueba»."
    assert context.recommended_action == ACTION


def test_configuration_failure_names_the_voice_and_offers_another(tmp_path):
    context = _fail(
        tmp_path,
        TtsVoiceConfigurationError("no existe «test_runtime/python.exe»."),
    )

    assert context.family == "CONFIG"
    assert context.user_message == (
        "La configuración de la voz «Voz de prueba» no es válida: no existe "
        "«test_runtime/python.exe»."
    )
    assert context.recommended_action == (
        "Corrige el documento de la voz en config/voice_configs/ o elige otra "
        "voz en el menú VOZ."
    )


def test_voice_document_that_cannot_load_keeps_the_generic_voice_label(tmp_path):
    class _Broken:
        def get_tts_voice_configuration(self):
            raise TtsVoiceConfigurationError("seed debe ser un número entero.")

    builder = VoiceBuilder(
        config_manager=_Broken(),
        backend_registry=TtsBackendRegistry((_RecordingBackend(),)),
        workspace_parent=tmp_path / "workspaces",
    )
    with pytest.raises(OperationalError) as caught:
        builder.build("Texto.", output_path=tmp_path / "voz.mp3")

    assert caught.value.context.user_message == (
        "La configuración de la voz no es válida: seed debe ser un número entero."
    )


# --- Piper's resource errors reach the user in Spanish -----------------------


def test_missing_piper_model_is_described_in_spanish(tmp_path):
    relative = Path("models/audio/piper/fixture/voice.onnx")

    with pytest.raises(TtsBackendError) as error:
        PiperBackend(tmp_path).synthesize(_request(tmp_path, relative))

    assert error.value.diagnostic.kind is TtsBackendErrorKind.RESOURCE_UNAVAILABLE
    assert error.value.diagnostic.detail == "no se encuentra el modelo ONNX de Piper."


def test_empty_piper_sidecar_is_described_in_spanish(tmp_path):
    relative, model_path = _write_model_pair(tmp_path)
    Path(f"{model_path}.json").write_bytes(b"")

    with pytest.raises(TtsBackendError) as error:
        PiperBackend(tmp_path).synthesize(_request(tmp_path, relative))

    assert error.value.diagnostic.detail == (
        "está vacío el .onnx.json del modelo de Piper."
    )
