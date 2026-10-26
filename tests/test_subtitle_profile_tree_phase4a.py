import json
import shutil
import tempfile
import unittest
from pathlib import Path

from app.modules.video.config.loaders.subtitle_loader import (
    SubtitleConfigLoader,
)
from app.shared.config_manager import ConfigManager
from app.shared.subtitle_profile_identity import SubtitleProfileKey


class SubtitleProfileTreePhase4ATest(unittest.TestCase):

    COMPONENTS = ("guion", "imagen", "video")
    FORMATS = ("horizontal", "vertical")
    MODES = {
        "linea_unica": "single_line",
        "palabra_por_palabra": "word_by_word",
    }
    MAIN_PROFILES = {
        ("guion", "vertical"): Path(
            "config/profiles/guion/vertical/perfil_guion_vertical.json"
        ),
        ("guion", "horizontal"): Path(
            "config/profiles/guion/horizontal/perfil_guion_horizontal.json"
        ),
        ("imagen", "vertical"): Path(
            "config/profiles/imagen/vertical/perfil_imagen_vertical.json"
        ),
        ("imagen", "horizontal"): Path(
            "config/profiles/imagen/horizontal/perfil_imagen_horizontal.json"
        ),
        ("video", "vertical"): Path(
            "config/profiles/video/vertical/perfil_video_vertical.json"
        ),
        ("video", "horizontal"): Path(
            "config/profiles/video/horizontal/perfil_video_horizontal.json"
        ),
    }
    EXPECTED_CUE_POLICIES = {
        "single_line": {
            "mode": "single_line",
            "max_chars_per_line": 60,
            "min_duration": 1.0,
            "max_duration": 3.0,
            "significant_gap_threshold": 0.35,
            "text_case": "original",
            "punctuation": {
                "remove_commas": False,
                "remove_periods": False,
                "remove_colons": False,
                "remove_semicolons": False,
                "remove_question_marks": False,
                "remove_exclamation_marks": False,
                "remove_ellipsis": False,
                "remove_hyphens": False,
                "remove_em_dashes": False,
                "remove_double_quotes": False,
                "remove_single_quotes": False,
                "remove_parentheses": False,
            },
        },
        "word_by_word": {
            "mode": "word_by_word",
            "min_duration": 0.30,
            "max_duration": 1.20,
            "significant_gap_threshold": 0.35,
            "micro_cues": {
                "enabled": True,
                "min_frames": 1,
                "min_display_seconds": 0.05,
                "merge_preference": "next",
            },
            "text_case": "original",
            "punctuation": {
                "remove_commas": True,
                "remove_periods": True,
                "remove_colons": False,
                "remove_semicolons": False,
                "remove_question_marks": False,
                "remove_exclamation_marks": False,
                "remove_ellipsis": False,
                "remove_hyphens": False,
                "remove_em_dashes": False,
                "remove_double_quotes": False,
                "remove_single_quotes": False,
                "remove_parentheses": False,
            },
        },
    }
    EXPECTED_RENDER_STYLES = {
        "vertical": {
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
        },
        "horizontal": {
            "font": "gotham",
            "font_size": 16,
            "bold": False,
            "primary_colour": "&H00FFFFFF",
            "outline_colour": "&H00000000",
            "back_colour": "&H00000000",
            "border_style": 1,
            "outline": 0,
            "shadow": 1,
            "alignment": 2,
            "margin_v": 25,
            "offset": 0.0,
        },
    }

    # F5 (H7): the vertical format fits fewer characters per line.
    EXPECTED_MAX_CHARS_PER_LINE = {"vertical": 20, "horizontal": 60}

    def test_tree_contains_expected_profiles(self):
        actual = {
            path
            for component in self.COMPONENTS
            for path in Path(
                "config/profiles"
            ).glob(f"{component}/*/estandar/subtitulos/*.json")
        }

        self.assertTrue(self._expected_paths().issubset(actual))
        self.assertGreaterEqual(len(actual), len(self._expected_paths()))
        self.assertFalse(Path("config/profiles/video_srt").exists())

    def test_profiles_have_valid_unique_canonical_identity(self):
        profile_ids = set()

        for component, profile_format, suffix, mode, path in self._cases():
            with self.subTest(path=path):
                profile = self._load(path)
                expected_id = f"subtitulo_{component}_{profile_format}_{suffix}"

                self.assertEqual(
                    {
                    "component",
                    "format",
                    "family",
                    "profile_id",
                    "display_name",
                    "cue_policy",
                    "render_style",
                    },
                    set(profile),
                )
                self.assertEqual(component, profile["component"])
                self.assertEqual(profile_format, profile["format"])
                self.assertEqual("estandar", profile["family"])
                self.assertEqual(expected_id, profile["profile_id"])
                self.assertEqual(
                    self._display_name_for(profile_format, mode),
                    profile["display_name"],
                )
                self.assertEqual(mode, profile["cue_policy"]["mode"])
                self.assertNotIn(expected_id, profile_ids)
                profile_ids.add(expected_id)

        self.assertEqual(len(self._expected_paths()), len(profile_ids))

    def test_profiles_preserve_the_final_cue_and_render_contract(self):
        for _, profile_format, _, mode, path in self._cases():
            with self.subTest(path=path):
                profile = self._load(path)
                expected_cue_policy = dict(self.EXPECTED_CUE_POLICIES[mode])
                if "max_chars_per_line" in expected_cue_policy:
                    expected_cue_policy["max_chars_per_line"] = (
                        self.EXPECTED_MAX_CHARS_PER_LINE[profile_format]
                    )
                self.assertEqual(
                    expected_cue_policy,
                    profile["cue_policy"],
                )
                self.assertEqual(
                    self.EXPECTED_RENDER_STYLES[profile_format],
                    profile["render_style"],
                )

    def test_profiles_are_independent_regular_files(self):
        paths = sorted(self._expected_paths())
        source_bytes = {path: path.read_bytes() for path in paths}

        self.assertEqual(len(paths), len({path.resolve() for path in paths}))
        for path in paths:
            with self.subTest(path=path):
                self.assertTrue(path.is_file())
                self.assertFalse(path.is_symlink())

        with tempfile.TemporaryDirectory() as directory:
            copies = []
            for path in paths:
                destination = Path(directory) / path.name
                shutil.copyfile(path, destination)
                copies.append(destination)

            original_bytes = {path: path.read_bytes() for path in copies}
            first = copies[0]
            first.write_bytes(first.read_bytes() + b"\n")

            for path in copies[1:]:
                self.assertEqual(original_bytes[path], path.read_bytes())
            for source in paths:
                self.assertEqual(source_bytes[source], source.read_bytes())

    def test_removed_subtitle_legacy_sources_do_not_exist(self):
        self.assertFalse(Path("config/subtitle_configs").exists())
        for path in self.MAIN_PROFILES.values():
            with self.subTest(path=path):
                self.assertNotIn(
                    "subtitles",
                    self._load(path)["video_style"],
                )

    def test_official_runtime_loads_new_cue_profiles(self):
        for component, profile_format, _, _, path in self._cases():
            subtitle_key = SubtitleProfileKey(
                component,
                profile_format,
                self._load(path)["profile_id"],
                "estandar",
            )

            with self.subTest(path=path):
                loaded = ConfigManager().get_subtitle_profile_by_key(
                    subtitle_key
                )

            self.assertEqual(path, loaded.path)
            self.assertEqual(self._load(path)["cue_policy"], loaded.cue_policy)

    def test_render_loader_accepts_new_profile_render_style(self):
        loader = SubtitleConfigLoader()

        for component, profile_format, _, _, path in self._cases():
            with self.subTest(component=component, profile_format=profile_format):
                render_style = self._load(path)["render_style"]
                loaded = loader.load_render_style(render_style)

                self.assertEqual(render_style["font"], loaded.font)
                self.assertEqual(render_style["font_size"], loaded.font_size)
                self.assertEqual(render_style["margin_v"], loaded.margin_v)
                self.assertEqual(render_style["offset"], loaded.offset)

    def _cases(self):
        for component in self.COMPONENTS:
            for profile_format in self.FORMATS:
                for suffix, mode in self.MODES.items():
                    yield (
                        component,
                        profile_format,
                        suffix,
                        mode,
                        Path("config/profiles")
                        / component
                        / profile_format
                        / "estandar" / "subtitulos"
                        / f"subtitulo_{component}_{profile_format}_{suffix}.json",
                    )

    def _expected_paths(self):
        return {path for _, _, _, _, path in self._cases()}

    @staticmethod
    def _display_name_for(profile_format, mode):
        if mode == "single_line":
            return "Línea única"
        return "Palabra única" if profile_format == "vertical" else "Palabra por palabra"

    def _load(self, path):
        return json.loads(Path(path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
