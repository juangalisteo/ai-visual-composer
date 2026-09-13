import json
import shutil
import subprocess
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
from app.modules.video.video_config import VideoConfig
from app.shared.profile_identity import ProfileKey
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


class SubtitleTypographyPhaseETest(unittest.TestCase):

    BASE_STYLE = {
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
    EXTENDED_STYLE = {
        **BASE_STYLE,
        "italic": True,
        "underline": False,
        "strikeout": True,
        "secondary_colour": "&H80ABCDEF",
        "margin_l": 0,
        "margin_r": 40,
        "scale_x": 100,
        "scale_y": 110.5,
        "spacing": 2.0,
    }

    def setUp(self):
        self.loader = SubtitleConfigLoader()

    def test_optional_fields_are_loaded_and_emitted_with_ass_names(self):
        config = self.loader.load_render_style(self.EXTENDED_STYLE)
        style = SubtitleStyleBuilder().build(self.EXTENDED_STYLE)

        self.assertTrue(config.italic)
        self.assertFalse(config.underline)
        self.assertTrue(config.strikeout)
        self.assertEqual("&H80ABCDEF", config.secondary_colour)
        self.assertEqual(0, config.margin_l)
        self.assertEqual(40, config.margin_r)
        self.assertEqual(100.0, config.scale_x)
        self.assertEqual(110.5, config.scale_y)
        self.assertEqual(2.0, config.spacing)
        for expected in (
            "Italic=1",
            "Underline=0",
            "StrikeOut=1",
            "SecondaryColour=&H80ABCDEF",
            "MarginL=0",
            "MarginR=40",
            "ScaleX=100",
            "ScaleY=110.5",
            "Spacing=2.0",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, style)

    def test_absent_optional_fields_preserve_the_existing_force_style(self):
        style = SubtitleStyleBuilder().build(self.BASE_STYLE)
        config = self.loader.load_render_style(self.BASE_STYLE)

        self.assertIsNone(config.italic)
        self.assertIsNone(config.secondary_colour)
        self.assertIsNone(config.margin_l)
        self.assertIsNone(config.scale_x)
        for key in (
            "Italic=",
            "Underline=",
            "StrikeOut=",
            "SecondaryColour=",
            "MarginL=",
            "MarginR=",
            "ScaleX=",
            "ScaleY=",
            "Spacing=",
        ):
            with self.subTest(key=key):
                self.assertNotIn(key, style)

    def test_video_config_preserves_declared_optional_fields_for_the_builder(self):
        subtitle_config = self.loader.load_render_style(self.EXTENDED_STYLE)
        video_config = VideoConfig(
            width=1080,
            height=1920,
            fps=30,
            pixel_format="yuv420p",
            subtitles=subtitle_config,
            motion=None,
            transitions=None,
            overlays=None,
            visual_effects=None,
            fade=None,
            validation=None,
            codec="libx264",
            preset="medium",
            crf=18,
            audio_codec="aac",
            audio_bitrate="192k",
            movflags="+faststart",
        )

        style = video_config.subtitle_style
        self.assertTrue(style["italic"])
        self.assertEqual("&H80ABCDEF", style["secondary_colour"])
        self.assertEqual(40, style["margin_r"])
        self.assertIn("ScaleY=110.5", SubtitleStyleBuilder().build(style))

    def test_optional_booleans_require_real_booleans(self):
        for field in ("italic", "underline", "strikeout"):
            with self.subTest(field=field, value=True):
                self.assertTrue(
                    self._load(**{field: True}).__getattribute__(field)
                )
            with self.subTest(field=field, value=False):
                self.assertFalse(
                    self._load(**{field: False}).__getattribute__(field)
                )
            self._assert_invalid(field, "true", f"render_style.{field}")

    def test_secondary_colour_uses_the_existing_ass_contract(self):
        self.assertEqual(
            "&H00A1B2C3",
            self._load(secondary_colour="&H00A1B2C3").secondary_colour,
        )
        self._assert_invalid(
            "secondary_colour",
            "&H00A1B2CG",
            "secondary_colour",
        )
        self._assert_invalid(
            "secondary_colour",
            "&H00A1B2C",
            "secondary_colour",
        )

    def test_optional_margins_are_nonnegative_integers(self):
        for field in ("margin_l", "margin_r"):
            with self.subTest(field=field):
                self.assertEqual(0, getattr(self._load(**{field: 0}), field))
                self.assertEqual(25, getattr(self._load(**{field: 25}), field))
                self._assert_invalid(field, -1, f"render_style.{field}")
                self._assert_invalid(field, 1.5, f"render_style.{field}")
                self._assert_invalid(field, "25", f"render_style.{field}")

    def test_optional_scale_and_spacing_are_finite_numbers(self):
        for field in ("scale_x", "scale_y", "spacing"):
            with self.subTest(field=field):
                self.assertEqual(12.5, getattr(self._load(**{field: 12.5}), field))
                self._assert_invalid(field, float("nan"), f"render_style.{field}")
                self._assert_invalid(field, float("inf"), f"render_style.{field}")
                self._assert_invalid(field, "12.5", f"render_style.{field}")

    def test_standard_design_and_dynamic_profiles_share_the_contract(self):
        self._assert_standard_profile()
        self._assert_design_profile()
        self._assert_dynamic_profile()

    def _assert_standard_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "profiles"
            key = SubtitleProfileKey.for_profile(
                ProfileKey.for_component("video", "instagram"),
                "single_line",
            )
            path = root / key.relative_path
            path.parent.mkdir(parents=True)
            data = self._source_standard("video").copy()
            data["render_style"].update(self.EXTENDED_STYLE)
            path.write_text(json.dumps(data), encoding="utf-8")

            resolved = SubtitleProfileResolver(root).load(key)
            self.assertIn("Italic=1", SubtitleStyleBuilder().build(resolved.render_style))

    def _assert_design_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "profiles"
            profile_key = ProfileKey.for_component(
                "video",
                "instagram",
                family="design",
                profile_id="video_instagram_design_modo_conciencia_reels",
            )
            key = SubtitleProfileKey.for_profile(profile_key, "word_by_word")
            path = root / key.relative_path
            path.parent.mkdir(parents=True)
            data = json.loads(
                Path(
                    "config/profiles/video/instagram/design/"
                    "modo_conciencia_reels.json"
                ).read_text(encoding="utf-8")
            )
            data["subtitle_profile"]["render_style"].update(self.EXTENDED_STYLE)
            path.write_text(json.dumps(data), encoding="utf-8")

            resolved = SubtitleProfileResolver(root).load(key)
            self.assertIn("MarginR=40", SubtitleStyleBuilder().build(resolved.render_style))

    def _assert_dynamic_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "profiles"
            profile_key = ProfileKey.for_component("studio", "instagram")
            data = self._source_standard("studio").copy()
            profile_id = "subtitulo_studio_instagram_linea_unica_tipografico"
            data["profile_id"] = profile_id
            data["display_name"] = "Tipografico"
            data["render_style"].update(self.EXTENDED_STYLE)
            path = root / "studio/instagram/estandar" / f"{profile_id}.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(data), encoding="utf-8")

            resolver = SubtitleProfileResolver(root)
            descriptor = resolver.discover_profiles(profile_key)[0]
            resolved = resolver.load_selection(profile_key, descriptor.profile_id)
            self.assertEqual(profile_id, resolved.key.profile_id)
            self.assertIn("Spacing=2.0", SubtitleStyleBuilder().build(resolved.render_style))

    def _assert_invalid(self, field, value, message):
        with self.assertRaisesRegex((TypeError, ValueError), message):
            self._load(**{field: value})

    def _load(self, **changes):
        style = deepcopy(self.BASE_STYLE)
        style.update(changes)
        return self.loader.load_render_style(style)

    @staticmethod
    def _source_standard(component):
        path = Path(
            f"config/profiles/{component}/instagram/estandar/"
            f"subtitulo_{component}_instagram_linea_unica.json"
        )
        return json.loads(path.read_text(encoding="utf-8"))


@unittest.skipUnless(
    shutil.which("ffmpeg"),
    "FFmpeg es obligatorio para la prueba real ASS/libass.",
)
class SubtitleTypographyPhaseERealFfmpegTest(unittest.TestCase):

    def test_ffmpeg_libass_accepts_the_extended_force_style(self):
        style = {
            **SubtitleTypographyPhaseETest.EXTENDED_STYLE,
            "margin_l": 25,
            "margin_r": 25,
            "spacing": 1.5,
        }
        force_style = SubtitleStyleBuilder().build(style)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subtitle_path = root / "captions.srt"
            output_path = root / "rendered.mp4"
            subtitle_path.write_text(
                "1\n00:00:00,000 --> 00:00:00,800\nTexto de prueba\n",
                encoding="utf-8",
            )
            escaped_subtitle = self._escape_filter_path(subtitle_path)
            escaped_fonts = self._escape_filter_path(Path("assets/fonts"))
            filter_value = (
                f"subtitles='{escaped_subtitle}':fontsdir='{escaped_fonts}':"
                f"force_style='{force_style}'"
            )
            result = subprocess.run(
                [
                    "ffmpeg", "-y", "-f", "lavfi", "-i",
                    "color=c=black:s=320x180:r=25:d=1",
                    "-vf", filter_value,
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    str(output_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue(output_path.is_file())
            self.assertGreater(output_path.stat().st_size, 0)

    @staticmethod
    def _escape_filter_path(path):
        return (
            Path(path).resolve().as_posix()
            .replace(":", r"\:")
            .replace("'", r"\'")
        )


if __name__ == "__main__":
    unittest.main()
