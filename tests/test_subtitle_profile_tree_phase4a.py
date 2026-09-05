import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.modules.video.config.loaders.subtitle_loader import (
    SubtitleConfigLoader,
)
from app.shared.config_manager import ConfigManager
from app.shared.profile_identity import ProfileKey


class SubtitleProfileTreePhase4ATest(unittest.TestCase):

    COMPONENTS = ("guion", "imagen", "video")
    PLATFORMS = ("instagram", "youtube")
    STYLES = {
        "linea_unica": "single_line",
        "palabra_por_palabra": "word_by_word",
    }
    MAIN_PROFILES = {
        ("guion", "instagram"): Path(
            "config/profiles/guion/instagram/perfil_guion_instagram.json"
        ),
        ("guion", "youtube"): Path(
            "config/profiles/guion/youtube/perfil_guion_youtube.json"
        ),
        ("imagen", "instagram"): Path(
            "config/profiles/imagen/instagram/perfil_imagen_instagram.json"
        ),
        ("imagen", "youtube"): Path(
            "config/profiles/imagen/youtube/perfil_imagen_youtube.json"
        ),
        ("video", "instagram"): Path(
            "config/profiles/video/instagram/perfil_video_instagram.json"
        ),
        ("video", "youtube"): Path(
            "config/profiles/video/youtube/perfil_video_youtube.json"
        ),
    }
    EXPECTED_CUE_POLICIES = {
        "single_line": {
            "mode": "single_line",
            "max_chars_per_line": 60,
            "min_duration": 1.0,
            "max_duration": 3.0,
            "significant_gap_threshold": 0.35,
            "split_on_punctuation": True,
            "avoid_orphan_words": True,
            "merge_short_chunks": True,
            "balance_duration": True,
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
            "uppercase": False,
            "remove_extra_commas": True,
        },
    }
    EXPECTED_RENDER_STYLES = {
        "instagram": {
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
        "youtube": {
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

    def test_tree_contains_exactly_twelve_expected_profiles(self):
        actual = {
            path
            for component in self.COMPONENTS
            for path in Path(
                "config/profiles"
            ).glob(f"{component}/*/subtitulos/*.json")
        }

        self.assertEqual(self._expected_paths(), actual)
        self.assertEqual(12, len(actual))
        self.assertFalse(Path("config/profiles/video_srt").exists())

    def test_profiles_have_valid_unique_canonical_identity(self):
        profile_ids = set()

        for component, platform, suffix, style, path in self._cases():
            with self.subTest(path=path):
                profile = self._load(path)
                expected_id = f"subtitulo_{component}_{platform}_{suffix}"

                self.assertEqual(
                    {
                        "component",
                        "platform",
                        "profile_id",
                        "style",
                        "cue_policy",
                        "render_style",
                    },
                    set(profile),
                )
                self.assertEqual(component, profile["component"])
                self.assertEqual(platform, profile["platform"])
                self.assertEqual(expected_id, profile["profile_id"])
                self.assertEqual(style, profile["style"])
                self.assertNotIn(expected_id, profile_ids)
                profile_ids.add(expected_id)

        self.assertEqual(12, len(profile_ids))

    def test_profiles_preserve_the_final_cue_and_render_contract(self):
        for _, platform, _, style, path in self._cases():
            with self.subTest(path=path):
                profile = self._load(path)
                self.assertEqual(
                    self.EXPECTED_CUE_POLICIES[style],
                    profile["cue_policy"],
                )
                self.assertEqual(
                    self.EXPECTED_RENDER_STYLES[platform],
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
        for component, platform, _, style, path in self._cases():
            profile_key = ProfileKey.for_component(component, platform)
            environment = {
                "MC_PROFILE_COMPONENT": component,
                "MC_PROFILE_PLATFORM": platform,
                "MC_PROFILE_ID": profile_key.profile_id,
            }

            with self.subTest(path=path), patch.dict(
                os.environ,
                environment,
                clear=True,
            ):
                loaded = ConfigManager().get_subtitle_profile(style)

            self.assertEqual(path, loaded.path)
            self.assertEqual(self._load(path)["cue_policy"], loaded.cue_policy)

    def test_render_loader_accepts_new_profile_render_style(self):
        loader = SubtitleConfigLoader()

        for component, platform, _, _, path in self._cases():
            with self.subTest(component=component, platform=platform):
                render_style = self._load(path)["render_style"]
                loaded = loader.load_render_style(render_style)

                self.assertEqual(render_style["font"], loaded.font)
                self.assertEqual(render_style["font_size"], loaded.font_size)
                self.assertEqual(render_style["margin_v"], loaded.margin_v)
                self.assertEqual(render_style["offset"], loaded.offset)

    def _cases(self):
        for component in self.COMPONENTS:
            for platform in self.PLATFORMS:
                for suffix, style in self.STYLES.items():
                    yield (
                        component,
                        platform,
                        suffix,
                        style,
                        Path("config/profiles")
                        / component
                        / platform
                        / "subtitulos"
                        / f"subtitulo_{component}_{platform}_{suffix}.json",
                    )

    def _expected_paths(self):
        return {path for _, _, _, _, path in self._cases()}

    def _load(self, path):
        return json.loads(Path(path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
