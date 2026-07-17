import unittest
from dataclasses import FrozenInstanceError

from app.domain import (
    GenerationResult,
    GlobalIntention,
    LocalIntention,
    NarrativeAnalysis,
    StoryboardScene,
    VisualBrief,
    VisualPlan,
)


class VisualGenerationDomainModelsTest(unittest.TestCase):

    def test_models_are_passive_immutable_domain_structures(self):
        analysis = NarrativeAnalysis(
            source_text="La ley de correspondencia.",
            concepts=("correspondence",)
        )

        self.assertEqual(
            analysis.concepts,
            ("correspondence",)
        )

        with self.assertRaises(
            FrozenInstanceError
        ):
            analysis.source_text = "changed"

    def test_intention_models_keep_global_and_local_responsibilities(self):
        global_intention = GlobalIntention(
            purpose="Reveal a hidden relation."
        )

        local_intention = LocalIntention(
            global_intention=global_intention,
            scene_function="Show the discovery."
        )

        self.assertIs(
            local_intention.global_intention,
            global_intention
        )
        self.assertEqual(
            local_intention.scene_function,
            "Show the discovery."
        )

    def test_visual_models_do_not_require_backend_specific_data(self):
        scene = StoryboardScene(
            scene_number=1,
            text="A reflective scene."
        )

        plan = VisualPlan(
            storyboard_scene=scene,
            staging=("quiet interior",),
            photography=("soft directional light",)
        )

        brief = VisualBrief(
            storyboard_scene=scene,
            visual_plan=plan,
            subject="study table",
            constraints=("no readable text",)
        )

        result = GenerationResult(
            output_path="output/images/scene_001.png",
            scene_number=1,
            width=1280,
            height=720
        )

        self.assertEqual(
            brief.visual_plan,
            plan
        )
        self.assertEqual(
            result.status,
            "completed"
        )


if __name__ == "__main__":
    unittest.main()
