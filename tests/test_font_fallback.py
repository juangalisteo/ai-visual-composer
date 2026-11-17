"""Fallback font: what FontManager does when a registered font file is missing (G3)."""

import json
import shutil
from pathlib import Path

import pytest

from app.managers.font_manager import FallbackNotices, FontManager
from app.modules.video.config.loaders.subtitle_loader import SubtitleConfigLoader
from app.modules.video.subtitles.subtitle_render_preparation import (
    SubtitleRenderPreparation,
)


# Bundled font that the fixture copies as every test file (metrics need a real font).
REAL_FONT = FontManager().resolve_path("Anton")

CATALOG = {
    "fonts": {
        "test_font": {
            "file": "test_font.otf",
            "aliases": ["test alias"],
            "fallback": "test_fallback",
        },
        "test_other": {
            "file": "test_other.otf",
            "aliases": [],
            "fallback": "test_fallback",
        },
        "test_fallback": {"file": "test_fallback.ttf", "aliases": []},
        "test_lonely": {"file": "test_lonely.otf", "aliases": []},
    }
}

STYLE = {
    "font_size": 22, "bold": True,
    "primary_colour": "&H00000000", "secondary_colour": "&H00FFFFFF",
    "outline_colour": "&H00000000", "back_colour": "&H00000000",
    "border_style": 1, "outline": 0, "shadow": 0, "alignment": 2,
    "margin_v": 55, "margin_l": 0, "margin_r": 0,
    "offset": 0.0, "dynamic": True, "word_effect": "active_pill",
    "pill_colour": "&H0000FFFF", "pill_padding": 6, "pill_radius": 4,
}


@pytest.fixture
def fonts(tmp_path, monkeypatch):
    """A catalog in tmp_path: test_font and test_other fall back to test_fallback.

    The test runs inside tmp_path, so config/fonts.json and assets/fonts/ are
    the same relative paths as in the application. No font file exists until
    the test creates it.
    """
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "fonts.json").write_text(
        json.dumps(CATALOG), encoding="utf-8"
    )
    fonts_dir = tmp_path / "assets" / "fonts"
    fonts_dir.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    return {
        font_name: fonts_dir / entry["file"]
        for font_name, entry in CATALOG["fonts"].items()
    }


def _create(*paths):
    for path in paths:
        shutil.copyfile(REAL_FONT, path)


def test_font_with_its_file_resolves_to_itself_without_warning(fonts, capsys):
    _create(fonts["test_font"], fonts["test_fallback"])
    manager = FontManager()

    assert manager.resolve_name("test alias") == "test_font"
    assert manager.resolve_path("test alias") == fonts["test_font"].resolve()
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("attempt", ("primera", "segunda"))
def test_missing_font_uses_its_fallback_and_warns_once(fonts, capsys, attempt):
    """Run twice: the second run proves each test starts with an empty registry."""
    _create(fonts["test_fallback"])

    for _ in range(3):
        manager = FontManager()
        assert manager.resolve_name("test alias") == "test_fallback"
        assert manager.resolve_path("test_font") == fonts["test_fallback"].resolve()

    assert capsys.readouterr().out == (
        "ADVERTENCIA: falta la fuente «test_font.otf»; los subtítulos usan "
        "«test_fallback» en su lugar. Para usar la original, pon ese archivo "
        "en assets/fonts/.\n"
    )


def test_fallback_warning_never_shows_the_full_path_of_the_computer(fonts, capsys):
    _create(fonts["test_fallback"])

    FontManager().resolve_path("test_font")

    output = capsys.readouterr().out
    assert "en assets/fonts/." in output
    for full_path in (Path.cwd(), Path.cwd().resolve(), fonts["test_font"]):
        assert str(full_path) not in output
        assert full_path.as_posix() not in output


def test_each_missing_font_warns_once(fonts, capsys):
    _create(fonts["test_fallback"])
    manager = FontManager()

    for _ in range(2):
        assert manager.resolve_name("test_font") == "test_fallback"
        assert manager.resolve_name("test_other") == "test_fallback"

    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 2
    assert "«test_font.otf»" in lines[0]
    assert "«test_other.otf»" in lines[1]


def test_each_registry_warns_on_its_own_and_warns_again_after_reset(fonts, capsys):
    _create(fonts["test_fallback"])
    notices = FallbackNotices()

    FontManager(fallback_notices=notices).resolve_name("test_font")
    FontManager(fallback_notices=notices).resolve_name("test_font")
    FontManager().resolve_name("test_font")
    notices.reset()
    FontManager(fallback_notices=notices).resolve_name("test_font")

    assert capsys.readouterr().out.count("ADVERTENCIA:") == 3


def test_missing_font_and_fallback_keep_todays_error(fonts, capsys):
    manager = FontManager()

    assert manager.resolve_name("test_font") == "test_font"
    with pytest.raises(FileNotFoundError) as error:
        manager.resolve_path("test_font")
    assert str(error.value) == (
        f"No existe el archivo de fuente: {fonts['test_font'].resolve()}"
    )
    assert manager.exists("test_font") is False
    assert capsys.readouterr().out == ""


def test_missing_font_without_declared_fallback_keeps_todays_error(fonts, capsys):
    _create(fonts["test_fallback"])
    manager = FontManager()

    assert manager.resolve_name("test_lonely") == "test_lonely"
    with pytest.raises(FileNotFoundError, match="No existe el archivo de fuente"):
        manager.resolve_path("test_lonely")
    assert capsys.readouterr().out == ""


def test_unregistered_font_name_passes_through_unchanged(fonts, capsys):
    manager = FontManager()

    assert manager.resolve_name("Test Unregistered") == "Test Unregistered"
    with pytest.raises(ValueError, match="No existe una ruta registrada"):
        manager.resolve_path("Test Unregistered")
    assert capsys.readouterr().out == ""


def _prepare(tmp_path, font, dynamic):
    source = tmp_path / f"{font}_{dynamic}.srt"
    source.write_text(
        "1\n00:00:00,000 --> 00:00:01,500\nUNO DOS TRES\n", encoding="utf-8"
    )
    style_source = dict(STYLE, font=font, dynamic=dynamic)
    if not dynamic:
        del style_source["word_effect"]
    style = SubtitleConfigLoader().load_render_style(style_source)
    prepared = SubtitleRenderPreparation().prepare(
        source, style, 1080, 1920, style_source
    )
    try:
        if prepared.force_style is not None:
            return prepared.force_style
        return Path(prepared.path).read_text(encoding="utf-8")
    finally:
        prepared.cleanup()


@pytest.mark.parametrize("dynamic", (True, False), ids=("dinamico", "estatico"))
def test_missing_font_renders_exactly_as_its_fallback(fonts, tmp_path, dynamic):
    """Static force_style and dynamic ASS (metrics included) use the fallback."""
    _create(fonts["test_fallback"])

    replaced = _prepare(tmp_path, "test_font", dynamic)
    direct = _prepare(tmp_path, "test_fallback", dynamic)

    assert "test_fallback" in replaced
    assert "test_font" not in replaced
    assert replaced == direct


def test_declared_fallbacks_ship_their_file():
    """Each fallback of the repository catalog is a font whose file is bundled."""
    manager = FontManager()

    for font_name in manager.list_fonts():
        fallback = manager.declaration(font_name).fallback
        if fallback is None:
            continue
        with_file = manager.declaration(fallback)
        assert (FontManager.FONTS_DIR / with_file.file).is_file(), font_name
