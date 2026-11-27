"""A project that already exists is never overwritten without asking (A1).

PRUEBA-GS, fallos 2 y 3: «ELIMINAR OUTPUT → 1» emptied the whole output/
folder, and repeating a name overwrote the project without a word.
"""

from unittest.mock import Mock, patch

import pytest

import main
from app.controllers.interaction.common_options import CommonOptions
from app.controllers.interaction.terminal import Terminal
from app.controllers.run_controller import RunController


def _controller(answers, messages):
    answers = iter(answers)
    terminal = Terminal(
        reader=lambda prompt: next(answers),
        writer=messages.append,
    )
    controller = RunController(
        common_options=CommonOptions(
            terminal,
            lambda: pytest.fail("No debe cancelar"),
        )
    )
    controller._print = messages.append
    return controller


@pytest.fixture
def project_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "output" / "existente" / "video").mkdir(parents=True)
    (tmp_path / "output" / "existente" / "video" / "existente.mp4").write_bytes(b"x")
    return tmp_path


def test_a_new_name_asks_nothing_more(project_root):
    messages = []

    result = _controller(("nuevo",), messages).ask_project()

    assert result == ("nuevo", False)
    assert messages == ["\nPROYECTO\n"]
    assert (project_root / "output" / "existente" / "video" / "existente.mp4").is_file()


def test_an_existing_name_can_be_overwritten(project_root):
    messages = []

    result = _controller(("existente", "1"), messages).ask_project()

    assert result == ("existente", True)
    assert messages == [
        "\nPROYECTO\n",
        "\nEl proyecto «existente» ya existe.\n",
        "1. Sobrescribir",
        "2. Poner otro nombre",
    ]
    # Asking removes nothing: main.py does it once the request is complete.
    assert (project_root / "output" / "existente" / "video" / "existente.mp4").is_file()


def test_another_name_is_asked_again_until_it_is_new(project_root):
    messages = []

    result = _controller(("existente", "2", "existente", "2", "otro"), messages).ask_project()

    assert result == ("otro", False)
    assert messages.count("\nPROYECTO\n") == 3
    assert messages.count("\nEl proyecto «existente» ya existe.\n") == 2


def test_the_question_names_the_project_folder(project_root):
    messages = []

    result = _controller(("  exis:tente ", "1"), messages).ask_project()

    assert result == ("exis:tente", True)
    assert "\nEl proyecto «existente» ya existe.\n" in messages


@pytest.mark.parametrize("name", (".", ".."))
def test_a_name_that_is_not_a_folder_inside_output_is_not_valid(project_root, name):
    messages = []

    result = _controller((name, "nuevo"), messages).ask_project()

    assert result == ("nuevo", False)
    assert messages == ["\nPROYECTO\n", "\nOpción no válida.", "\nPROYECTO\n"]


def test_main_overwrites_only_after_the_request_says_so(project_root):
    request = Mock(route=None, project_name="existente", overwrite_project=True)
    events = []

    with patch("main.RunController") as controller, patch(
        "main.FormatCatalog"
    ), patch("main.FontManager"), patch(
        "main.run_application",
        side_effect=lambda request: events.append(
            (project_root / "output" / "existente").exists()
        ),
    ):
        controller.return_value.run.return_value = request
        assert main.main() == 0

    assert events == [False]
    assert (project_root / "output").is_dir()


def test_main_keeps_the_project_without_overwrite(project_root):
    request = Mock(route=None, project_name="existente", overwrite_project=False)

    with patch("main.RunController") as controller, patch(
        "main.FormatCatalog"
    ), patch("main.FontManager"), patch("main.run_application"):
        controller.return_value.run.return_value = request
        assert main.main() == 0

    assert (project_root / "output" / "existente" / "video" / "existente.mp4").is_file()


def test_no_menu_empties_output():
    import inspect

    from app.controllers import run_controller
    from app.controllers.interaction import common_options

    for module in (run_controller, common_options, main):
        source = inspect.getsource(module)
        assert "ELIMINAR OUTPUT" not in source
        assert "reset()" not in source
