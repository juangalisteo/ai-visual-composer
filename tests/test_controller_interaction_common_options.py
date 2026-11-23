import json

import pytest

from app.controllers.interaction.common_options import CommonOptions
from app.controllers.interaction.terminal import Terminal
from tests.test_menu_helpers import MenuAnswers


def _voice_document(display_name, voice_id):
    return {
        "kind": "tts_voice",
        "voice_id": voice_id,
        "display_name": display_name,
        "backend_key": "fixture_backend",
        "backend_voice_id": "fixture_voice",
        "language": "es-ES",
        "prosody": {"speaking_rate": 1.0, "volume_gain_db": 0.0},
        "backend_options": {},
    }


def test_voice_configs_are_sorted_by_selection_key_labeled_from_document_and_return_the_selected_stem(tmp_path):
    voice_configs = tmp_path / "voice_configs"
    voice_configs.mkdir()
    (voice_configs / "zeta.json").write_text(
        json.dumps(_voice_document("Segunda voz", "fixture_voice_2")),
        encoding="utf-8",
    )
    (voice_configs / "alpha.json").write_text(
        json.dumps(_voice_document("Primera voz", "fixture_voice_1")),
        encoding="utf-8",
    )
    terminal = MenuAnswers("Segunda voz")

    selected = CommonOptions(
        terminal,
        lambda: pytest.fail("No debe cancelar"),
        voice_configs,
    ).select_voice_config()

    assert selected == "zeta"
    assert terminal.messages == [
        "\nVOZ\n",
        "1. Primera voz",
        "2. Segunda voz",
    ]


def test_current_voice_catalog_exposes_chatterbox_and_piper_options_declaratively():
    terminal = MenuAnswers("Chatterbox (natural, GPU)", "Carlfm", "Davefx")
    options = CommonOptions(terminal, lambda: pytest.fail("No debe cancelar"))

    assert options.select_voice_config() == "chatterbox_multilingual"
    assert options.select_voice_config() == "piper_carlfm"
    assert options.select_voice_config() == "piper_davefx"
    assert terminal.messages == [
        "\nVOZ\n",
        "1. Chatterbox (natural, GPU)",
        "2. Carlfm",
        "3. Davefx",
    ] * 3
    assert "Miro" not in terminal.messages

def test_voice_config_keeps_its_existing_file_not_found_contract(tmp_path):
    with pytest.raises(
        FileNotFoundError,
        match="No se encontraron configuraciones en config/voice_configs.",
    ):
        CommonOptions(
            MenuAnswers(),
            lambda: pytest.fail("No debe cancelar"),
            tmp_path,
        ).select_voice_config()


def test_common_music_and_overlays_keep_technical_values_and_texts():
    terminal = MenuAnswers("Aleatoria", "Sin música", "Sí", "No")
    options = CommonOptions(terminal, lambda: pytest.fail("No debe cancelar"))

    assert options.select_music_category() == "random"
    assert options.select_music_category() is None
    assert options.select_overlays_mode() == "on"
    assert options.select_overlays_mode() == "off"
    assert terminal.messages == [
        "\nMÚSICA\n",
        "1. Aleatoria",
        "2. Sin música",
        "\nMÚSICA\n",
        "1. Aleatoria",
        "2. Sin música",
        "\nOVERLAYS\n",
        "1. Sí",
        "2. No",
        "\nOVERLAYS\n",
        "1. Sí",
        "2. No",
    ]


def test_project_name_trims_retries_and_keeps_the_cancel_callback():
    answers = iter(("   ", "  proyecto final  "))
    messages = []
    options = CommonOptions(
        Terminal(reader=lambda prompt: next(answers), writer=messages.append),
        lambda: pytest.fail("No debe cancelar"),
    )

    assert options.ask_project_name() == "proyecto final"
    assert messages == [
        "\nPROYECTO\n",
        "\nOpción no válida.",
    ]

    calls = []

    def cancel():
        calls.append("cancel")
        raise RuntimeError("cancelled")

    with pytest.raises(RuntimeError, match="cancelled"):
        CommonOptions(Terminal(reader=lambda prompt: "0"), cancel).ask_project_name()
    assert calls == ["cancel"]


def test_clear_output_retries_and_returns_a_real_bool():
    answers = iter(("x", "2"))
    messages = []
    options = CommonOptions(
        Terminal(reader=lambda prompt: next(answers), writer=messages.append),
        lambda: pytest.fail("No debe cancelar"),
    )

    assert options.ask_clear_output() is False
    assert messages == [
        "\nELIMINAR OUTPUT\n",
        "1. Sí",
        "2. No",
        "\nOpción no válida.",
    ]
