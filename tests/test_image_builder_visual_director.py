import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.modules.images.image_builder import ImageBuilder


class FailingVisualDirector:

    def direct(
        self,
        context
    ):
        raise RuntimeError(
            "forced visual director failure"
        )


class ImageBuilderVisualDirectorTest(unittest.TestCase):

    def test_build_enriches_prompts_without_changing_scene_contract(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            storyboard_path = self._write_storyboard(
                root
            )
            manifest_path = root / "images_manifest.json"
            output_dir = root / "images"
            workflow_path = self._write_workflow(
                root
            )

            with self._patched_environment(
                manifest_path=manifest_path,
                profile={
                    "format": "horizontal",
                    "video_style": {
                        "width": 640,
                        "height": 360
                    }
                }
            ):
                builder = ImageBuilder(
                    workflow_path=workflow_path
                )

                with patch.object(
                    ImageBuilder,
                    "_generate_image",
                    side_effect=self._fake_generate_image
                ) as generate_image:
                    result_path = builder.build(
                        storyboard_path=storyboard_path,
                        output_dir=output_dir
                    )

            self.assertEqual(
                manifest_path,
                result_path
            )
            self.assertEqual(
                2,
                generate_image.call_count
            )

            manifest = json.loads(
                manifest_path.read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                2,
                len(manifest)
            )
            self.assertEqual(
                3.5,
                manifest[0]["duration"]
            )
            self.assertIn(
                "wide horizontal 16:9",
                manifest[0]["prompt"]
            )
            self.assertIn(
                "professional cinematic realism",
                manifest[0]["prompt"]
            )
            self.assertIn(
                "coherent production design",
                manifest[0]["prompt"]
            )
            self.assertIn(
                "positive_prompt",
                manifest[0]
            )
            self.assertIn(
                "negative_prompt",
                manifest[0]
            )
            self.assertEqual(
                {
                    "scene",
                    "prompt",
                    "positive_prompt",
                    "negative_prompt",
                    "visual_director",
                    "image",
                    "width",
                    "height",
                    "duration"
                },
                set(
                    manifest[0].keys()
                )
            )
            self.assertFalse(
                manifest[0]["visual_director"]["fallback"]
            )
            self.assertTrue(
                manifest[0]["visual_director"]["directives"]
            )

    def test_vertical_profile_adds_vertical_prompt_guidance(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            storyboard_path = self._write_storyboard(
                root
            )
            manifest_path = root / "images_manifest.json"
            output_dir = root / "images"
            workflow_path = self._write_workflow(
                root
            )

            with self._patched_environment(
                manifest_path=manifest_path,
                profile={
                    "format": "vertical",
                    "video_style": {
                        "width": 360,
                        "height": 640
                    }
                }
            ):
                builder = ImageBuilder(
                    workflow_path=workflow_path
                )

                with patch.object(
                    ImageBuilder,
                    "_generate_image",
                    side_effect=self._fake_generate_image
                ):
                    builder.build(
                        storyboard_path=storyboard_path,
                        output_dir=output_dir
                    )

            manifest = json.loads(
                manifest_path.read_text(
                    encoding="utf-8"
                )
            )

            self.assertIn(
                "vertical 9:16",
                manifest[0]["prompt"]
            )

    def test_falls_back_to_legacy_prompt_when_director_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            storyboard_path = self._write_storyboard(
                root
            )
            manifest_path = root / "images_manifest.json"
            output_dir = root / "images"
            workflow_path = self._write_workflow(
                root
            )

            with self._patched_environment(
                manifest_path=manifest_path,
                profile={
                    "format": "horizontal",
                    "video_style": {
                        "width": 640,
                        "height": 360
                    }
                }
            ):
                builder = ImageBuilder(
                    workflow_path=workflow_path,
                    visual_director=FailingVisualDirector()
                )

                with patch.object(
                    ImageBuilder,
                    "_generate_image",
                    side_effect=self._fake_generate_image
                ):
                    builder.build(
                        storyboard_path=storyboard_path,
                        output_dir=output_dir
                    )

            manifest = json.loads(
                manifest_path.read_text(
                    encoding="utf-8"
                )
            )

            self.assertIn(
                "A quiet dawn over a valley",
                manifest[0]["prompt"]
            )
            self.assertIn(
                "professional cinematic realism",
                manifest[0]["prompt"]
            )
            self.assertTrue(
                manifest[0]["visual_director"]["enabled"]
            )
            self.assertTrue(
                manifest[0]["visual_director"]["fallback"]
            )
            self.assertIn(
                "forced visual director failure",
                manifest[0]["visual_director"]["fallback_reason"]
            )

    def test_can_be_disabled_from_optional_profile_section(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            storyboard_path = self._write_storyboard(
                root
            )
            manifest_path = root / "images_manifest.json"
            output_dir = root / "images"
            workflow_path = self._write_workflow(
                root
            )

            with self._patched_environment(
                manifest_path=manifest_path,
                profile={
                    "format": "horizontal",
                    "video_style": {
                        "width": 640,
                        "height": 360
                    },
                    "visual_director": {
                        "enabled": False
                    }
                }
            ):
                builder = ImageBuilder(
                    workflow_path=workflow_path
                )

                with patch.object(
                    ImageBuilder,
                    "_generate_image",
                    side_effect=self._fake_generate_image
                ):
                    builder.build(
                        storyboard_path=storyboard_path,
                        output_dir=output_dir
                    )

            manifest = json.loads(
                manifest_path.read_text(
                    encoding="utf-8"
                )
            )

            self.assertIn(
                "A quiet dawn over a valley",
                manifest[0]["prompt"]
            )
            self.assertIn(
                "professional cinematic realism",
                manifest[0]["prompt"]
            )
            self.assertFalse(
                manifest[0]["visual_director"]["enabled"]
            )
            self.assertFalse(
                manifest[0]["visual_director"]["fallback"]
            )

    def test_official_profiles_do_not_require_visual_director_config(self):
        builder = ImageBuilder()

        for profile_path in (
            Path("config/profiles/youtube/modo_conciencia.json"),
            Path("config/profiles/instagram/modo_conciencia.json")
        ):
            with self.subTest(
                profile_path=profile_path
            ):
                profile = json.loads(
                    profile_path.read_text(
                        encoding="utf-8"
                    )
                )

                self.assertTrue(
                    builder._is_visual_director_enabled(
                        profile
                    )
                )

                width, height = (
                    builder._get_image_dimensions(
                        profile
                    )
                )

                self.assertGreater(
                    width,
                    0
                )
                self.assertGreater(
                    height,
                    0
                )

    def test_legacy_prompt_separates_8k_from_text_restrictions(self):
        prompt = ImageBuilder()._build_prompt(
            "A quiet architectural corridor"
        )

        self.assertIn(
            "premium film still, 8k, no text",
            prompt
        )
        self.assertNotIn(
            "8kno text",
            prompt
        )

    def _write_storyboard(
        self,
        root
    ):
        storyboard_path = root / "storyboard.json"
        storyboard_path.write_text(
            json.dumps(
                [
                    {
                        "scene": 1,
                        "text": (
                            "La luz aparece sobre el valle "
                            "y transforma la atmosfera."
                        ),
                        "visual_idea": (
                            "A quiet dawn over a valley"
                        ),
                        "duration": 3.5
                    },
                    {
                        "scene": 2,
                        "text": (
                            "La luz se abre en el horizonte."
                        ),
                        "visual_idea": (
                            "A soft light opening on the horizon"
                        ),
                        "duration": 2.5
                    }
                ],
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

        return storyboard_path

    def _write_workflow(
        self,
        root
    ):
        workflow_path = root / "workflow.json"
        workflow_path.write_text(
            "{}",
            encoding="utf-8"
        )

        return workflow_path

    def _patched_environment(
        self,
        manifest_path,
        profile
    ):
        project = SimpleNamespace(
            images_manifest_path=lambda: manifest_path
        )
        config = SimpleNamespace(
            get_profile_config=lambda: profile
        )

        return patch.multiple(
            "app.modules.images.image_builder",
            ProjectManager=lambda: project,
            ConfigManager=lambda: config
        )

    def _fake_generate_image(
        self,
        prompt,
        scene_number,
        output_dir,
        width,
        height
    ):
        output_dir.mkdir(
            parents=True,
            exist_ok=True
        )
        image_path = output_dir / f"scene_{scene_number:03d}.png"
        image_path.write_text(
            f"{width}x{height}\n{prompt}",
            encoding="utf-8"
        )

        return image_path


if __name__ == "__main__":
    unittest.main()
