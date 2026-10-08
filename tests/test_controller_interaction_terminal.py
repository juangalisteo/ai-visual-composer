import pytest

from app.controllers.interaction.terminal import Terminal
from app.controllers.run_controller import RunController
from app.shared.operational_error import OperationalError


def test_terminal_writes_through_the_injected_writer():
    messages = []

    Terminal(writer=messages.append).write("mensaje")

    assert messages == ["mensaje"]


def test_terminal_retries_invalid_selection_and_preserves_item_identity():
    answers = iter(("x", "3", "2"))
    messages = []
    items = (object(), object())

    selected = Terminal(
        reader=lambda prompt: next(answers),
        writer=messages.append,
    ).select_from_list(items, lambda: pytest.fail("No debe cancelar"))

    assert selected is items[1]
    assert messages == ["\nOpción no válida.", "\nOpción no válida."]


def test_terminal_delegates_zero_to_the_supplied_cancellation_callback():
    calls = []

    def cancel():
        calls.append("cancel")
        raise RuntimeError("cancelled")

    with pytest.raises(RuntimeError, match="cancelled"):
        Terminal(reader=lambda prompt: "0").select_from_list(("uno",), cancel)

    assert calls == ["cancel"]


def test_run_controller_delegates_terminal_and_keeps_cancellation_owner():
    class FakeTerminal:
        def __init__(self):
            self.messages = []
            self.items = None
            self.callback = None

        def write(self, message):
            self.messages.append(message)

        def select_from_list(self, items, on_cancel):
            self.items = items
            self.callback = on_cancel
            return items[0]

    terminal = FakeTerminal()
    controller = RunController(terminal=terminal)

    controller._print("mensaje")
    assert controller._select_from_list(("uno", "dos")) == "uno"
    assert terminal.messages == ["mensaje"]
    assert terminal.items == ("uno", "dos")

    with pytest.raises(OperationalError):
        terminal.callback()
