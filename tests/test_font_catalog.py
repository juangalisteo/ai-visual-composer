"""Font catalog (config/fonts.json): what FontManager reads and what it rejects."""

import json
from unittest.mock import patch

import pytest

import main
from app.managers.font_manager import FontDeclaration, FontManager
from app.shared.operational_error import OperationalError


def _write_catalog(tmp_path, content):
    path = tmp_path / "fonts.json"
    path.write_text(
        content if isinstance(content, str) else json.dumps(content),
        encoding="utf-8",
    )
    return path


def _font(file_name="test_font.otf", aliases=(), fallback=None):
    entry = {"file": file_name, "aliases": list(aliases)}
    if fallback is not None:
        entry["fallback"] = fallback
    return entry


def test_catalog_declares_name_file_aliases_and_fallback(tmp_path):
    path = _write_catalog(tmp_path, {
        "fonts": {
            "test_font": _font(
                aliases=(" Test Alias ", "test_font"), fallback="test_fallback"
            ),
            "test_fallback": _font("test_fallback.ttf", ("test_fallback",)),
        },
    })
    manager = FontManager(path)

    manager.validate()
    assert manager.list_fonts() == ("test_font", "test_fallback")
    assert manager.declaration("TEST ALIAS") == FontDeclaration(
        name="test_font",
        file="test_font.otf",
        aliases=("test alias", "test_font"),
        fallback="test_fallback",
    )
    assert manager.declaration("test_fallback").fallback is None
    assert manager.declaration("test_unregistered") is None


@pytest.mark.parametrize(
    ("fonts", "detail"),
    (
        pytest.param(
            {"test_font": _font(fallback="test_missing")},
            "La reserva «test_missing» de la fuente «test_font» no está en "
            "el catálogo.",
            id="reserva_que_no_existe",
        ),
        pytest.param(
            {
                "test_font": _font(fallback="test_fallback"),
                "test_fallback": _font("test_fallback.ttf", fallback="test_other"),
                "test_other": _font("test_other.ttf"),
            },
            "La reserva «test_fallback» de la fuente «test_font» tiene a su "
            "vez reserva («test_other»); solo se admite un nivel.",
            id="reserva_de_una_reserva",
        ),
        pytest.param(
            {"test_font": _font(fallback="test_font")},
            "La reserva «test_font» de la fuente «test_font» tiene a su vez "
            "reserva («test_font»); solo se admite un nivel.",
            id="reserva_de_si_misma",
        ),
        pytest.param(
            {
                "test_font": _font(aliases=("test alias",)),
                "test_other": _font("test_other.otf", ("Test Alias ",)),
            },
            "El alias «test alias» está repetido (en «test_font» y en "
            "«test_other»).",
            id="alias_repetido",
        ),
        pytest.param(
            {"test_font": _font(aliases=("test alias", "TEST ALIAS"))},
            "El alias «test alias» está repetido en «test_font».",
            id="alias_repetido_en_la_misma_fuente",
        ),
        pytest.param(
            {"test_font": _font("../test_font.otf")},
            "La configuración fonts.test_font.file («../test_font.otf») queda "
            "fuera de assets/fonts/: debe ser solo el nombre del archivo.",
            id="archivo_en_la_carpeta_de_arriba",
        ),
        pytest.param(
            {"test_font": _font("test_folder/test_font.otf")},
            "fonts.test_font.file («test_folder/test_font.otf») queda fuera",
            id="archivo_en_subcarpeta",
        ),
        pytest.param(
            {"test_font": _font("test_folder\\test_font.otf")},
            "fonts.test_font.file («test_folder\\test_font.otf») queda fuera",
            id="archivo_en_subcarpeta_windows",
        ),
        pytest.param(
            {"test_font": _font("C:/test_font.otf")},
            "fonts.test_font.file («C:/test_font.otf») queda fuera",
            id="ruta_absoluta",
        ),
        pytest.param(
            {"test_font": _font("..")},
            "fonts.test_font.file («..») queda fuera",
            id="carpeta_de_arriba",
        ),
        pytest.param(
            {"test_font": {"aliases": []}},
            "Falta la configuración obligatoria: fonts.test_font.file.",
            id="sin_archivo",
        ),
        pytest.param(
            {"test_font": {"file": "test_font.otf"}},
            "Falta la configuración obligatoria: fonts.test_font.aliases.",
            id="sin_alias",
        ),
        pytest.param(
            {"test_font": _font(aliases=("test alias", "  "))},
            "La configuración fonts.test_font.aliases[1] debe contener texto.",
            id="alias_vacio",
        ),
        pytest.param(
            {"test_font": _font(fallback="  ")},
            "La configuración fonts.test_font.fallback debe contener texto.",
            id="reserva_vacia",
        ),
    ),
)
def test_invalid_catalog_is_a_config_error_that_names_the_problem(
    tmp_path,
    fonts,
    detail,
):
    path = _write_catalog(tmp_path, {"fonts": fonts})

    with pytest.raises(OperationalError) as caught:
        FontManager(path).validate()

    context = caught.value.context
    assert context.family == "CONFIG"
    assert context.user_message.startswith("El catálogo de fuentes no es válido:")
    assert detail in context.user_message
    assert context.resource == str(path)


@pytest.mark.parametrize(
    ("content", "detail"),
    (
        ("{", "Expecting property name"),
        ({"fuentes": {}}, "Falta la configuración obligatoria: fonts."),
        ({"fonts": {"test_font": "test_font.otf"}}, "fonts.test_font debe ser un diccionario"),
    ),
)
def test_broken_catalog_fails_on_first_use_too(tmp_path, content, detail):
    path = _write_catalog(tmp_path, content)

    with pytest.raises(OperationalError) as caught:
        FontManager(path).resolve_name("test_font")

    assert caught.value.context.family == "CONFIG"
    assert detail in caught.value.context.user_message


def test_without_catalog_every_name_passes_through(tmp_path):
    """Like config/formats.json: no file, no declared font."""
    manager = FontManager(tmp_path / "fonts.json")

    manager.validate()
    assert manager.list_fonts() == ()
    assert manager.resolve_name("Test Font") == "Test Font"
    with pytest.raises(ValueError, match="No existe una ruta registrada"):
        manager.resolve_path("Test Font")


def test_repository_catalog_is_valid():
    manager = FontManager()

    manager.validate()
    assert manager.list_fonts()


def test_main_stops_before_the_first_menu_when_the_font_catalog_is_broken(tmp_path):
    path = _write_catalog(tmp_path, {
        "fonts": {"test_font": _font(fallback="test_missing")},
    })

    with patch("main.FontManager", return_value=FontManager(path)), patch(
        "main.RunController"
    ) as controller, patch("builtins.print") as print_mock:
        result = main.main()

    assert result == 1
    controller.assert_not_called()
    output = print_mock.call_args.args[0]
    assert output.startswith("ERROR\n")
    assert "El catálogo de fuentes no es válido" in output
    assert "«test_missing»" in output
    assert str(path) in output
