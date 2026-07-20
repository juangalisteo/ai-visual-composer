import inspect
import unittest

from app.domain import (
    ColorPlan,
    CompositionPlan,
    GenerationResult,
    GenerationTranslation,
    GlobalIntent,
    LightingPlan,
    MotionSense,
    NarrativeReading,
    PhotographyPlan,
    SceneIntent,
    StagingPlan,
    StoryboardScene,
    VisualBrief,
    VisualStrategy,
)
from app.domain.adapters import (
    LegacyCognitiveAdapter,
    LegacyCognitiveSceneAdaptation,
)


class LegacyCognitiveAdapterTest(unittest.TestCase):

    def test_storyboard_scene_adapts_to_cognitive_models(self):
        scene = StoryboardScene(
            scene_number=3,
            text="  La correspondencia aparece.  ",
            narrative_role="exposition",
            narrative_moment="opening",
            subject="pattern",
            action="reflecting",
            setting="quiet room",
            duration=4,
            source_index=2
        )

        adapted = LegacyCognitiveAdapter.from_storyboard_scene(
            storyboard_scene=scene,
            visual_idea="  A quiet symbolic pattern  "
        )

        self.assertIsInstance(
            adapted,
            LegacyCognitiveSceneAdaptation
        )
        self.assertIsInstance(
            adapted.narrative_reading,
            NarrativeReading
        )
        self.assertIsInstance(
            adapted.global_intent,
            GlobalIntent
        )
        self.assertIsInstance(
            adapted.scene_intent,
            SceneIntent
        )
        self.assertIsInstance(
            adapted.visual_strategy,
            VisualStrategy
        )
        self.assertIsInstance(
            adapted.staging,
            StagingPlan
        )
        self.assertIsInstance(
            adapted.photography,
            PhotographyPlan
        )
        self.assertIsInstance(
            adapted.composition,
            CompositionPlan
        )
        self.assertIsInstance(
            adapted.lighting,
            LightingPlan
        )
        self.assertIsInstance(
            adapted.color,
            ColorPlan
        )
        self.assertIsInstance(
            adapted.motion,
            MotionSense
        )
        self.assertIsInstance(
            adapted.visual_brief,
            VisualBrief
        )

    def test_storyboard_adapter_preserves_known_data_without_interpretation(self):
        scene = StoryboardScene(
            scene_number=1,
            text="  Texto narrativo.  ",
            narrative_role="setup",
            narrative_moment="first beat",
            subject="table",
            action="waiting",
            setting="interior"
        )

        adapted = LegacyCognitiveAdapter.from_storyboard_scene(
            storyboard_scene=scene,
            visual_idea="  A still table  "
        )

        self.assertEqual(
            "Texto narrativo.",
            adapted.narrative_reading.facts.stated[0]
        )
        self.assertEqual(
            "setup",
            adapted.narrative_reading.function.primary
        )
        self.assertEqual(
            "first beat",
            adapted.narrative_reading.context.known_context
        )
        self.assertEqual(
            "table",
            adapted.staging.main_subject
        )
        self.assertEqual(
            "waiting",
            adapted.staging.action_or_state
        )
        self.assertEqual(
            "interior",
            adapted.staging.environment
        )
        self.assertEqual(
            "A still table",
            adapted.visual_brief.visible_content
        )

    def test_missing_legacy_data_stays_empty(self):
        scene = StoryboardScene(
            scene_number=1,
            text="Scene text."
        )

        adapted = LegacyCognitiveAdapter.from_storyboard_scene(
            storyboard_scene=scene
        )

        self.assertEqual(
            "",
            adapted.global_intent.expressive_purpose
        )
        self.assertEqual(
            "",
            adapted.scene_intent.emotional_function
        )
        self.assertEqual(
            "",
            adapted.visual_strategy.representation_approach
        )
        self.assertEqual(
            "",
            adapted.photography.point_of_view
        )
        self.assertEqual(
            "",
            adapted.composition.visual_hierarchy
        )
        self.assertEqual(
            "",
            adapted.lighting.source
        )
        self.assertEqual(
            "",
            adapted.color.temperature
        )
        self.assertEqual(
            "",
            adapted.motion.latent_energy
        )

    def test_generation_result_adapts_to_translation_trace_only(self):
        result = GenerationResult(
            output_path="output/images/scene_001.png",
            scene_number=1,
            width=640,
            height=360,
            duration=3
        )

        translation = (
            LegacyCognitiveAdapter.generation_translation_from_result(
                generation_result=result,
                target_backend="legacy"
            )
        )

        self.assertIsInstance(
            translation,
            GenerationTranslation
        )
        self.assertEqual(
            "legacy",
            translation.target_backend
        )
        self.assertEqual(
            (),
            translation.translation_priorities
        )
        self.assertEqual(
            (),
            translation.translation_restrictions
        )
        self.assertEqual(
            (),
            translation.translated_directives
        )
        self.assertEqual(
            (
                "GenerationResult.output_path",
                "GenerationResult.scene_number",
                "GenerationResult.width",
                "GenerationResult.height",
                "GenerationResult.duration",
            ),
            translation.trace_references
        )

    def test_adapter_has_no_runtime_backend_or_prompt_dependencies(self):
        source = inspect.getsource(
            LegacyCognitiveAdapter
        )

        forbidden = (
            "ComfyUI",
            "Flux",
            "HTTP",
            "ImageBuilder",
            "ImagePromptSystem",
            "ComfyUIBackend",
            "ImageManifestWriter",
            "Manifest",
            "urllib",
            "requests",
        )

        for item in forbidden:
            with self.subTest(
                item=item
            ):
                self.assertNotIn(
                    item,
                    source
                )


if __name__ == "__main__":
    unittest.main()
