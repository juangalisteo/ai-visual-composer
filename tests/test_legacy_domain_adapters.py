import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.domain import GenerationResult, StoryboardScene
from app.domain.adapters import (
    LegacyGenerationResultAdapter,
    LegacyStoryboardSceneAdapter,
)
from app.modules.images.image_builder import ImageBuilder


class LegacyDomainAdaptersTest(unittest.TestCase):

    def test_storyboard_adapter_preserves_legacy_scene_data(self):
        scene = {
            "scene": 4,
            "text": "  Texto narrativo.  ",
            "duration": 3,
            "visual_idea": "A quiet symbolic image"
        }

        storyboard_scene = LegacyStoryboardSceneAdapter.from_dict(
            scene=scene,
            default_scene_number=1
        )

        self.assertIsInstance(
            storyboard_scene,
            StoryboardScene
        )
        self.assertEqual(
            4,
            storyboard_scene.scene_number
        )
        self.assertEqual(
            "Texto narrativo.",
            storyboard_scene.text
        )
        self.assertEqual(
            3,
            storyboard_scene.duration
        )
        self.assertEqual(
            1,
            storyboard_scene.source_index
        )
        self.assertEqual(
            "",
            storyboard_scene.subject
        )
        self.assertEqual(
            "A quiet symbolic image",
            LegacyStoryboardSceneAdapter.visual_idea(
                scene
            )
        )

    def test_generation_result_adapter_preserves_legacy_output_data(self):
        storyboard_scene = StoryboardScene(
            scene_number=2,
            text="Escena",
            duration=2.5
        )

        result = LegacyGenerationResultAdapter.from_image_result(
            image_path=Path("output/images/scene_002.png"),
            storyboard_scene=storyboard_scene,
            width=640,
            height=360
        )

        self.assertIsInstance(
            result,
            GenerationResult
        )
        self.assertEqual(
            "output\\images\\scene_002.png",
            result.output_path
        )
        self.assertEqual(
            2,
            result.scene_number
        )
        self.assertEqual(
            640,
            result.width
        )
        self.assertEqual(
            360,
            result.height
        )
        self.assertEqual(
            2.5,
            result.duration
        )

    def test_image_builder_uses_domain_models_without_changing_manifest(self):
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
                get_profile_config=lambda: {
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

            with patch.multiple(
                "app.modules.images.image_builder",
                ProjectManager=lambda: project,
                ConfigManager=lambda: config
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

        self.assertEqual(
            [
                {
                    "scene": 1,
                    "prompt": (
                        "A quiet dawn over a valley, "
                        "ultra realistic cinematic image, "
                        "photorealistic, documentary style, "
                        "golden volumetric lighting, "
                        "deep shadows, natural colors, "
                        "high detail, sharp focus, "
                        "epic composition, atmospheric depth, "
                        "no cartoon, no anime, no illustration, "
                        "premium film still, 8k, "
                        "no text, no letters, no words, "
                        "no typography, no captions, "
                        "no subtitles, no logos, "
                        "no watermarks, no signs, "
                        "no readable characters, "
                        "no handwritten text, "
                        "no printed text, "
                        "no text on books, "
                        "no text on screens, "
                        "no text on walls, "
                        "no text on objects, "
                        "professional cinematic realism, "
                        "grounded documentary aesthetic, "
                        "natural believable appearance, "
                        "coherent production design, "
                        "professional visual quality"
                    ),
                    "positive_prompt": (
                        "A quiet dawn over a valley, "
                        "ultra realistic cinematic image, "
                        "photorealistic, documentary style, "
                        "golden volumetric lighting, "
                        "deep shadows, natural colors, "
                        "high detail, sharp focus, "
                        "epic composition, atmospheric depth, "
                        "no cartoon, no anime, no illustration, "
                        "premium film still, 8k, "
                        "no text, no letters, no words, "
                        "no typography, no captions, "
                        "no subtitles, no logos, "
                        "no watermarks, no signs, "
                        "no readable characters, "
                        "no handwritten text, "
                        "no printed text, "
                        "no text on books, "
                        "no text on screens, "
                        "no text on walls, "
                        "no text on objects"
                    ),
                    "negative_prompt": "",
                    "visual_director": {
                        "enabled": False,
                        "fallback": False,
                        "fallback_reason": None,
                        "directives": {}
                    },
                    "image": str(
                        output_dir / "scene_001.png"
                    ),
                    "width": 640,
                    "height": 360,
                    "duration": 3
                }
            ],
            manifest
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
