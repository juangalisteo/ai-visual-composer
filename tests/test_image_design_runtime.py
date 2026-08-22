import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core import start


class FakeImageBuilder:

    def __init__(self):
        self.received_scenes = None

    def build(
        self,
        storyboard_path=None,
        output_dir=None
    ):
        storyboard_path = Path(
            storyboard_path
        )
        output_dir = Path(
            output_dir
        )
        self.received_scenes = json.loads(
            storyboard_path.read_text(
                encoding="utf-8"
            )
        )
        output_dir.mkdir(
            parents=True,
            exist_ok=True
        )
        image_path = (
            output_dir
            / "scene_001.png"
        )
        image_path.write_bytes(
            b"image"
        )
        manifest_path = (
            output_dir
            / "images_manifest.json"
        )
        manifest_path.write_text(
            json.dumps(
                [
                    {
                        "scene": 1,
                        "image": str(image_path),
                        "width": 1080,
                        "height": 1920,
                        "duration": None
                    }
                ],
                indent=4
            ),
            encoding="utf-8"
        )
        return manifest_path


class ImageDesignRuntimeTest(unittest.TestCase):

    def test_start_routes_design_image_before_narrative_pipeline(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            previous_cwd = Path.cwd()
            fake_image_builder = FakeImageBuilder()

            try:
                os.chdir(
                    root
                )
                input_dir = root / "input"
                input_dir.mkdir()
                (
                    input_dir
                    / "guion_imagen.txt"
                ).write_text(
                    "Diseno visual directo desde start.",
                    encoding="utf-8"
                )

                with patch.dict(
                    os.environ,
                    {
                        "MC_PIPELINE_MODE": "design_image",
                        "MC_PROJECT_NAME": "design start",
                    },
                    clear=False
                ), patch(
                    "app.core.start.ConfigManager",
                    side_effect=AssertionError(
                        "ConfigManager must not run before design route"
                    )
                ), patch(
                    "app.core.start.ImageBuilder",
                    return_value=fake_image_builder
                ), patch(
                    "app.core.start.MediaProbe.get_duration",
                    return_value=None
                ):
                    result = start.iniciar()

                self.assertEqual(
                    "images_manifest.json",
                    Path(result).name
                )
                self.assertEqual(
                    1,
                    len(fake_image_builder.received_scenes)
                )
            finally:
                os.chdir(
                    previous_cwd
                )

    def test_design_image_uses_guion_imagen_and_generates_one_manifest_entry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            previous_cwd = Path.cwd()
            fake_image_builder = FakeImageBuilder()

            try:
                os.chdir(
                    root
                )
                input_dir = root / "input"
                input_dir.mkdir()
                (
                    input_dir
                    / "tema.txt"
                ).write_text(
                    "tema que no debe usarse",
                    encoding="utf-8"
                )
                (
                    input_dir
                    / "guion.txt"
                ).write_text(
                    "guion narrativo que no debe usarse",
                    encoding="utf-8"
                )
                (
                    input_dir
                    / "guion_imagen.txt"
                ).write_text(
                    "Diseno visual manual para una sola imagen.",
                    encoding="utf-8"
                )

                with patch.dict(
                    os.environ,
                    {
                        "MC_PIPELINE_MODE": "design_image",
                        "MC_PROJECT_NAME": "design image",
                    },
                    clear=False
                ), patch(
                    "app.core.start.ScriptOperation",
                    side_effect=AssertionError(
                        "ScriptOperation must not run"
                    )
                ), patch(
                    "app.core.start.ScriptPreparationService",
                    side_effect=AssertionError(
                        "ScriptPreparationService must not run"
                    )
                ), patch(
                    "app.core.start.VoiceBuilder",
                    side_effect=AssertionError(
                        "VoiceBuilder must not run"
                    )
                ), patch(
                    "app.core.start.MusicSelector",
                    side_effect=AssertionError(
                        "MusicSelector must not run"
                    )
                ), patch(
                    "app.core.start.AudioMixer",
                    side_effect=AssertionError(
                        "AudioMixer must not run"
                    )
                ), patch(
                    "app.core.start.SubtitleBuilder",
                    side_effect=AssertionError(
                        "SubtitleBuilder must not run"
                    )
                ), patch(
                    "app.core.start.SrtOptimizer",
                    side_effect=AssertionError(
                        "SrtOptimizer must not run"
                    )
                ), patch(
                    "app.core.start.StoryboardBuilder",
                    side_effect=AssertionError(
                        "StoryboardBuilder must not run"
                    )
                ), patch(
                    "app.core.start.VideoBuilder",
                    side_effect=AssertionError(
                        "VideoBuilder must not run"
                    )
                ), patch(
                    "app.core.start.MediaProbe.get_duration",
                    return_value=None
                ):
                    result = start.ejecutar_diseno_imagen(
                        image_builder=fake_image_builder
                    )

                manifest = json.loads(
                    Path(result).read_text(
                        encoding="utf-8"
                    )
                )
                self.assertEqual(
                    1,
                    len(manifest)
                )
                self.assertEqual(
                    "scene_001.png",
                    Path(manifest[0]["image"]).name
                )
                self.assertEqual(
                    1,
                    len(fake_image_builder.received_scenes)
                )
                self.assertEqual(
                    (
                        "Diseno visual manual para una sola "
                        "imagen."
                    ),
                    fake_image_builder.received_scenes[0][
                        "filmable_interpretation"
                    ]
                )
                self.assertFalse(
                    (
                        root
                        / "output"
                        / "design image"
                        / "audio"
                    ).exists()
                )
                self.assertFalse(
                    (
                        root
                        / "output"
                        / "design image"
                        / "subtitles"
                    ).exists()
                )
                self.assertFalse(
                    (
                        root
                        / "output"
                        / "design image"
                        / "video"
                    ).exists()
                )
            finally:
                os.chdir(
                    previous_cwd
                )

    def test_design_image_rejects_more_than_one_scene(self):
        with self.assertRaises(
            ValueError
        ):
            start._ensure_single_design_scene(
                [
                    {
                        "scene": 1
                    },
                    {
                        "scene": 2
                    }
                ]
            )

    def test_design_profiles_define_independent_image_dimensions(self):
        cases = (
            (
                "config/profiles/diseno/imagen/instagram.json",
                1080,
                1920
            ),
            (
                "config/profiles/diseno/imagen/youtube.json",
                1920,
                1080
            ),
        )

        for profile_path, expected_width, expected_height in cases:
            with self.subTest(
                profile_path=profile_path
            ):
                profile = json.loads(
                    Path(profile_path).read_text(
                        encoding="utf-8"
                    )
                )

                self.assertEqual(
                    expected_width,
                    profile["video_style"]["width"]
                )
                self.assertEqual(
                    expected_height,
                    profile["video_style"]["height"]
                )
                self.assertEqual(
                    {
                        "images": True
                    },
                    profile["builders"]
                )
                self.assertNotIn(
                    "voice",
                    profile["builders"]
                )
                self.assertNotIn(
                    "storyboard",
                    profile["builders"]
                )
                self.assertNotIn(
                    "video",
                    profile["builders"]
                )


if __name__ == "__main__":
    unittest.main()
