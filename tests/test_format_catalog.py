import json
from unittest.mock import patch

import pytest

import main
from app.controllers.interaction.format_catalog import FormatCatalog
from app.controllers.run_controller import RunController
from app.modules.studio import StudioInputMode
from app.shared.operational_error import (
    OperationalError,
    create_operational_error,
)
from app.shared.profile_identity import OperationalProfileKey, ProfileComponent
from app.shared.profile_resolver import OperationalProfileDescriptor
from tests.test_menu_helpers import MenuAnswers


def _profiles_root(tmp_path, *profile_formats):
    root = tmp_path / "profiles"
    for profile_format in profile_formats:
        (root / ProfileComponent.GUION.value / profile_format).mkdir(parents=True)
    return root


def _write_catalog(tmp_path, content):
    path = tmp_path / "formats.json"
    path.write_text(
        content if isinstance(content, str) else json.dumps(content),
        encoding="utf-8",
    )
    return path


def test_without_catalog_formats_use_the_generic_label_and_alphabetical_order(
    tmp_path,
):
    root = _profiles_root(tmp_path, "test_format_b", "test_format_a")
    catalog = FormatCatalog(tmp_path / "formats.json", root)

    assert catalog.ordered(("test_format_b", "test_format_a")) == (
        "test_format_a",
        "test_format_b",
    )
    assert catalog.label("test_format_a") == "Test Format A"


def test_undeclared_formats_follow_the_declared_ones_alphabetically(tmp_path):
    root = _profiles_root(
        tmp_path,
        "test_format_a",
        "test_format_b",
        "test_format_c",
        "other_format",
    )
    path = _write_catalog(tmp_path, {
        "formats": {
            "test_format_c": {"display_name": "Primero declarado", "order": 1},
            "test_format_b": {"display_name": "Segundo declarado", "order": 2},
        },
    })
    catalog = FormatCatalog(path, root)

    assert catalog.ordered(
        ("other_format", "test_format_a", "test_format_b", "test_format_c"),
    ) == ("test_format_c", "test_format_b", "other_format", "test_format_a")
    assert catalog.label("test_format_c") == "Primero declarado"
    assert catalog.label("test_format_b") == "Segundo declarado"
    assert catalog.label("other_format") == "Other Format"


def test_declaration_without_format_directory_is_a_clear_config_error(tmp_path):
    root = _profiles_root(tmp_path, "test_format")
    path = _write_catalog(tmp_path, {
        "formats": {
            "test_format": {"display_name": "Formato técnico", "order": 1},
            "missing_format": {"display_name": "Sin carpeta", "order": 2},
        },
    })

    with pytest.raises(OperationalError) as caught:
        FormatCatalog(path, root).ordered(("test_format",))

    context = caught.value.context
    assert context.family == "CONFIG"
    assert "sin carpeta de perfiles: missing_format." in context.user_message
    assert "test_format" not in context.user_message
    assert context.resource == str(path)
    assert tuple(context.technical_metadata["formats"]) == ("missing_format",)


@pytest.mark.parametrize(
    ("content", "detail"),
    (
        ({"formats": {"test_format": {"order": 1}}}, "formats.test_format.display_name"),
        ({"formats": {"test_format": {"display_name": "Formato técnico"}}}, "formats.test_format.order"),
        ({"formats": {"test_format": {"display_name": "Formato técnico", "order": "primero"}}}, "formats.test_format.order"),
        ({"formats": {"test_format": {"display_name": "   ", "order": 1}}}, "formats.test_format.display_name"),
        ({"formats": {"test_format": "Formato técnico"}}, "formats.test_format"),
        ({"formatos": {}}, "formats"),
        ("{", "Expecting property name"),
    ),
)
def test_invalid_catalog_is_a_config_error_that_names_the_problem(
    tmp_path,
    content,
    detail,
):
    root = _profiles_root(tmp_path, "test_format")
    path = _write_catalog(tmp_path, content)

    with pytest.raises(OperationalError) as caught:
        FormatCatalog(path, root).label("test_format")

    context = caught.value.context
    assert context.family == "CONFIG"
    assert context.user_message.startswith("El catálogo de formatos no es válido:")
    assert detail in context.user_message
    assert context.resource == str(path)


def test_project_catalog_declares_vertical_first_with_its_aspect_ratio():
    catalog = FormatCatalog()

    assert catalog.ordered(("horizontal", "vertical")) == ("vertical", "horizontal")
    assert catalog.label("vertical") == "Vertical 9:16"
    assert catalog.label("horizontal") == "Horizontal 16:9"


def _first_menu(print_mock):
    printed = [str(call.args[0]) for call in print_mock.call_args_list if call.args]
    start = printed.index("\nFORMATO\n")
    return printed[start:start + 3]


def test_every_format_menu_lists_the_declared_order_and_labels():
    controller = RunController()
    menus = {
        "perfil": lambda: controller._select_profile_identity(
            ProfileComponent.GUION,
            select_subtitles=False,
        ),
        "studio": lambda: controller._select_studio_operational_format(
            controller._studio_operational_profiles_by_format(),
        ),
        "subtítulos studio": lambda: controller._select_studio_subtitle_profile(
            StudioInputMode.VIDEO.value,
        ),
    }
    for menu, select in menus.items():
        answers = MenuAnswers(
            "Horizontal 16:9",
            "MODO CONCIENCIA",
            "Modo Conciencia | Línea única",
        )
        with patch("builtins.input", side_effect=answers.input), patch(
            "builtins.print", side_effect=answers.print
        ) as print_mock:
            select()

        assert _first_menu(print_mock) == [
            "\nFORMATO\n",
            "1. Vertical 9:16",
            "2. Horizontal 16:9",
        ], menu


class _TwoFormatResolver:
    def discover_formats(self, component):
        return ("test_format_a", "test_format_b")

    def discover_operational_profiles(self, component, profile_format):
        return (
            OperationalProfileDescriptor(
                key=OperationalProfileKey(component, profile_format, "test_profile"),
                path=None,
                display_name="Perfil técnico",
            ),
        )

    def resolve_operational(self, profile_key):
        return f"{profile_key.format}.json"


def test_run_controller_presents_formats_with_the_injected_catalog(tmp_path):
    root = _profiles_root(tmp_path, "test_format_a", "test_format_b")
    path = _write_catalog(tmp_path, {
        "formats": {"test_format_b": {"display_name": "Formato B", "order": 1}},
    })
    controller = RunController(
        profile_resolver=_TwoFormatResolver(),
        format_catalog=FormatCatalog(path, root),
    )
    answers = MenuAnswers("Test Format A")

    with patch("builtins.input", side_effect=answers.input), patch(
        "builtins.print", side_effect=answers.print
    ) as print_mock:
        selected = controller._select_profile_identity(
            ProfileComponent.GUION,
            select_subtitles=False,
        )

    assert _first_menu(print_mock) == [
        "\nFORMATO\n",
        "1. Formato B",
        "2. Test Format A",
    ]
    assert selected["profile_key"].format == "test_format_a"


def test_studio_summary_uses_the_menu_label_and_survives_a_broken_catalog():
    assert main._format_label("vertical") == "Vertical 9:16"

    class BrokenCatalog:
        def label(self, profile_format):
            raise create_operational_error(
                family="CONFIG",
                user_message="Catálogo roto.",
                recommended_action="Corrija el catálogo.",
                operation="Leer catálogo de formatos",
            )

    with patch.object(main, "FormatCatalog", BrokenCatalog):
        assert main._format_label("test_format") == "Test Format"
