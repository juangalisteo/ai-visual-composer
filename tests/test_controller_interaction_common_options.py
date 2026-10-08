from unittest.mock import Mock, call

import pytest

from app.controllers.interaction.common_options import CommonOptions
from app.controllers.interaction.terminal import Terminal


class SelectingTerminal:
    def __init__(self, positions=()):
        self._positions = iter(positions)
        self.messages = []

    def write(self, message):
        self.messages.append(message)

    def select_from_list(self, items, on_cancel):
        return items[next(self._positions) - 1]


def test_voice_configs_are_sorted_labeled_and_return_the_selected_stem(tmp_path):
    voice_configs = tmp_path / "voice_configs"
    voice_configs.mkdir()
    (voice_configs / "zeta.json").write_text("{}", encoding="utf-8")
    (voice_configs / "femenina.json").write_text("{}", encoding="utf-8")
    terminal = SelectingTerminal((2,))

    selected = CommonOptions(
        terminal,
        lambda: pytest.fail("No debe cancelar"),
        voice_configs,
    ).select_voice_config()

    assert selected == "zeta"
    assert terminal.messages == [
        "\nVOZ\n",
        "1. Femenina",
        "2. Zeta",
    ]


def test_voice_config_keeps_its_existing_file_not_found_contract(tmp_path):
    with pytest.raises(
        FileNotFoundError,
        match="No se encontraron configuraciones en config/voice_configs.",
    ):
        CommonOptions(
            SelectingTerminal(),
            lambda: pytest.fail("No debe cancelar"),
            tmp_path,
        ).select_voice_config()


def test_common_music_and_overlays_keep_technical_values_and_texts():
    terminal = SelectingTerminal((1, 2, 1, 2))
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
