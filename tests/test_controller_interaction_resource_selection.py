from pathlib import Path
from unittest.mock import Mock

import pytest

from app.controllers.interaction.resource_selection import ResourceSelection
from app.controllers.interaction.terminal import Terminal
from tests.test_menu_helpers import MenuAnswers


class SelectingTerminal(MenuAnswers):
    def __init__(self, *labels):
        super().__init__(*labels)
        self.select_calls = 0

    def select_from_list(self, items, on_cancel):
        self.select_calls += 1
        return super().select_from_list(items, on_cancel)


def test_studio_candidate_bypasses_the_menu_and_returns_the_original_path():
    terminal = SelectingTerminal()
    candidate = Path("input/studio/video/source.mp4")
    selection = ResourceSelection(
        terminal,
        lambda: pytest.fail("No debe cancelar"),
        Mock(),
    )

    assert selection.select_studio_input_candidate(
        "VIDEO",
        (candidate,),
        direct=True,
    ) is candidate
    assert terminal.messages == []
    assert terminal.select_calls == 0


def test_studio_candidate_keeps_discovery_order_and_original_path():
    first = Path("input/studio/video/Zeta.mp4")
    second = Path("input/studio/video/alpha.mp4")
    terminal = SelectingTerminal("alpha.mp4")
    selection = ResourceSelection(
        terminal,
        lambda: pytest.fail("No debe cancelar"),
        Mock(),
    )

    assert selection.select_studio_input_candidate(
        "VIDEO",
        (first, second),
        direct=False,
    ) is second
    assert terminal.messages == [
        "\nVIDEO\n",
        "1. Zeta.mp4",
        "2. alpha.mp4",
    ]


def test_studio_music_skips_the_domain_selector_when_disabled():
    music_selector = Mock()
    terminal = SelectingTerminal("No")

    assert ResourceSelection(
        terminal,
        lambda: pytest.fail("No debe cancelar"),
        music_selector,
    ).select_studio_music() is None
    music_selector.select.assert_not_called()
    assert terminal.messages == ["\nMÚSICA\n", "1. Sí", "2. No"]


def test_studio_music_delegates_random_selection_only_when_enabled():
    music_selector = Mock()
    track = Path("assets/music/track.mp3")
    music_selector.select.return_value = track

    assert ResourceSelection(
        SelectingTerminal("Sí"),
        lambda: pytest.fail("No debe cancelar"),
        music_selector,
    ).select_studio_music() is track
    music_selector.select.assert_called_once_with("random")


def test_resource_selection_keeps_terminal_cancellation_callback():
    calls = []

    def cancel():
        calls.append("cancel")
        raise RuntimeError("cancelled")

    with pytest.raises(RuntimeError, match="cancelled"):
        ResourceSelection(Terminal(reader=lambda prompt: "0"), cancel, Mock()) \
            .select_studio_music()
    assert calls == ["cancel"]
