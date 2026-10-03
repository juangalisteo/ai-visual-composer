import json
import shutil
import tempfile
import unittest
from pathlib import Path

from app.shared.profile_identity import (
    OperationalProfileKey,
    ProfileComponent,
)
from app.shared.profile_resolver import ProfileResolver


class ProfileTreePhase2Test(unittest.TestCase):

    COMPONENT_PATHS = {
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
        "studio_instagram": Path(
            "config/profiles/studio/instagram/"
            "perfil_studio_instagram.json"
        ),
        "studio_youtube": Path(
            "config/profiles/studio/youtube/"
            "perfil_studio_youtube.json"
        ),
    }

    WAN_PATHS = {
        "instagram": Path(
            "config/profiles/video/instagram/"
            "wan_i2v_instagram.json"
        ),
        "youtube": Path(
            "config/profiles/video/youtube/"
            "wan_i2v_youtube.json"
        ),
    }

    BASE_IDENTITIES = {
        "guion_instagram": ("guion", "instagram", "guion_instagram"),
        "guion_youtube": ("guion", "youtube", "guion_youtube"),
        "imagen_instagram": ("imagen", "instagram", "imagen_instagram"),
        "imagen_youtube": ("imagen", "youtube", "imagen_youtube"),
        "video_instagram": ("video", "instagram", "video_instagram"),
        "video_youtube": ("video", "youtube", "video_youtube"),
        "studio_instagram": ("studio", "instagram", "studio_instagram"),
        "studio_youtube": ("studio", "youtube", "studio_youtube"),
    }

    REMOVED_LEGACY_PATHS = (
        Path("config/profiles/guion/instagram.json"),
        Path("config/profiles/guion/youtube.json"),
        Path("config/profiles/video/instagram.json"),
        Path("config/profiles/video/youtube.json"),
        Path("config/profiles/instagram/modo_conciencia.json"),
        Path("config/profiles/youtube/modo_conciencia.json"),
        Path("config/profiles/diseno"),
    )

    def test_component_tree_contains_distinct_regular_files(self):
        paths = tuple(self.COMPONENT_PATHS.values()) + tuple(
            self.WAN_PATHS.values()
        )

        self.assertEqual(len(paths), len(set(paths)))
        for path in paths:
            with self.subTest(path=path):
                self.assertTrue(path.is_file())
                self.assertFalse(path.is_symlink())

    def test_removed_legacy_profile_paths_do_not_exist(self):
        for path in self.REMOVED_LEGACY_PATHS:
            with self.subTest(path=path):
                self.assertFalse(path.exists())

    def test_base_profiles_declare_their_structural_identity(self):
        for profile_id, expected in self.BASE_IDENTITIES.items():
            with self.subTest(profile_id=profile_id):
                path = self.COMPONENT_PATHS[profile_id]
                data = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(expected[0], data["component"])
                self.assertEqual(expected[1], data["platform"])
                self.assertEqual(expected[2], data["profile_id"])

    def test_component_profiles_can_diverge_independently(self):
        image_source = self.COMPONENT_PATHS["imagen_instagram"]
        video_source = self.COMPONENT_PATHS["video_instagram"]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image_copy = root / "image.json"
            video_copy = root / "video.json"
            shutil.copyfile(image_source, image_copy)
            shutil.copyfile(video_source, video_copy)
            original_video = video_copy.read_bytes()

            image_copy.write_bytes(image_copy.read_bytes() + b"\n")

            self.assertNotEqual(image_copy.read_bytes(), video_copy.read_bytes())
            self.assertEqual(original_video, video_copy.read_bytes())

    def test_platform_profiles_can_diverge_independently(self):
        instagram_source = self.COMPONENT_PATHS["imagen_instagram"]
        youtube_source = self.COMPONENT_PATHS["imagen_youtube"]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            instagram_copy = root / "instagram.json"
            youtube_copy = root / "youtube.json"
            shutil.copyfile(instagram_source, instagram_copy)
            shutil.copyfile(youtube_source, youtube_copy)
            original_youtube = youtube_copy.read_bytes()

            instagram_copy.write_bytes(instagram_copy.read_bytes() + b"\n")

            self.assertNotEqual(
                instagram_copy.read_bytes(),
                youtube_copy.read_bytes(),
            )
            self.assertEqual(original_youtube, youtube_copy.read_bytes())

    def test_profile_resolver_uses_component_scoped_paths(self):
        resolver = ProfileResolver()

        for component in ProfileComponent:
            for platform in ("instagram", "youtube"):
                profile_key = OperationalProfileKey(
                    component,
                    platform,
                    f"{component.value}_{platform}",
                )
                with self.subTest(profile_id=profile_key.profile_id):
                    self.assertEqual(
                        self.COMPONENT_PATHS[profile_key.profile_id],
                        resolver.resolve_operational(profile_key),
                    )

    def test_profile_resolver_uses_component_scoped_wan_paths(self):
        resolver = ProfileResolver()

        for platform, expected_path in self.WAN_PATHS.items():
            profile_key = OperationalProfileKey(
                ProfileComponent.VIDEO,
                platform,
                f"video_{platform}",
            )
            with self.subTest(platform=platform):
                self.assertEqual(
                    expected_path,
                    resolver.resolve_video_component(profile_key),
                )

    def test_unimplemented_video_srt_profile_family_does_not_exist(self):
        self.assertFalse(Path("config/profiles/video_srt").exists())


if __name__ == "__main__":
    unittest.main()
