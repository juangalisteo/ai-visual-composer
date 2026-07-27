import unittest

from app.domain import (
    GenerationResult,
    StoryboardScene,
)
from app.domain.adapters import (
    GenerationResultAdapter,
    RuntimeCognitiveAdapter,
    RuntimeCognitiveSceneAdaptation,
    StoryboardSceneAdapter,
)


class RuntimeDomainAdaptersTest(unittest.TestCase):

    def test_storyboard_adapter_preserves_current_storyboard_contract(self):
        scene = StoryboardSceneAdapter.from_dict(
            scene={
                "scene": "2",
                "text": "La escena conserva su texto.",
                "duration": 4.5,
                "visual_idea": "A quiet dawn over a valley",
            },
            default_scene_number=1,
        )

        self.assertEqual(
            scene,
            StoryboardScene(
                scene_number=2,
                text="La escena conserva su texto.",
                duration=4.5,
                source_index=1,
            ),
        )
        self.assertEqual(
            "A quiet dawn over a valley",
            StoryboardSceneAdapter.visual_idea(
                {
                    "visual_idea": "A quiet dawn over a valley",
                }
            ),
        )

    def test_generation_result_adapter_preserves_manifest_inputs(self):
        result = GenerationResultAdapter.from_image_result(
            image_path="output/images/scene_001.png",
            storyboard_scene=StoryboardScene(
                scene_number=1,
                text="Escena",
                duration=3.0,
            ),
            width=640,
            height=360,
        )

        self.assertEqual(
            result,
            GenerationResult(
                output_path="output\\images\\scene_001.png",
                scene_number=1,
                width=640,
                height=360,
                duration=3.0,
            ),
        )

    def test_runtime_cognitive_adapter_builds_effective_visual_source_data(self):
        adaptation = RuntimeCognitiveAdapter.from_storyboard_scene(
            storyboard_scene=StoryboardScene(
                scene_number=1,
                text="La escena conserva su texto.",
                subject="una persona",
                action="observa una llave",
                setting="una biblioteca",
                duration=5.0,
                source_index=1,
            ),
            visual_idea="A person observing an old key",
            orientation="horizontal",
        )

        self.assertIsInstance(
            adaptation,
            RuntimeCognitiveSceneAdaptation,
        )
        self.assertEqual(
            "A person observing an old key",
            adaptation.visual_brief.visible_content,
        )
        self.assertEqual(
            "wide horizontal 16:9",
            adaptation.visual_brief.narrative_composition,
        )
        self.assertEqual(
            "una persona",
            adaptation.visual_brief.staging.main_subject,
        )
        self.assertEqual(
            "observa una llave",
            adaptation.visual_brief.staging.action_or_state,
        )
        self.assertEqual(
            "una biblioteca",
            adaptation.visual_brief.staging.environment,
        )
        self.assertIn(
            "StoryboardScene.duration",
            adaptation.trace_references,
        )

    def test_orientation_guidance_is_deterministic_and_explicit(self):
        self.assertEqual(
            "vertical 9:16",
            RuntimeCognitiveAdapter.composition_guidance_from_orientation(
                "vertical"
            ),
        )
        self.assertEqual(
            "wide horizontal 16:9",
            RuntimeCognitiveAdapter.composition_guidance_from_orientation(
                "horizontal"
            ),
        )
        self.assertEqual(
            "",
            RuntimeCognitiveAdapter.composition_guidance_from_orientation(
                "square"
            ),
        )


if __name__ == "__main__":
    unittest.main()
