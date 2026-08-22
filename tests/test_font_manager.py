import unittest
from pathlib import Path

from app.managers.font_manager import FontManager


class FontManagerTest(
    unittest.TestCase
):

    EXPECTED_FONTS = {
        "gotham": (
            "Gotham Narrow Bold",
            "Gotham Narrow Bold.otf",
        ),
        "unisans": (
            "UniSansHeavyCAPS",
            "Uni Sans Heavy.otf",
        ),
        "oswald": (
            "Oswald",
            "Oswald-VariableFont_wght.ttf",
        ),
        "anton": (
            "Anton",
            "Anton-Regular.ttf",
        ),
    }

    def test_supported_font_aliases_resolve_to_expected_files(self):
        manager = FontManager()

        for alias, (
            resolved_name,
            filename,
        ) in self.EXPECTED_FONTS.items():
            with self.subTest(
                alias=alias
            ):
                self.assertEqual(
                    resolved_name,
                    manager.resolve_name(
                        alias
                    )
                )
                self.assertEqual(
                    filename,
                    manager.resolve_path(
                        alias
                    ).name
                )

    def test_all_documented_font_files_exist(self):
        for _, filename in self.EXPECTED_FONTS.values():
            with self.subTest(
                filename=filename
            ):
                self.assertTrue(
                    (
                        Path("assets/fonts")
                        / filename
                    ).is_file()
                )

    def test_fonts_directory_contains_only_font_files(self):
        fonts_dir = Path(
            "assets/fonts"
        )
        allowed_suffixes = {
            ".otf",
            ".ttf"
        }

        for path in fonts_dir.iterdir():
            if not path.is_file():
                continue

            with self.subTest(
                filename=path.name
            ):
                self.assertIn(
                    path.suffix.lower(),
                    allowed_suffixes
                )

    def test_registered_fonts_match_reference_file(self):
        manager = FontManager()

        for alias, (
            resolved_name,
            filename,
        ) in self.EXPECTED_FONTS.items():
            with self.subTest(
                alias=alias
            ):
                self.assertIn(
                    resolved_name,
                    manager.list_fonts()
                )
                self.assertTrue(
                    (
                        Path("assets/fonts")
                        / filename
                    ).is_file()
                )


if __name__ == "__main__":
    unittest.main()
