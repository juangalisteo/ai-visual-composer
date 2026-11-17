import contextlib
import shutil
import tempfile
import unittest
from pathlib import Path

from app.managers.font_manager import FallbackNotices, FontManager


FONTS_DIR = Path("assets/fonts")


class FontManagerTest(
    unittest.TestCase
):

    # alias -> (font name, file in assets/fonts/, fallback font name or None)
    EXPECTED_FONTS = {
        "gotham": (
            "Gotham Narrow Bold",
            "Gotham Narrow Bold.otf",
            "Anton",
        ),
        "unisans": (
            "UniSansHeavyCAPS",
            "Uni Sans Heavy.otf",
            "Anton",
        ),
        "oswald": (
            "Oswald",
            "Oswald-VariableFont_wght.ttf",
            None,
        ),
        "anton": (
            "Anton",
            "Anton-Regular.ttf",
            None,
        ),
    }

    def bundled_fonts(self):
        """Fonts without fallback: the repository ships their file."""
        return {
            alias: expected
            for alias, expected in self.EXPECTED_FONTS.items()
            if expected[2] is None
        }

    def fonts_with_fallback(self):
        """Fonts that may be missing: their fallback replaces them."""
        return {
            alias: expected
            for alias, expected in self.EXPECTED_FONTS.items()
            if expected[2] is not None
        }

    def test_registered_fonts_match_reference_file(self):
        manager = FontManager()

        for alias, (
            resolved_name,
            filename,
            fallback,
        ) in self.EXPECTED_FONTS.items():
            with self.subTest(
                alias=alias
            ):
                declaration = manager.declaration(
                    alias
                )
                self.assertEqual(
                    (resolved_name, filename, fallback),
                    (
                        declaration.name,
                        declaration.file,
                        declaration.fallback,
                    )
                )
                self.assertIn(
                    resolved_name,
                    manager.list_fonts()
                )

    def test_bundled_fonts_have_their_file_and_resolve_to_it(self):
        manager = FontManager()

        for alias, (
            resolved_name,
            filename,
            _,
        ) in self.bundled_fonts().items():
            with self.subTest(
                alias=alias
            ):
                self.assertTrue(
                    (
                        FONTS_DIR
                        / filename
                    ).is_file()
                )
                self.assertEqual(
                    resolved_name,
                    manager.resolve_name(
                        alias
                    )
                )
                self.assertEqual(
                    (FONTS_DIR / filename).resolve(),
                    manager.resolve_path(
                        alias
                    )
                )

    def test_fonts_with_fallback_use_their_file_or_their_fallback(self):
        """In this install: the font's own file if it is there, else its fallback's."""
        manager = FontManager()

        for alias, (
            resolved_name,
            filename,
            fallback,
        ) in self.fonts_with_fallback().items():
            with self.subTest(
                alias=alias
            ):
                if (FONTS_DIR / filename).is_file():
                    expected_name = resolved_name
                    expected_file = filename
                else:
                    expected_name = fallback
                    expected_file = manager.declaration(
                        fallback
                    ).file

                self.assertEqual(
                    expected_name,
                    manager.resolve_name(
                        alias
                    )
                )
                self.assertEqual(
                    (FONTS_DIR / expected_file).resolve(),
                    manager.resolve_path(
                        alias
                    )
                )

    def test_fonts_with_fallback_use_it_when_their_file_is_missing(self):
        """Repository catalog with only the bundled fonts on disk, in any install."""
        catalog = Path("config/fonts.json").resolve()
        bundled_files = [
            (FONTS_DIR / filename).resolve()
            for _, filename, _ in self.bundled_fonts().values()
        ]
        files_by_name = {
            resolved_name: filename
            for resolved_name, filename, _ in self.EXPECTED_FONTS.values()
        }

        with tempfile.TemporaryDirectory() as directory, contextlib.chdir(
            directory
        ):
            Path("config").mkdir()
            shutil.copyfile(catalog, "config/fonts.json")
            FONTS_DIR.mkdir(parents=True)
            for path in bundled_files:
                shutil.copyfile(path, FONTS_DIR / path.name)
            manager = FontManager(
                fallback_notices=FallbackNotices()
            )

            for alias, (
                _,
                _,
                fallback,
            ) in self.fonts_with_fallback().items():
                with self.subTest(
                    alias=alias
                ):
                    self.assertEqual(
                        fallback,
                        manager.resolve_name(
                            alias
                        )
                    )
                    self.assertEqual(
                        (
                            FONTS_DIR
                            / files_by_name[fallback]
                        ).resolve(),
                        manager.resolve_path(
                            alias
                        )
                    )

    def test_fonts_directory_contains_only_font_files(self):
        allowed_suffixes = {
            ".otf",
            ".ttf"
        }

        for path in FONTS_DIR.iterdir():
            if not path.is_file():
                continue

            with self.subTest(
                filename=path.name
            ):
                self.assertIn(
                    path.suffix.lower(),
                    allowed_suffixes
                )


if __name__ == "__main__":
    unittest.main()
