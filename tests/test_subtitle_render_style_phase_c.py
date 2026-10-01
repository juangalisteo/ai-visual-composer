import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from app.modules.video.config.loaders.subtitle_loader import (
    SubtitleConfigLoader,
)
from app.modules.video.subtitles.subtitle_style_builder import (
    SubtitleStyleBuilder,
)
from app.shared.profile_identity import ProfileKey
from app.shared.operational_error import OperationalError
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


class SubtitleRenderStylePhaseCTest(unittest.TestCase):

    VALID_STYLE = {
        "font": "unisans",
        "font_size": 14,
        "bold": False,
        "primary_colour": "&H00FFFFFF",
        "outline_colour": "&H80000000",
        "back_colour": "&H00000000",
        "border_style": 1,
        "outline": 0,
        "shadow": 1,
        "alignment": 2,
        "margin_v": 55,
        "offset": -0.06,
    }

    def setUp(self):
        self.loader = SubtitleConfigLoader()

    def test_current_style_is_loaded_and_offset_is_not_ass_style(self):
        loaded = self.loader.load_render_style(self.VALID_STYLE)
        style = SubtitleStyleBuilder().build(self.VALID_STYLE)

        self.assertEqual("unisans", loaded.font)
        self.assertEqual(14, loaded.font_size)
        self.assertFalse(loaded.bold)
        self.assertEqual(-0.06, loaded.offset)
        self.assertIn("FontName=UniSansHeavyCAPS", style)
        self.assertIn("FontSize=14", style)
        self.assertIn("Bold=0", style)
        self.assertIn("PrimaryColour=&H00FFFFFF", style)
        self.assertIn("OutlineColour=&H80000000", style)
        self.assertIn("BackColour=&H00000000", style)
        self.assertIn("BorderStyle=1", style)
        self.assertIn("Outline=0", style)
        self.assertIn("Shadow=1", style)
        self.assertIn("Alignment=2", style)
        self.assertIn("MarginV=55", style)
        self.assertNotIn("offset", style.lower())

    def test_font_contract_preserves_aliases_and_external_names(self):
        alias = self.loader.load_render_style(self.VALID_STYLE)
        external_style = self._style(font="External Font")
        external = self.loader.load_render_style(external_style)

        self.assertEqual("unisans", alias.font)
        self.assertEqual("External Font", external.font)
        self.assertIn(
            "FontName=External Font",
            SubtitleStyleBuilder().build(external_style),
        )
        self._assert_invalid("font", "", "render_style.font")
        self._assert_invalid("font", 4, "render_style.font")

    def test_font_size_requires_a_positive_integer_value(self):
        self.assertEqual(18, self._load(font_size=18).font_size)
        self._assert_invalid("font_size", 0, "font_size debe ser > 0")
        self._assert_invalid("font_size", -1, "font_size debe ser > 0")
        self._assert_invalid("font_size", "large", "render_style.font_size")
        self._assert_invalid("font_size", True, "render_style.font_size")

    def test_bold_requires_a_real_boolean(self):
        self.assertTrue(self._load(bold=True).bold)
        self.assertFalse(self._load(bold=False).bold)
        self.assertIn(
            "Bold=1",
            SubtitleStyleBuilder().build(self._style(bold=True)),
        )
        self.assertIn(
            "Bold=0",
            SubtitleStyleBuilder().build(self._style(bold=False)),
        )
        self._assert_invalid("bold", "true", "render_style.bold")
        self._assert_invalid("bold", 1, "render_style.bold")

    def test_ass_colours_require_aabbggrr_hex_notation(self):
        for field in (
            "primary_colour",
            "outline_colour",
            "back_colour",
        ):
            with self.subTest(field=field):
                self.assertEqual(
                    "&H80ABCDEF",
                    getattr(self._load(**{field: "&H80ABCDEF"}), field),
                )
                self._assert_invalid(field, "#FFFFFF", field)
                self._assert_invalid(field, "&H00ABCDE", field)
                self._assert_invalid(field, "&H00ABCDEG", field)

    def test_border_style_accepts_ass_supported_values_only(self):
        for value in (1, 3):
            with self.subTest(value=value):
                self.assertEqual(value, self._load(border_style=value).border_style)
        self._assert_invalid("border_style", 0, "border_style debe ser uno de")
        self._assert_invalid("border_style", 2, "border_style debe ser uno de")

    def test_outline_shadow_alignment_and_margin_v_ranges(self):
        self.assertEqual(0, self._load(outline=0).outline)
        self.assertEqual(0, self._load(shadow=0).shadow)
        self.assertEqual(0, self._load(margin_v=0).margin_v)
        for alignment in range(1, 10):
            with self.subTest(alignment=alignment):
                self.assertEqual(
                    alignment,
                    self._load(alignment=alignment).alignment,
                )
        self._assert_invalid("outline", -1, "outline debe ser >= 0")
        self._assert_invalid("shadow", -1, "shadow debe ser >= 0")
        self._assert_invalid("margin_v", -1, "margin_v debe ser >= 0")
        self._assert_invalid("alignment", 0, "alignment debe estar entre 1 y 9")
        self._assert_invalid("alignment", 10, "alignment debe estar entre 1 y 9")

    def test_offset_is_finite_timing_data(self):
        self.assertEqual(-0.06, self._load(offset=-0.06).offset)
        self.assertEqual(0.0, self._load(offset=0.0).offset)
        self._assert_invalid("offset", float("nan"), "offset debe ser un numero finito")
        self._assert_invalid("offset", True, "render_style.offset")

    def test_standard_and_design_profiles_are_validated_at_resolution(self):
        self._assert_invalid_standard_profile("font_size", 0)
        self._assert_invalid_design_profile("alignment", 10)

    def test_dynamic_profile_is_validated_during_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "profiles"
            main_key = ProfileKey.for_component("guion", "instagram")
            source = self._source_standard()
            data = json.loads(source.read_text(encoding="utf-8"))
            data["profile_id"] = "subtitulo_guion_instagram_prueba_c"
            data["display_name"] = "Prueba C"
            data["render_style"]["shadow"] = -1
            path = (
                root
                / "guion/instagram/estandar/subtitulos"
                / "subtitulo_guion_instagram_prueba_c.json"
            )
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(data), encoding="utf-8")

            with self.assertRaises(OperationalError) as captured:
                SubtitleProfileResolver(root).discover_profiles(main_key)
            self.assertEqual("VALIDATION", captured.exception.context.family)
            self.assertIsInstance(captured.exception.__cause__, ValueError)

    def _assert_invalid_standard_profile(self, field, value):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "profiles"
            key = SubtitleProfileKey.for_profile(
                ProfileKey.for_component("guion", "instagram"),
                "single_line",
            )
            path = root / key.relative_path
            path.parent.mkdir(parents=True)
            data = json.loads(self._source_standard().read_text(encoding="utf-8"))
            data["render_style"][field] = value
            path.write_text(json.dumps(data), encoding="utf-8")

            with self.assertRaises(OperationalError) as captured:
                SubtitleProfileResolver(root).load(key)
            self.assertEqual("VALIDATION", captured.exception.context.family)
            self.assertIsInstance(captured.exception.__cause__, ValueError)

    def _assert_invalid_design_profile(self, field, value):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "profiles"
            key = SubtitleProfileKey(
                "video", "instagram", "modo_conciencia_reels", "design",
            )
            path = root / "video/instagram/design/subtitulos/modo_conciencia_reels.json"
            path.parent.mkdir(parents=True)
            data = json.loads(
                Path(
                    "config/profiles/video/instagram/design/"
                    "subtitulos/modo_conciencia_reels.json"
                ).read_text(encoding="utf-8")
            )
            data["render_style"][field] = value
            path.write_text(json.dumps(data), encoding="utf-8")

            with self.assertRaises(OperationalError) as captured:
                SubtitleProfileResolver(root).load(key)
            self.assertEqual("VALIDATION", captured.exception.context.family)
            self.assertIsInstance(captured.exception.__cause__, ValueError)

    def _assert_invalid(self, field, value, message):
        with self.assertRaisesRegex((TypeError, ValueError), message):
            self._load(**{field: value})

    def _load(self, **changes):
        return self.loader.load_render_style(self._style(**changes))

    def _style(self, **changes):
        style = deepcopy(self.VALID_STYLE)
        style.update(changes)
        return style

    @staticmethod
    def _source_standard():
        return Path(
            "config/profiles/guion/instagram/estandar/subtitulos/"
            "subtitulo_guion_instagram_linea_unica.json"
        )


if __name__ == "__main__":
    unittest.main()
