import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from app.shared.profile_identity import (
    ProfileComponent,
    ProfileKey,
    ProfilePlatform,
)
from app.shared.profile_resolver import ProfileResolver


class ProfileTreePhase2Test(unittest.TestCase):

    COPY_PAIRS = (
        (
            Path("config/profiles/guion/instagram.json"),
            Path(
                "config/profiles/guion/instagram/"
                "perfil_guion_instagram.json"
            ),
            "BA65B13A6C51A0C47FF020FCA59D09D07E5857CDFC7CF9A3B6B7B75794E7DE2B",
        ),
        (
            Path("config/profiles/guion/youtube.json"),
            Path(
                "config/profiles/guion/youtube/"
                "perfil_guion_youtube.json"
            ),
            "233B3FF4C76E5572E083F5F2ADEB6BB9728B24A7468EEA35E6F6917AF93A0135",
        ),
        (
            Path(
                "config/profiles/instagram/"
                "modo_conciencia.json"
            ),
            Path(
                "config/profiles/imagen/instagram/"
                "perfil_imagen_instagram.json"
            ),
            "BA65B13A6C51A0C47FF020FCA59D09D07E5857CDFC7CF9A3B6B7B75794E7DE2B",
        ),
        (
            Path(
                "config/profiles/youtube/"
                "modo_conciencia.json"
            ),
            Path(
                "config/profiles/imagen/youtube/"
                "perfil_imagen_youtube.json"
            ),
            "233B3FF4C76E5572E083F5F2ADEB6BB9728B24A7468EEA35E6F6917AF93A0135",
        ),
        (
            Path(
                "config/profiles/instagram/"
                "modo_conciencia.json"
            ),
            Path(
                "config/profiles/video/instagram/"
                "perfil_video_instagram.json"
            ),
            "BA65B13A6C51A0C47FF020FCA59D09D07E5857CDFC7CF9A3B6B7B75794E7DE2B",
        ),
        (
            Path("config/profiles/video/instagram.json"),
            Path(
                "config/profiles/video/instagram/"
                "wan_i2v_instagram.json"
            ),
            "829C503BF01FAEFE9F7488D28EF128C901689FB8797AC1EF0B6AA6FF87032AF2",
        ),
        (
            Path(
                "config/profiles/youtube/"
                "modo_conciencia.json"
            ),
            Path(
                "config/profiles/video/youtube/"
                "perfil_video_youtube.json"
            ),
            "233B3FF4C76E5572E083F5F2ADEB6BB9728B24A7468EEA35E6F6917AF93A0135",
        ),
        (
            Path("config/profiles/video/youtube.json"),
            Path(
                "config/profiles/video/youtube/"
                "wan_i2v_youtube.json"
            ),
            "E7A08A0371D651D3B5AEACBD4F59F54EE59EC70D6AF1038E9D2921815B88B9B1",
        ),
    )

    NEW_COMPONENT_PATHS = {
        "guion_instagram": Path(
            "config/profiles/guion/instagram/"
            "perfil_guion_instagram.json"
        ),
        "guion_youtube": Path(
            "config/profiles/guion/youtube/"
            "perfil_guion_youtube.json"
        ),
        "imagen_instagram": Path(
            "config/profiles/imagen/instagram/"
            "perfil_imagen_instagram.json"
        ),
        "imagen_youtube": Path(
            "config/profiles/imagen/youtube/"
            "perfil_imagen_youtube.json"
        ),
        "video_instagram": Path(
            "config/profiles/video/instagram/"
            "perfil_video_instagram.json"
        ),
        "video_youtube": Path(
            "config/profiles/video/youtube/"
            "perfil_video_youtube.json"
        ),
    }

    LEGACY_COMPONENT_PATHS = {
        "guion_instagram": Path(
            "config/profiles/guion/instagram.json"
        ),
        "guion_youtube": Path(
            "config/profiles/guion/youtube.json"
        ),
        "imagen_instagram": Path(
            "config/profiles/instagram/modo_conciencia.json"
        ),
        "imagen_youtube": Path(
            "config/profiles/youtube/modo_conciencia.json"
        ),
        "video_instagram": Path(
            "config/profiles/instagram/modo_conciencia.json"
        ),
        "video_youtube": Path(
            "config/profiles/youtube/modo_conciencia.json"
        ),
    }

    def test_new_tree_contains_exact_byte_for_byte_copies(self):
        for source, destination, expected_hash in self.COPY_PAIRS:
            with self.subTest(destination=destination):
                source_bytes = source.read_bytes()
                destination_bytes = destination.read_bytes()

                self.assertEqual(
                    source_bytes,
                    destination_bytes
                )
                self.assertEqual(
                    json.loads(
                        source_bytes.decode("utf-8")
                    ),
                    json.loads(
                        destination_bytes.decode("utf-8")
                    )
                )
                self.assertEqual(
                    expected_hash,
                    self._sha256(source_bytes)
                )
                self.assertEqual(
                    expected_hash,
                    self._sha256(destination_bytes)
                )

    def test_new_profiles_are_distinct_regular_files_without_symlinks(self):
        destinations = tuple(
            destination
            for _, destination, _ in self.COPY_PAIRS
        )

        for source, destination, _ in self.COPY_PAIRS:
            with self.subTest(destination=destination):
                self.assertTrue(source.is_file())
                self.assertTrue(destination.is_file())
                self.assertFalse(source.is_symlink())
                self.assertFalse(destination.is_symlink())
                self.assertNotEqual(
                    source.resolve(),
                    destination.resolve()
                )

        self.assertEqual(
            len(destinations),
            len(set(destinations))
        )
        self.assertNotEqual(
            self.NEW_COMPONENT_PATHS["imagen_instagram"],
            self.NEW_COMPONENT_PATHS["video_instagram"]
        )
        self.assertNotEqual(
            self.NEW_COMPONENT_PATHS["imagen_youtube"],
            self.NEW_COMPONENT_PATHS["video_youtube"]
        )

    def test_temporary_copies_can_diverge_without_cross_component_changes(self):
        image_source = self.NEW_COMPONENT_PATHS[
            "imagen_instagram"
        ]
        video_source = self.NEW_COMPONENT_PATHS[
            "video_instagram"
        ]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image_copy = root / "image.json"
            video_copy = root / "video.json"
            shutil.copyfile(image_source, image_copy)
            shutil.copyfile(video_source, video_copy)
            original_video = video_copy.read_bytes()

            image_copy.write_bytes(
                image_copy.read_bytes() + b"\n"
            )

            self.assertNotEqual(
                image_copy.read_bytes(),
                video_copy.read_bytes()
            )
            self.assertEqual(
                original_video,
                video_copy.read_bytes()
            )

    def test_temporary_copies_can_diverge_without_cross_platform_changes(self):
        instagram_source = self.NEW_COMPONENT_PATHS[
            "imagen_instagram"
        ]
        youtube_source = self.NEW_COMPONENT_PATHS[
            "imagen_youtube"
        ]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            instagram_copy = root / "instagram.json"
            youtube_copy = root / "youtube.json"
            shutil.copyfile(
                instagram_source,
                instagram_copy
            )
            shutil.copyfile(
                youtube_source,
                youtube_copy
            )
            original_youtube = youtube_copy.read_bytes()

            instagram_copy.write_bytes(
                instagram_copy.read_bytes() + b"\n"
            )

            self.assertNotEqual(
                instagram_copy.read_bytes(),
                youtube_copy.read_bytes()
            )
            self.assertEqual(
                original_youtube,
                youtube_copy.read_bytes()
            )

    def test_profile_resolver_still_uses_only_legacy_component_paths(self):
        resolver = ProfileResolver()

        for component in ProfileComponent:
            for platform in ProfilePlatform:
                profile_key = ProfileKey.for_component(
                    component,
                    platform
                )
                with self.subTest(
                    profile_id=profile_key.profile_id
                ):
                    resolved = resolver.resolve(
                        profile_key
                    )
                    self.assertEqual(
                        self.LEGACY_COMPONENT_PATHS[
                            profile_key.profile_id
                        ],
                        resolved
                    )
                    self.assertNotEqual(
                        self.NEW_COMPONENT_PATHS[
                            profile_key.profile_id
                        ],
                        resolved
                    )

    def test_profile_resolver_still_uses_only_legacy_wan_paths(self):
        resolver = ProfileResolver()
        expected_paths = {
            ProfilePlatform.INSTAGRAM: Path(
                "config/profiles/video/instagram.json"
            ),
            ProfilePlatform.YOUTUBE: Path(
                "config/profiles/video/youtube.json"
            ),
        }

        for platform, expected_path in expected_paths.items():
            profile_key = ProfileKey.for_component(
                ProfileComponent.VIDEO,
                platform
            )
            with self.subTest(platform=platform.value):
                resolved = resolver.resolve_video_component(
                    profile_key
                )
                self.assertEqual(
                    expected_path,
                    resolved
                )
                self.assertNotEqual(
                    Path(
                        "config/profiles/video"
                    ) / platform.value / (
                        f"wan_i2v_{platform.value}.json"
                    ),
                    resolved
                )

    def test_phase2_does_not_create_future_profile_families(self):
        self.assertFalse(
            Path("config/profiles/video_srt").exists()
        )
        for root in (
            Path("config/profiles/guion"),
            Path("config/profiles/imagen"),
            Path("config/profiles/video"),
        ):
            for platform in ProfilePlatform:
                self.assertFalse(
                    (
                        root
                        / platform.value
                        / "subtitulos"
                    ).exists()
                )

    def _sha256(
        self,
        content
    ):
        return hashlib.sha256(
            content
        ).hexdigest().upper()


if __name__ == "__main__":
    unittest.main()
