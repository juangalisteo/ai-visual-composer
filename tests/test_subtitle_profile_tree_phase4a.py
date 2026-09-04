import hashlib
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
            "config/profiles/guion/instagram/"
            "perfil_guion_instagram.json"
        ),
        ("guion", "youtube"): Path(
            "config/profiles/guion/youtube/"
            "perfil_guion_youtube.json"
        ),
        ("imagen", "instagram"): Path(
            "config/profiles/imagen/instagram/"
            "perfil_imagen_instagram.json"
        ),
        ("imagen", "youtube"): Path(
            "config/profiles/imagen/youtube/"
            "perfil_imagen_youtube.json"
        ),
        ("video", "instagram"): Path(
            "config/profiles/video/instagram/"
            "perfil_video_instagram.json"
        ),
        ("video", "youtube"): Path(
            "config/profiles/video/youtube/"
            "perfil_video_youtube.json"
        ),
    }
    CUE_PROFILES = {
        "single_line": Path(
            "config/subtitle_configs/single_line.json"
        ),
        "word_by_word": Path(
            "config/subtitle_configs/word_by_word.json"
        ),
    }
    SOURCE_HASHES = {
        Path("config/subtitle_configs/single_line.json"): (
            "628BEFAF60E6B3E40869E7AD60F56D599462B01D"
            "EACD187DFB16A10ACC50F19A"
        ),
        Path("config/subtitle_configs/word_by_word.json"): (
            "FF7D1826D42E1310EAE215CC6D9AF7486EBAC1FD"
            "F59BD24F6038AED7B643A1E5"
        ),
        Path(
            "config/profiles/guion/instagram/"
            "perfil_guion_instagram.json"
        ): (
            "BA65B13A6C51A0C47FF020FCA59D09D07E5857C"
            "DFC7CF9A3B6B7B75794E7DE2B"
        ),
        Path(
            "config/profiles/guion/youtube/"
            "perfil_guion_youtube.json"
        ): (
            "233B3FF4C76E5572E083F5F2ADEB6BB9728B24A7"
            "468EEA35E6F6917AF93A0135"
        ),
        Path(
            "config/profiles/imagen/instagram/"
            "perfil_imagen_instagram.json"
        ): (
            "BA65B13A6C51A0C47FF020FCA59D09D07E5857C"
            "DFC7CF9A3B6B7B75794E7DE2B"
        ),
        Path(
            "config/profiles/imagen/youtube/"
            "perfil_imagen_youtube.json"
        ): (
            "233B3FF4C76E5572E083F5F2ADEB6BB9728B24A7"
            "468EEA35E6F6917AF93A0135"
        ),
        Path(
            "config/profiles/video/instagram/"
            "perfil_video_instagram.json"
        ): (
            "BA65B13A6C51A0C47FF020FCA59D09D07E5857C"
            "DFC7CF9A3B6B7B75794E7DE2B"
        ),
        Path(
            "config/profiles/video/youtube/"
            "perfil_video_youtube.json"
        ): (
            "233B3FF4C76E5572E083F5F2ADEB6BB9728B24A7"
            "468EEA35E6F6917AF93A0135"
        ),
    }

    def test_tree_contains_exactly_twelve_expected_profiles(self):
        actual = set(
            Path("config/profiles").glob(
                "*/*/subtitulos/*.json"
            )
        )

        self.assertEqual(self._expected_paths(), actual)
        self.assertEqual(12, len(actual))
        self.assertFalse(Path("config/profiles/video_srt").exists())

    def test_profiles_have_valid_unique_canonical_identity(self):
        profile_ids = set()

        for component, platform, suffix, style, path in self._cases():
            with self.subTest(path=path):
                profile = self._load(path)
                expected_id = (
                    f"subtitulo_{component}_{platform}_{suffix}"
                )

                self.assertEqual(
                    {
                        "component",
                        "platform",
                        "profile_id",
                        "style",
                        "cue_policy",
                        "render_style",
                    },
                    set(profile)
                )
                self.assertEqual(component, profile["component"])
                self.assertEqual(platform, profile["platform"])
                self.assertEqual(expected_id, profile["profile_id"])
                self.assertEqual(style, profile["style"])
                self.assertIsInstance(profile["cue_policy"], dict)
                self.assertIsInstance(profile["render_style"], dict)
                self.assertNotIn(expected_id, profile_ids)
                profile_ids.add(expected_id)

        self.assertEqual(12, len(profile_ids))

    def test_all_profiles_equal_their_effective_legacy_configuration(self):
        for component, platform, _, style, path in self._cases():
            with self.subTest(path=path):
                profile = self._load(path)
                main_profile = self._load(
                    self.MAIN_PROFILES[(component, platform)]
                )
                legacy_effective = {
                    "cue_policy": self._load(
                        self.CUE_PROFILES[style]
                    ),
                    "render_style": main_profile[
                        "video_style"
                    ]["subtitles"],
                }

                self.assertEqual(
                    legacy_effective,
                    {
                        "cue_policy": profile["cue_policy"],
                        "render_style": profile["render_style"],
                    }
                )

    def test_profiles_are_independent_regular_files(self):
        paths = sorted(self._expected_paths())
        source_bytes = {
            path: path.read_bytes()
            for path in paths
        }

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

            original_bytes = {
                path: path.read_bytes()
                for path in copies
            }
            first = copies[0]
            first.write_bytes(first.read_bytes() + b"\n")

            for path in copies[1:]:
                self.assertEqual(original_bytes[path], path.read_bytes())
            for source in paths:
                self.assertEqual(
                    source_bytes[source],
                    source.read_bytes()
                )

    def test_legacy_sources_remain_byte_for_byte_intact(self):
        for path, expected_hash in self.SOURCE_HASHES.items():
            with self.subTest(path=path):
                self.assertEqual(
                    expected_hash,
                    hashlib.sha256(path.read_bytes()).hexdigest().upper()
                )

    def test_official_runtime_loads_new_cue_profiles(self):
        for component, platform, _, style, path in self._cases():
            profile_key = ProfileKey.for_component(
                component,
                platform
            )
            environment = {
                "MC_PROFILE_COMPONENT": component,
                "MC_PROFILE_PLATFORM": platform,
                "MC_PROFILE_ID": profile_key.profile_id,
            }

            with self.subTest(path=path), patch.dict(
                os.environ,
                environment,
                clear=True
            ):
                loaded = ConfigManager().get_subtitle_profile(
                    style
                )

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
                        / (
                            f"subtitulo_{component}_{platform}_"
                            f"{suffix}.json"
                        ),
                    )

    def _expected_paths(self):
        return {
            path
            for _, _, _, _, path in self._cases()
        }

    def _load(self, path):
        return json.loads(
            Path(path).read_text(encoding="utf-8")
        )


if __name__ == "__main__":
    unittest.main()
