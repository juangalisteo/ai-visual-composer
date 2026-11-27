import json
from unittest.mock import patch

import pytest

import main
from app.cli import studio_summary
from app.controllers.run_controller import RunController
from app.modules.studio import StudioInputMode
from app.shared.format_catalog import FormatCatalog, SceneSeconds
from app.shared.operational_error import OperationalError
from app.shared.profile_identity import OperationalProfileKey, ProfileComponent
from app.shared.profile_resolver import (
    OperationalProfileDescriptor,
    ProfileResolver,
)
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
    catalog = FormatCatalog(tmp_path / "formats.json")

    assert catalog.ordered(("test_format_b", "test_format_a")) == (
        "test_format_a",
        "test_format_b",
    )
    assert catalog.label("test_format_a") == "Test Format A"


def test_undeclared_formats_follow_the_declared_ones_alphabetically(tmp_path):
    path = _write_catalog(tmp_path, {
        "formats": {
            "test_format_c": {"display_name": "Primero declarado", "order": 1},
            "test_format_b": {"display_name": "Segundo declarado", "order": 2},
        },
    })
    catalog = FormatCatalog(path)

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
        FormatCatalog(path).validate(ProfileResolver(root))

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
        ({"formats": {"test_format": {"display_name": "Formato técnico", "order": 1, "orientation": "test_orientation"}}}, "formats.test_format.orientation debe ser portrait o landscape"),
        ({"formats": {"test_format": {"display_name": "Formato técnico", "order": 1, "image_guidance": "   "}}}, "formats.test_format.image_guidance"),
        ({"formats": {"test_format": {"display_name": "Formato técnico", "order": 1, "scene_seconds": 7}}}, "formats.test_format.scene_seconds"),
        ({"formats": {"test_format": {"display_name": "Formato técnico", "order": 1, "scene_seconds": {"min": 5, "target_min": 6, "target_max": 8}}}}, "formats.test_format.scene_seconds.max"),
        ({"formats": {"test_format": {"display_name": "Formato técnico", "order": 1, "scene_seconds": {"min": 5, "target_min": "seis", "target_max": 8, "max": 9}}}}, "formats.test_format.scene_seconds.target_min"),
        ({"formats": {"test_format": {"display_name": "Formato técnico", "order": 1, "scene_seconds": {"min": 5, "target_min": 6, "target_max": 8, "max": True}}}}, "formats.test_format.scene_seconds.max"),
        ({"formats": {"test_format": {"display_name": "Formato técnico", "order": 1, "scene_seconds": {"min": 0, "target_min": 6, "target_max": 8, "max": 9}}}}, "0 < min <= target_min <= target_max <= max"),
        ({"formats": {"test_format": {"display_name": "Formato técnico", "order": 1, "scene_seconds": {"min": 5, "target_min": 8, "target_max": 6, "max": 9}}}}, "0 < min <= target_min <= target_max <= max"),
        ({"formats": {"test_format": {"display_name": "Formato técnico", "order": 1, "scene_seconds": {"min": 5, "target_min": 6, "target_max": 10, "max": 9}}}}, "0 < min <= target_min <= target_max <= max"),
        ({"formats": {"test_format": {"display_name": "Formato técnico", "order": 1, "scene_seconds": {"min": 6.5, "target_min": 6, "target_max": 8, "max": 9}}}}, "0 < min <= target_min <= target_max <= max"),
    ),
)
def test_invalid_catalog_is_a_config_error_that_names_the_problem(
    tmp_path,
    content,
    detail,
):
    path = _write_catalog(tmp_path, content)

    with pytest.raises(OperationalError) as caught:
        FormatCatalog(path).label("test_format")

    context = caught.value.context
    assert context.family == "CONFIG"
    assert context.user_message.startswith("El catálogo de formatos no es válido:")
    assert detail in context.user_message
    assert context.resource == str(path)


def test_orientation_and_image_guidance_come_only_from_the_declaration(tmp_path):
    path = _write_catalog(tmp_path, {
        "formats": {
            "test_portrait_format": {
                "display_name": "Formato técnico alto",
                "order": 1,
                "orientation": "portrait",
                "image_guidance": "test portrait guidance",
            },
            "test_bare_format": {"display_name": "Formato técnico", "order": 2},
        },
    })
    catalog = FormatCatalog(path)

    assert catalog.orientation("test_portrait_format") == "portrait"
    assert catalog.image_guidance("test_portrait_format") == "test portrait guidance"
    assert catalog.orientation("test_bare_format") is None
    assert catalog.orientation("test_undeclared_format") is None
    for profile_format in ("test_bare_format", "test_undeclared_format"):
        with pytest.raises(OperationalError) as caught:
            catalog.image_guidance(profile_format)

        context = caught.value.context
        assert context.family == "CONFIG"
        assert "image_guidance" in context.user_message
        assert f"«{profile_format}»" in context.user_message
        assert context.resource == str(path)


def test_scene_seconds_come_only_from_the_declaration(tmp_path):
    path = _write_catalog(tmp_path, {
        "formats": {
            "test_timed_format": {
                "display_name": "Formato técnico con escenas",
                "order": 1,
                "scene_seconds": {
                    "min": 4,
                    "target_min": 4.5,
                    "target_max": 7,
                    "max": 7,
                },
            },
            "test_bare_format": {"display_name": "Formato técnico", "order": 2},
        },
    })
    catalog = FormatCatalog(path)

    assert catalog.scene_seconds("test_timed_format") == SceneSeconds(
        min=4.0,
        target_min=4.5,
        target_max=7.0,
        max=7.0,
    )
    for profile_format in ("test_bare_format", "test_undeclared_format"):
        with pytest.raises(OperationalError) as caught:
            catalog.scene_seconds(profile_format)

        context = caught.value.context
        assert context.family == "CONFIG"
        assert "scene_seconds" in context.user_message
        assert f"«{profile_format}»" in context.user_message
        assert context.resource == str(path)


def test_project_catalog_declares_vertical_first_with_its_aspect_ratio():
    catalog = FormatCatalog()

    assert catalog.ordered(("horizontal", "vertical")) == ("vertical", "horizontal")
    assert catalog.label("vertical") == "Vertical 9:16"
    assert catalog.label("horizontal") == "Horizontal 16:9"
    assert catalog.orientation("vertical") == "portrait"
    assert catalog.orientation("horizontal") == "landscape"
    assert catalog.image_guidance("vertical") == "vertical 9:16"
    assert catalog.image_guidance("horizontal") == "wide horizontal 16:9"
    for profile_format in ("vertical", "horizontal"):
        # T0: scenes of about 6 s (owner decision).
        assert catalog.scene_seconds(profile_format) == SceneSeconds(
            min=4.0,
            target_min=5.0,
            target_max=7.0,
            max=8.0,
        )
    catalog.validate(ProfileResolver())


def test_main_stops_before_the_first_menu_when_the_catalog_is_broken(tmp_path):
    path = _write_catalog(tmp_path, "{")

    with patch("main.FormatCatalog", return_value=FormatCatalog(path)), patch(
        "main.RunController"
    ) as controller, patch("builtins.print") as print_mock:
        result = main.main()

    assert result == 1
    controller.assert_not_called()
    output = print_mock.call_args.args[0]
    assert output.startswith("ERROR\n")
    assert "El catálogo de formatos no es válido" in output
    assert str(path) in output


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
    path = _write_catalog(tmp_path, {
        "formats": {"test_format_b": {"display_name": "Formato B", "order": 1}},
    })
    controller = RunController(
        profile_resolver=_TwoFormatResolver(),
        format_catalog=FormatCatalog(path),
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


def test_studio_summary_uses_the_menu_label():
    assert studio_summary._format_label("vertical") == "Vertical 9:16"
    assert studio_summary._format_label("test_format") == "Test Format"
