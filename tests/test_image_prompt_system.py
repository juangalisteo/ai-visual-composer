import inspect
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.modules.images.image_builder import ImageBuilder
from app.modules.images.prompt_system import ImagePromptSystem


class RecordingPromptSystem:

    def __init__(
        self
    ):
        self.legacy_visual_ideas = []
        self.composed_prompts = []

    def build_legacy_prompt(
        self,
        visual_idea
    ):
        self.legacy_visual_ideas.append(
            visual_idea
        )
        return (
            f"legacy::{visual_idea}"
        )

    def compose_backend_prompt(
        self,
        positive_prompt,
        negative_prompt=""
    ):
        self.composed_prompts.append(
            (
                positive_prompt,
                negative_prompt
            )
        )
        return (
            f"backend::{positive_prompt}::{negative_prompt}"
        )

    def dedupe_prompt_parts(
        self,
        parts
    ):
        return list(
            parts
        )


class FailingVisualDirector:

    def direct(
        self,
        context
    ):
        raise RuntimeError(
            "forced visual director failure"
        )


class ImagePromptSystemTest(unittest.TestCase):

    def test_legacy_prompt_is_identical_to_image_builder_wrapper(self):
        visual_idea = "A quiet architectural corridor"
        prompt_system = ImagePromptSystem()
        builder = ImageBuilder(
            prompt_system=prompt_system
        )

        self.assertEqual(
            builder._build_prompt(
                visual_idea
            ),
            prompt_system.build_legacy_prompt(
                visual_idea
            )
        )
        self.assertIn(
            "premium film still, 8k, no text",
            prompt_system.build_legacy_prompt(
                visual_idea
            )
        )

    def test_directed_prompt_composition_is_identical_to_wrapper(self):
        positive_prompt = (
            "A symbolic room, wide horizontal 16:9"
        )
        negative_prompt = (
            "no text, no logos"
        )
        prompt_system = ImagePromptSystem()
        builder = ImageBuilder(
            prompt_system=prompt_system
        )

        self.assertEqual(
            builder._compose_backend_prompt(
                positive_prompt=positive_prompt,
                negative_prompt=negative_prompt
            ),
            prompt_system.compose_backend_prompt(
                positive_prompt=positive_prompt,
                negative_prompt=negative_prompt
            )
        )
        self.assertEqual(
            (
                "A symbolic room, wide horizontal 16:9, "
                "professional cinematic realism, "
                "grounded documentary aesthetic, "
                "natural believable appearance, "
                "coherent production design, "
                "professional visual quality, "
                "avoid: no text, no logos"
            ),
            prompt_system.compose_backend_prompt(
                positive_prompt=positive_prompt,
                negative_prompt=negative_prompt
            )
        )

    def test_directed_prompt_without_negative_prompt_is_identical(self):
        positive_prompt = (
            "A symbolic room, wide horizontal 16:9"
        )
        prompt = ImagePromptSystem().compose_backend_prompt(
            positive_prompt=positive_prompt,
            negative_prompt=""
        )

        self.assertEqual(
            (
                "A symbolic room, wide horizontal 16:9, "
                "professional cinematic realism, "
                "grounded documentary aesthetic, "
                "natural believable appearance, "
                "coherent production design, "
                "professional visual quality"
            ),
            prompt
        )
        self.assertNotIn(
            "avoid:",
            prompt
        )

    def test_prompt_system_has_no_backend_dependencies(self):
        source = inspect.getsource(
            ImagePromptSystem
        )

        for forbidden in (
            "ComfyUI",
            "urllib",
            "Request",
            "urlopen",
            "workflow",
            "manifest",
            "_generate_image",
            "_download_image"
        ):
            with self.subTest(
                forbidden=forbidden
            ):
                self.assertNotIn(
                    forbidden,
                    source
                )

    def test_image_builder_delegates_prompt_composition_when_disabled(self):
        prompt_system = RecordingPromptSystem()
        manifest = self._build_manifest(
            prompt_system=prompt_system,
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
        )

        self.assertEqual(
            ["A quiet dawn over a valley"],
            prompt_system.legacy_visual_ideas
        )
        self.assertEqual(
            [
                (
                    "legacy::A quiet dawn over a valley",
                    ""
                )
            ],
            prompt_system.composed_prompts
        )
        self.assertEqual(
            "backend::legacy::A quiet dawn over a valley::",
            manifest[0]["prompt"]
        )

    def test_image_builder_delegates_prompt_composition_on_fallback(self):
        prompt_system = RecordingPromptSystem()
        manifest = self._build_manifest(
            prompt_system=prompt_system,
            visual_director=FailingVisualDirector(),
            profile={
                "format": "horizontal",
                "video_style": {
                    "width": 640,
                    "height": 360
                }
            }
        )

        self.assertEqual(
            ["A quiet dawn over a valley"],
            prompt_system.legacy_visual_ideas
        )
        self.assertEqual(
            [
                (
                    "legacy::A quiet dawn over a valley",
                    ""
                )
            ],
            prompt_system.composed_prompts
        )
        self.assertEqual(
            "backend::legacy::A quiet dawn over a valley::",
            manifest[0]["prompt"]
        )
        self.assertTrue(
            manifest[0]["visual_director"]["fallback"]
        )

    def _build_manifest(
        self,
        prompt_system,
        profile,
        visual_director=None
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            storyboard_path = root / "storyboard.json"
            manifest_path = root / "images_manifest.json"
            output_dir = root / "images"
            workflow_path = root / "workflow.json"

            storyboard_path.write_text(
                json.dumps(
                    [
                        {
                            "scene": 1,
                            "text": "La escena conserva su texto.",
                            "visual_idea": "A quiet dawn over a valley",
                            "duration": 3
                        }
                    ],
                    ensure_ascii=False
                ),
                encoding="utf-8"
            )
            workflow_path.write_text(
                "{}",
                encoding="utf-8"
            )

            project = SimpleNamespace(
                images_manifest_path=lambda: manifest_path
            )
            config = SimpleNamespace(
                get_profile_config=lambda: profile
            )

            with patch.multiple(
                "app.modules.images.image_builder",
                ProjectManager=lambda: project,
                ConfigManager=lambda: config
            ):
                builder = ImageBuilder(
                    workflow_path=workflow_path,
                    visual_director=visual_director,
                    prompt_system=prompt_system
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

            return json.loads(
                manifest_path.read_text(
                    encoding="utf-8"
                )
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
