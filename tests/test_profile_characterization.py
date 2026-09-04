import hashlib
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.start import _load_video_component_profile
from app.modules.video.video_config import VideoConfigLoader
from app.shared.config_manager import ConfigManager
from app.shared.profile_identity import (
    ProfileComponent,
    ProfileKey,
    ProfilePlatform,
)
from app.shared.profile_resolver import ProfileResolver


class ProfileCharacterizationTest(unittest.TestCase):

    PROFILE_HASHES = {
        "config/profiles/guion/instagram.json": (
            "273c5e47d57e1021ee29618881dcaf0bb71238e46142879cb53ac6029f0d4411"
        ),
        "config/profiles/guion/youtube.json": (
            "4c773e16bef9309462bdf89c6453795b6ddb5760a505818a5c3b6da393bbaa35"
        ),
        "config/profiles/instagram/modo_conciencia.json": (
            "273c5e47d57e1021ee29618881dcaf0bb71238e46142879cb53ac6029f0d4411"
        ),
        "config/profiles/youtube/modo_conciencia.json": (
            "4c773e16bef9309462bdf89c6453795b6ddb5760a505818a5c3b6da393bbaa35"
        ),
        "config/profiles/diseno/imagen/instagram.json": (
            "68982a37116f836efe30129472656ae3aaf069f4fd83be87ecdb32777fb35558"
        ),
        "config/profiles/diseno/imagen/youtube.json": (
            "b14ec85306a55359ba02d2a189a27750028fd66eb89f42d542df9f8cb5b4bb7c"
        ),
        "config/profiles/diseno/video/instagram.json": (
            "1a03449be72a33a4844bc7cacdb24a7e8575b5e9ae9e23fabfb51424be81ac80"
        ),
        "config/profiles/diseno/video/youtube.json": (
            "60cc016d66cd9d40f65bfde84ae6930916a83eed2faa51cb3c5389786efb8dc4"
        ),
        "config/profiles/video/instagram.json": (
            "aa76732c4933d3f4b468f42f5ff168298e019dfb42e5f62c1a3fe61eeca392c7"
        ),
        "config/profiles/video/youtube.json": (
            "b5a159a407de677ed7af082a2a93f2bc00835d52e3e53fd3e135af01018bb76d"
        ),
        "config/subtitle_configs/single_line.json": (
            "2804e5bf5718b6412f74afb0e16b378081857364bd2cfaa3fa8104e7bac5203f"
        ),
        "config/subtitle_configs/word_by_word.json": (
            "039fd25387dcc416c6f785edb7a9f781f064eb979d0158b58e9f21aa7089dcf8"
        ),
    }

    PLATFORM_EXPECTATIONS = {
        ProfilePlatform.INSTAGRAM: {
            "format": "vertical",
            "resolution": "1080x1920",
            "width": 1080,
            "height": 1920,
            "fps": 30,
            "subtitle_config": "word_by_word",
            "subtitle_font": "unisans",
            "subtitle_size": 14,
            "subtitle_margin": 55,
            "subtitle_offset": -0.06,
            "seconds_per_image": 10,
        },
        ProfilePlatform.YOUTUBE: {
            "format": "horizontal",
            "resolution": "1920x1080",
            "width": 1920,
            "height": 1080,
            "fps": 30,
            "subtitle_config": "single_line",
            "subtitle_font": "gotham",
            "subtitle_size": 16,
            "subtitle_margin": 25,
            "subtitle_offset": 0.0,
            "seconds_per_image": 15,
        },
    }

    def setUp(self):
        self.resolver = ProfileResolver()

    def test_all_current_profile_files_keep_semantic_hashes(self):
        for path, expected_hash in self.PROFILE_HASHES.items():
            with self.subTest(path=path):
                data = self._load(Path(path))
                self.assertEqual(
                    expected_hash,
                    self._semantic_hash(data)
                )

    def test_guion_image_and_video_profiles_keep_effective_behavior(self):
        for component in ProfileComponent:
            for platform, expected in self.PLATFORM_EXPECTATIONS.items():
                with self.subTest(
                    component=component.value,
                    platform=platform.value
                ):
                    profile_key = ProfileKey.for_component(
                        component,
                        platform
                    )
                    profile = self.resolver.load(
                        profile_key
                    )
                    video_style = profile["video_style"]
                    subtitles = video_style["subtitles"]

                    self.assertEqual(
                        platform.value,
                        profile["platform"]
                    )
                    self.assertEqual(
                        expected["format"],
                        profile["format"]
                    )
                    self.assertEqual(
                        expected["resolution"],
                        profile["resolution"]
                    )
                    self.assertEqual(
                        expected["width"],
                        video_style["width"]
                    )
                    self.assertEqual(
                        expected["height"],
                        video_style["height"]
                    )
                    self.assertEqual(
                        expected["fps"],
                        video_style["fps"]
                    )
                    self.assertEqual(
                        expected["subtitle_config"],
                        profile["subtitle_config"]
                    )
                    self.assertEqual(
                        expected["subtitle_font"],
                        subtitles["font"]
                    )
                    self.assertEqual(
                        expected["subtitle_size"],
                        subtitles["font_size"]
                    )
                    self.assertEqual(
                        expected["subtitle_margin"],
                        subtitles["margin_v"]
                    )
                    self.assertEqual(
                        expected["subtitle_offset"],
                        subtitles["offset"]
                    )
                    self.assertEqual(
                        expected["seconds_per_image"],
                        video_style["storyboard"][
                            "seconds_per_image"
                        ]
                    )
                    self.assertEqual(
                        "scene",
                        video_style["overlays"][
                            "repeat_mode"
                        ]
                    )
                    self.assertEqual(
                        "slow",
                        profile["video"]["preset"]
                    )
                    self.assertEqual(
                        16,
                        profile["video"]["crf"]
                    )

    def test_design_routes_keep_legacy_profiles_and_dimensions(self):
        for target_component in (
            ProfileComponent.IMAGEN,
            ProfileComponent.VIDEO,
        ):
            for platform, expected in self.PLATFORM_EXPECTATIONS.items():
                with self.subTest(
                    target=target_component.value,
                    platform=platform.value
                ):
                    path = self.resolver.resolve_design(
                        target_component,
                        platform
                    )
                    profile = self.resolver.load_design(
                        target_component,
                        platform
                    )

                    self.assertEqual(
                        Path(
                            "config/profiles/diseno"
                        ) / target_component.value / (
                            f"{platform.value}.json"
                        ),
                        path
                    )
                    self.assertEqual(
                        platform.value,
                        profile["platform"]
                    )
                    self.assertEqual(
                        expected["format"],
                        profile["format"]
                    )
                    self.assertEqual(
                        expected["resolution"],
                        profile["resolution"]
                    )
                    self.assertEqual(
                        expected["width"],
                        profile["video_style"]["width"]
                    )
                    self.assertEqual(
                        expected["height"],
                        profile["video_style"]["height"]
                    )

    def test_video_wan_profiles_keep_current_parameters(self):
        expected_by_platform = {
            ProfilePlatform.INSTAGRAM: (
                (448, 800),
                (1080, 1920),
            ),
            ProfilePlatform.YOUTUBE: (
                (800, 448),
                (1920, 1080),
            ),
        }

        for platform, dimensions in expected_by_platform.items():
            with self.subTest(platform=platform.value):
                profile_key = ProfileKey.for_component(
                    ProfileComponent.VIDEO,
                    platform
                )
                path = self.resolver.resolve_video_component(
                    profile_key
                )
                profile = self.resolver.load_video_component(
                    profile_key
                )
                video = profile["video_component"]

                self.assertEqual(
                    Path("config/profiles/video")
                    / platform.value
                    / f"wan_i2v_{platform.value}.json",
                    path
                )
                self.assertEqual(
                    dimensions[0],
                    (
                        video["generation"]["width"],
                        video["generation"]["height"],
                    )
                )
                self.assertEqual(
                    dimensions[1],
                    (
                        video["target"]["width"],
                        video["target"]["height"],
                    )
                )
                self.assertEqual(49, video["frames"])
                self.assertEqual(12, video["fps"])
                self.assertEqual(20, video["sampling"]["steps"])
                self.assertEqual(5.0, video["sampling"]["cfg"])
                self.assertEqual(
                    "uni_pc",
                    video["sampling"]["sampler"]
                )
                self.assertEqual(
                    "simple",
                    video["sampling"]["scheduler"]
                )

    def test_subtitle_configuration_remains_effectively_split(self):
        for platform, expected in self.PLATFORM_EXPECTATIONS.items():
            with self.subTest(platform=platform.value):
                profile_key = ProfileKey.for_component(
                    ProfileComponent.VIDEO,
                    platform
                )
                environment = self._identity_environment(
                    profile_key,
                    self.resolver.resolve(profile_key)
                )
                environment["MC_SUBTITLE_CONFIG"] = ""

                with patch.dict(
                    os.environ,
                    environment,
                    clear=True
                ):
                    subtitle_config = (
                        ConfigManager()
                        .get_subtitle_config()
                    )

                expected_path = Path(
                    "config/subtitle_configs"
                ) / f"{expected['subtitle_config']}.json"
                self.assertEqual(
                    self._load(expected_path),
                    subtitle_config
                )

    def test_structured_identity_controls_wan_profile_resolution(self):
        instagram_key = ProfileKey.for_component(
            ProfileComponent.VIDEO,
            ProfilePlatform.INSTAGRAM
        )
        visual_profile = dict(
            self.resolver.load(instagram_key)
        )
        visual_profile["platform"] = "youtube"

        self.assertEqual(
            self.resolver.load_video_component(instagram_key),
            _load_video_component_profile(
                visual_profile,
                profile_key=instagram_key
            )
        )

    def test_runtime_objects_are_equal_for_legacy_and_identity_loading(self):
        for platform in ProfilePlatform:
            with self.subTest(platform=platform.value):
                profile_key = ProfileKey.for_component(
                    ProfileComponent.VIDEO,
                    platform
                )
                official_path = self.resolver.resolve(
                    profile_key
                )
                legacy_path = (
                    Path("config/profiles")
                    / platform.value
                    / "modo_conciencia.json"
                )

                with patch.dict(
                    os.environ,
                    self._legacy_environment(legacy_path),
                    clear=True
                ):
                    legacy_profile = (
                        ConfigManager()
                        .get_profile_config()
                    )
                    legacy_video = VideoConfigLoader().load()

                with patch.dict(
                    os.environ,
                    self._identity_environment(
                        profile_key,
                        official_path
                    ),
                    clear=True
                ):
                    identity_profile = (
                        ConfigManager()
                        .get_profile_config()
                    )
                    identity_video = VideoConfigLoader().load()

                self.assertEqual(
                    legacy_profile,
                    identity_profile
                )
                self.assertEqual(
                    legacy_video,
                    identity_video
                )
                self.assertEqual(
                    self._load(
                        Path("config/profiles/video")
                        / f"{platform.value}.json"
                    ),
                    self.resolver.load_video_component(
                        profile_key
                    )
                )
                self.assertEqual(
                    self.resolver.load_video_component(profile_key),
                    _load_video_component_profile(
                        identity_profile,
                        profile_key=profile_key
                    )
                )

    def _identity_environment(
        self,
        profile_key,
        path
    ):
        return {
            "MC_PROFILE_PATH": str(path),
            "MC_PROFILE_COMPONENT": profile_key.component.value,
            "MC_PROFILE_PLATFORM": profile_key.platform.value,
            "MC_PROFILE_ID": profile_key.profile_id,
        }

    def _legacy_environment(
        self,
        path
    ):
        return {
            "MC_PROFILE_PATH": str(path),
            "MC_PROFILE_COMPONENT": "",
            "MC_PROFILE_PLATFORM": "",
            "MC_PROFILE_ID": "",
        }

    def _load(
        self,
        path
    ):
        return json.loads(
            Path(path).read_text(
                encoding="utf-8"
            )
        )

    def _semantic_hash(
        self,
        data
    ):
        normalized = json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False
        ).encode("utf-8")
        return hashlib.sha256(
            normalized
        ).hexdigest()


if __name__ == "__main__":
    unittest.main()
