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
        "guion_vertical": Path(
            "config/profiles/guion/vertical/"
            "perfil_guion_vertical.json"
        ),
        "guion_horizontal": Path(
            "config/profiles/guion/horizontal/"
            "perfil_guion_horizontal.json"
        ),
        "imagen_vertical": Path(
            "config/profiles/imagen/vertical/"
            "perfil_imagen_vertical.json"
        ),
        "imagen_horizontal": Path(
            "config/profiles/imagen/horizontal/"
            "perfil_imagen_horizontal.json"
        ),
        "video_vertical": Path(
            "config/profiles/video/vertical/"
            "perfil_video_vertical.json"
        ),
        "video_horizontal": Path(
            "config/profiles/video/horizontal/"
            "perfil_video_horizontal.json"
        ),
        "studio_vertical": Path(
            "config/profiles/studio/vertical/"
            "perfil_studio_vertical.json"
        ),
        "studio_horizontal": Path(
            "config/profiles/studio/horizontal/"
            "perfil_studio_horizontal.json"
        ),
    }

    WAN_PATHS = {
        "vertical": Path(
            "config/profiles/video/vertical/"
            "wan_i2v_vertical.json"
        ),
        "horizontal": Path(
            "config/profiles/video/horizontal/"
            "wan_i2v_horizontal.json"
        ),
    }

    BASE_IDENTITIES = {
        "guion_vertical": ("guion", "vertical", "guion_vertical"),
        "guion_horizontal": ("guion", "horizontal", "guion_horizontal"),
        "imagen_vertical": ("imagen", "vertical", "imagen_vertical"),
        "imagen_horizontal": ("imagen", "horizontal", "imagen_horizontal"),
        "video_vertical": ("video", "vertical", "video_vertical"),
        "video_horizontal": ("video", "horizontal", "video_horizontal"),
        "studio_vertical": ("studio", "vertical", "studio_vertical"),
        "studio_horizontal": ("studio", "horizontal", "studio_horizontal"),
    }

    REMOVED_LEGACY_PATHS = (
        Path("config/profiles/guion/vertical.json"),
        Path("config/profiles/guion/horizontal.json"),
        Path("config/profiles/video/vertical.json"),
        Path("config/profiles/video/horizontal.json"),
        Path("config/profiles/vertical/modo_conciencia.json"),
        Path("config/profiles/horizontal/modo_conciencia.json"),
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
        image_source = self.COMPONENT_PATHS["imagen_vertical"]
        video_source = self.COMPONENT_PATHS["video_vertical"]

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
        vertical_source = self.COMPONENT_PATHS["imagen_vertical"]
        horizontal_source = self.COMPONENT_PATHS["imagen_horizontal"]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vertical_copy = root / "vertical.json"
            horizontal_copy = root / "horizontal.json"
            shutil.copyfile(vertical_source, vertical_copy)
            shutil.copyfile(horizontal_source, horizontal_copy)
            original_horizontal = horizontal_copy.read_bytes()

            vertical_copy.write_bytes(vertical_copy.read_bytes() + b"\n")

            self.assertNotEqual(
                vertical_copy.read_bytes(),
                horizontal_copy.read_bytes(),
            )
            self.assertEqual(original_horizontal, horizontal_copy.read_bytes())

    def test_profile_resolver_uses_component_scoped_paths(self):
        resolver = ProfileResolver()

        for component in ProfileComponent:
            for platform in ("horizontal", "vertical"):
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
