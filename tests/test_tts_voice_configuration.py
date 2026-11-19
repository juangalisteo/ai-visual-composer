import copy
import inspect
import json
from pathlib import Path

import pytest

from app.core.script_length import SpeechPacing
from app.modules.audio.voice_configuration import (
    TtsVoiceConfiguration,
    load_tts_voice_configuration,
)
from app.modules.audio.tts_backend_runtime import (
    build_default_tts_backend_registry,
)
from app.modules.audio.tts_contracts import TtsVoiceConfigurationError
from app.shared.config_manager import ConfigManager
from app.shared.operational_error import OperationalError


VOICE_CONFIGS_PATH = Path("config/voice_configs")


def _document(stem="piper_davefx"):
    return json.loads(
        (VOICE_CONFIGS_PATH / f"{stem}.json").read_text(encoding="utf-8")
    )


def test_current_voice_documents_load_as_neutral_configuration():
    configurations = {
        stem: load_tts_voice_configuration(_document(stem))
        for stem in ("piper_davefx", "piper_carlfm")
    }

    assert all(
        isinstance(configuration, TtsVoiceConfiguration)
        for configuration in configurations.values()
    )
    assert {
        stem: (
            configuration.voice.voice_id,
            configuration.display_name,
            configuration.voice.backend_key,
            configuration.voice.backend_voice_id,
        )
        for stem, configuration in configurations.items()
    } == {
        "piper_davefx": (
            "piper_voice_davefx",
            "Davefx",
            "piper_onnx",
            None,
        ),
        "piper_carlfm": (
            "piper_voice_carlfm",
            "Carlfm",
            "piper_onnx",
            None,
        ),
    }
    assert all(
        configuration.voice.prosody.speaking_rate == 1.0
        and configuration.voice.prosody.volume_gain_db == 0.0
        for configuration in configurations.values()
    )


def test_piper_voice_documents_are_unique_native_baselines_and_resolve_by_backend_key():
    expected_paths = {
        "piper_davefx": "models/audio/piper/es_ES_davefx/es_ES-davefx-medium.onnx",
        "piper_carlfm": "models/audio/piper/es_ES_carlfm/es_ES-carlfm-x_low.onnx",
    }
    configurations = {
        stem: load_tts_voice_configuration(_document(stem))
        for stem in expected_paths
    }
    catalog = tuple(
        load_tts_voice_configuration(json.loads(path.read_text(encoding="utf-8")))
        for path in sorted(VOICE_CONFIGS_PATH.glob("*.json"))
    )
    registry = build_default_tts_backend_registry()

    assert len({configuration.voice.voice_id for configuration in configurations.values()}) == 2
    assert len({configuration.voice.voice_id for configuration in catalog}) == len(catalog)
    assert tuple(path.stem for path in sorted(VOICE_CONFIGS_PATH.glob("*.json"))) == (
        "piper_carlfm",
        "piper_davefx",
    )
    assert "piper_voice_miro" not in {
        configuration.voice.voice_id for configuration in catalog
    }
    assert all(
        configuration.voice.backend_key == "piper_onnx"
        and configuration.voice.backend_voice_id is None
        and configuration.voice.language == "es-ES"
        and configuration.voice.prosody.speaking_rate == 1.0
        and configuration.voice.prosody.volume_gain_db == 0.0
        and configuration.voice.backend_options["synthesis"] == {"length_scale": 1.10}
        for configuration in configurations.values()
    )
    assert {
        stem: configuration.voice.backend_options["model"]["onnx_path"]
        for stem, configuration in configurations.items()
    } == expected_paths
    assert all(
        registry.resolve(configuration.voice.backend_key).backend_key == "piper_onnx"
        for configuration in configurations.values()
    )


def test_display_name_does_not_affect_technical_voice_identity():
    document = _document()
    renamed = copy.deepcopy(document)
    renamed["display_name"] = "Texto humano libre"

    original = load_tts_voice_configuration(document)
    changed = load_tts_voice_configuration(renamed)

    assert changed.display_name == "Texto humano libre"
    assert changed.voice == original.voice


def test_voice_identity_is_opaque_and_does_not_depend_on_document_filename():
    document = _document()
    document["voice_id"] = "technical_voice_fixture"

    configuration = load_tts_voice_configuration(document)

    assert configuration.voice.voice_id == "technical_voice_fixture"
    assert configuration.voice.backend_voice_id is None


@pytest.mark.parametrize("backend_voice_id", ("absent", None))
def test_backend_voice_id_is_optional_for_a_neutral_voice_document(backend_voice_id):
    document = _document()
    if backend_voice_id == "absent":
        document.pop("backend_voice_id", None)
    else:
        document["backend_voice_id"] = backend_voice_id

    configuration = load_tts_voice_configuration(document)

    assert configuration.voice.backend_voice_id is None
    assert configuration.voice.backend_key == "piper_onnx"


def test_backend_options_preserve_nested_json_like_data_without_common_interpretation():
    document = _document()
    document["backend_options"] = {
        "resource": {"path": "models/audio/fixture.onnx", "enabled": True},
        "synthesis": {"values": [0.5, None, "fixture"]},
    }

    configuration = load_tts_voice_configuration(document)

    assert configuration.voice.backend_options["resource"]["path"] == (
        "models/audio/fixture.onnx"
    )
    assert configuration.voice.backend_options["synthesis"]["values"] == (
        0.5,
        None,
        "fixture",
    )


@pytest.mark.parametrize(
    ("field", "value", "error"),
    (
        ("backend_voice_id", " ", "backend_voice_id"),
        ("backend_voice_id", [], "backend_voice_id"),
        ("backend_options", [], "backend_options"),
        ("backend_options", {"invalid": object()}, "JSON-like"),
    ),
)
def test_voice_configuration_rejects_invalid_optional_identity_and_options(
    field,
    value,
    error,
):
    document = _document()
    document[field] = value

    with pytest.raises((TypeError, ValueError), match=error):
        load_tts_voice_configuration(document)


def test_voice_configuration_rejects_unknown_common_fields():
    document = _document()
    document["unexpected_common_field"] = "fixture"

    with pytest.raises(ValueError, match="unknown tts_voice fields"):
        load_tts_voice_configuration(document)


@pytest.mark.parametrize(
    ("mutation", "error"),
    (
        (lambda document: document.pop("voice_id"), "voice_id"),
        (lambda document: document.update({"display_name": " "}), "display_name"),
        (lambda document: document.update({"backend_options": []}), "backend_options"),
        (lambda document: document.update({"kind": "other"}), "kind"),
        (lambda document: document["prosody"].pop("speaking_rate"), "speaking_rate"),
    ),
)
def test_voice_configuration_validates_required_neutral_fields(
    mutation,
    error,
):
    document = _document()
    mutation(document)

    with pytest.raises((TypeError, ValueError), match=error):
        load_tts_voice_configuration(document)


def test_current_voice_documents_declare_sentence_and_paragraph_pauses():
    for stem in ("piper_davefx", "piper_carlfm"):
        prosody = load_tts_voice_configuration(_document(stem)).voice.prosody

        assert prosody.sentence_pause_seconds == 0.5
        assert prosody.paragraph_pause_seconds == 0.35


def test_current_voice_documents_declare_their_measured_pacing():
    for stem in ("piper_davefx", "piper_carlfm"):
        pacing = load_tts_voice_configuration(_document(stem)).pacing

        assert isinstance(pacing, SpeechPacing)
        assert pacing.letters_per_second > pacing.words_per_second > 0


def test_voice_document_without_pacing_has_no_pacing():
    document = _document()
    del document["pacing"]

    assert load_tts_voice_configuration(document).pacing is None


def test_pacing_is_parsed_as_declared_data():
    document = _document()
    document["pacing"] = {"letters_per_second": 12.5, "words_per_second": 2.25}

    assert load_tts_voice_configuration(document).pacing == SpeechPacing(
        letters_per_second=12.5,
        words_per_second=2.25,
    )


@pytest.mark.parametrize(
    ("pacing", "message"),
    (
        ("rápido", "pacing debe ser un objeto con letters_per_second y words_per_second"),
        ({"letters_per_second": 13.0}, "pacing debe declarar words_per_second"),
        (
            {"letters_per_second": 13.0, "words_per_second": 2.5, "speed": 1},
            "pacing no admite las claves: speed",
        ),
        (
            {"letters_per_second": 0, "words_per_second": 2.5},
            "pacing.letters_per_second debe ser un número mayor que cero",
        ),
        (
            {"letters_per_second": 13.0, "words_per_second": -1},
            "pacing.words_per_second debe ser un número mayor que cero",
        ),
        (
            {"letters_per_second": "13", "words_per_second": 2.5},
            "pacing.letters_per_second debe ser un número",
        ),
        (
            {"letters_per_second": True, "words_per_second": 2.5},
            "pacing.letters_per_second debe ser un número",
        ),
    ),
)
def test_invalid_pacing_is_rejected_with_spanish_message(pacing, message):
    document = _document()
    document["pacing"] = pacing

    with pytest.raises(TtsVoiceConfigurationError) as error:
        load_tts_voice_configuration(document)

    assert message in str(error.value)


def test_current_voice_documents_share_the_same_slower_length_scale():
    length_scales = {
        stem: load_tts_voice_configuration(_document(stem)).voice.backend_options[
            "synthesis"
        ]["length_scale"]
        for stem in ("piper_davefx", "piper_carlfm")
    }

    assert length_scales == {"piper_davefx": 1.10, "piper_carlfm": 1.10}


def test_missing_pauses_mean_no_extra_silence():
    document = _document()
    del document["prosody"]["sentence_pause_seconds"]
    del document["prosody"]["paragraph_pause_seconds"]

    prosody = load_tts_voice_configuration(document).voice.prosody

    assert prosody.sentence_pause_seconds == 0.0
    assert prosody.paragraph_pause_seconds == 0.0


@pytest.mark.parametrize("value", (0, 0.0, 2, 0.25))
@pytest.mark.parametrize("field", ("sentence_pause_seconds", "paragraph_pause_seconds"))
def test_pause_accepts_zero_and_positive_seconds(field, value):
    document = _document()
    document["prosody"][field] = value

    assert getattr(load_tts_voice_configuration(document).voice.prosody, field) == value


@pytest.mark.parametrize(
    "value",
    (-0.5, "0.5", True, None, float("nan"), float("inf"), [0.5]),
)
@pytest.mark.parametrize("field", ("sentence_pause_seconds", "paragraph_pause_seconds"))
def test_pause_rejects_invalid_values_with_spanish_message(field, value):
    document = _document()
    document["prosody"][field] = value

    with pytest.raises(TtsVoiceConfigurationError) as error:
        load_tts_voice_configuration(document)

    assert str(error.value).startswith(
        f"prosody.{field} debe ser un número de segundos mayor o igual que 0 "
        "(0 = sin pausa extra); se recibió "
    )


def test_prosody_rejects_unknown_fields_such_as_misspelled_pauses():
    document = _document()
    document["prosody"]["sentence_pause"] = 0.5

    with pytest.raises(TtsVoiceConfigurationError) as error:
        load_tts_voice_configuration(document)

    assert str(error.value) == (
        "prosody no admite las claves: sentence_pause. Claves válidas: "
        "speaking_rate, volume_gain_db, sentence_pause_seconds, "
        "paragraph_pause_seconds."
    )


@pytest.mark.parametrize(
    ("selected_stem", "expected_voice_id", "expected_backend_key"),
    (
        ("piper_davefx", "piper_voice_davefx", "piper_onnx"),
        ("piper_carlfm", "piper_voice_carlfm", "piper_onnx"),
    ),
)
def test_current_terminal_selection_loads_the_same_neutral_voice_document(
    selected_stem,
    expected_voice_id,
    expected_backend_key,
):
    configuration = ConfigManager(
        voice_config_id=selected_stem
    ).get_tts_voice_configuration()

    assert configuration.voice.voice_id == expected_voice_id
    assert configuration.voice.backend_key == expected_backend_key


def test_explicit_voice_config_id_selects_its_own_voice_document(tmp_path):
    voice_configs = tmp_path / "voice_configs"
    voice_configs.mkdir()
    selected_document = _document()
    selected_document["voice_id"] = "technical_voice_selected"
    conflicting_document = _document()
    conflicting_document["voice_id"] = "technical_voice_conflict"
    (voice_configs / "test_voice_selected.json").write_text(
        json.dumps(selected_document),
        encoding="utf-8",
    )
    (voice_configs / "test_voice_conflict.json").write_text(
        json.dumps(conflicting_document),
        encoding="utf-8",
    )
    manager = ConfigManager(voice_config_id="test_voice_selected")
    manager.config_path = tmp_path
    configuration = manager.get_tts_voice_configuration()

    assert configuration.voice.voice_id == "technical_voice_selected"
    assert configuration.voice.backend_key == "piper_onnx"


def test_default_voice_configuration_is_the_approved_piper_davefx_baseline():
    configuration = ConfigManager().get_tts_voice_configuration()

    assert configuration.voice.voice_id == "piper_voice_davefx"
    assert configuration.voice.backend_key == "piper_onnx"
    assert configuration.voice.backend_options["synthesis"] == {"length_scale": 1.10}


def test_invalid_explicit_voice_override_preserves_the_configuration_error():
    with pytest.raises(OperationalError) as error:
        ConfigManager(
            voice_config_id="missing_voice_fixture"
        ).get_tts_voice_configuration()

    assert error.value.context.family == "CONFIG"
    assert isinstance(error.value.__cause__, FileNotFoundError)


@pytest.mark.parametrize("legacy_stem", ("femenina", "masculina", "masculina_santa"))
def test_removed_kokoro_voice_override_preserves_the_configuration_error(legacy_stem):
    with pytest.raises(OperationalError) as error:
        ConfigManager(voice_config_id=legacy_stem).get_tts_voice_configuration()

    assert error.value.context.family == "CONFIG"
    assert isinstance(error.value.__cause__, FileNotFoundError)


def test_configuration_parser_has_no_human_label_or_filename_routing():
    from app.modules.audio import voice_configuration

    source = inspect.getsource(voice_configuration).lower()
    for forbidden in (
        "masculina",
        "femenina",
        ".stem",
        "display_name ==",
        "display_name !=",
    ):
        assert forbidden not in source
