import unittest
from dataclasses import FrozenInstanceError

from app.domain import (
    ColorPlan,
    CompositionPlan,
    GenerationResult,
    GenerationTranslation,
    GlobalIntent,
    LightingPlan,
    MotionSense,
    NarrativeFacts,
    NarrativeReading,
    PhotographyPlan,
    SceneIntent,
    StagingPlan,
    StoryboardScene,
    VisualBrief,
    VisualStrategy,
)


class VisualGenerationDomainModelsTest(unittest.TestCase):

    def test_models_are_passive_immutable_domain_structures(self):
        reading = NarrativeReading(
            facts=NarrativeFacts(
                stated=(
                    "La ley de correspondencia.",
                )
            )
        )

        self.assertEqual(
            reading.facts.stated,
            (
                "La ley de correspondencia.",
            )
        )

        with self.assertRaises(
            FrozenInstanceError
        ):
            reading.facts = NarrativeFacts()

    def test_intent_models_keep_global_and_scene_responsibilities(self):
        global_intent = GlobalIntent(
            expressive_purpose="Reveal a hidden relation."
        )

        scene_intent = SceneIntent(
            emotional_function="Show the discovery."
        )

        self.assertEqual(
            global_intent.expressive_purpose,
            "Reveal a hidden relation."
        )
        self.assertEqual(
            scene_intent.emotional_function,
            "Show the discovery."
        )

    def test_visual_models_do_not_require_backend_specific_data(self):
        scene = StoryboardScene(
            scene_number=1,
            text="A reflective scene."
        )

        brief = VisualBrief(
            visible_content="study table",
            visual_strategy=VisualStrategy(
                representation_approach="quiet symbolic realism"
            ),
            staging=StagingPlan(
                main_subject="study table"
            )
        )

        result = GenerationResult(
            output_path="output/images/scene_001.png",
            scene_number=1,
            width=1280,
            height=720
        )

        self.assertEqual(
            brief.visible_content,
            "study table"
        )
        self.assertEqual(
            result.status,
            "completed"
        )

    def test_cognitive_language_models_can_be_composed(self):
        reading = NarrativeReading(
            facts=NarrativeFacts(
                stated=(
                    "A principle is explained.",
                )
            )
        )
        global_intent = GlobalIntent(
            expressive_purpose="Reveal an invisible order.",
            dominant_emotion="wonder",
            global_energy="calm"
        )
        scene_intent = SceneIntent(
            emotional_function="quiet revelation",
            emotion="awe",
            emotional_intensity="low"
        )
        strategy = VisualStrategy(
            representation_approach="cinematic abstraction",
            realism_level="grounded",
            symbolism_degree="restrained",
            scale_treatment="macro and micro echo"
        )
        staging = StagingPlan(
            main_subject="geometric pattern",
            environment="minimal contemplative space",
            action_or_state="still reflection"
        )
        photography = PhotographyPlan(
            point_of_view="observational",
            emotional_distance="measured",
            photographic_atmosphere="quiet"
        )
        composition = CompositionPlan(
            visual_hierarchy="pattern first",
            framing="centered",
            figure_ground_relationship="clear separation"
        )
        lighting = LightingPlan(
            source="soft motivated side light",
            quality="diffuse",
            contrast="gentle"
        )
        color = ColorPlan(
            temperature="neutral warm",
            palette=(
                "deep graphite",
                "soft gold"
            )
        )
        motion = MotionSense(
            latent_energy="contained",
            rhythm="slow",
            visual_breathing="spacious"
        )
        brief = VisualBrief(
            visible_content="nested geometric reflections",
            felt_experience="calm discovery",
            visual_strategy=strategy,
            staging=staging,
            photography=photography,
            composition=composition,
            lighting=lighting,
            color=color,
            motion=motion,
            continuity_relationship="continues the contemplative arc"
        )
        translation = GenerationTranslation(
            target_backend="generic image generator",
            translation_priorities=(
                "preserve visual hierarchy",
            ),
            translation_restrictions=(
                "no backend-specific syntax",
            ),
            translated_directives=(
                "structured visual directive",
            ),
            trace_references=(
                "VisualBrief.visible_content",
            )
        )

        self.assertEqual(
            reading.facts.stated,
            (
                "A principle is explained.",
            )
        )
        self.assertEqual(
            global_intent.global_energy,
            "calm"
        )
        self.assertEqual(
            scene_intent.emotional_intensity,
            "low"
        )
        self.assertIs(
            brief.visual_strategy,
            strategy
        )
        self.assertIs(
            brief.staging,
            staging
        )
        self.assertIs(
            brief.photography,
            photography
        )
        self.assertIs(
            brief.composition,
            composition
        )
        self.assertIs(
            brief.lighting,
            lighting
        )
        self.assertIs(
            brief.color,
            color
        )
        self.assertIs(
            brief.motion,
            motion
        )
        self.assertEqual(
            translation.trace_references,
            (
                "VisualBrief.visible_content",
            )
        )

    def test_cognitive_language_models_are_immutable(self):
        intent = SceneIntent(
            emotional_function="pause"
        )

        with self.assertRaises(
            FrozenInstanceError
        ):
            intent.emotional_function = "changed"

    def test_visual_brief_is_not_a_prompt_or_backend_payload(self):
        field_names = set(
            VisualBrief.__dataclass_fields__
        )

        forbidden = {
            "prompt",
            "positive_prompt",
            "negative_prompt",
            "payload",
            "workflow",
            "nodes",
            "file_path",
            "output_path",
            "constraints",
            "negative_constraints"
        }

        self.assertTrue(
            forbidden.isdisjoint(
                field_names
            )
        )

    def test_generation_translation_does_not_own_creative_decisions(self):
        field_names = set(
            GenerationTranslation.__dataclass_fields__
        )

        forbidden = {
            "narrative_reading",
            "global_intent",
            "scene_intent",
            "visual_brief",
            "visual_strategy",
            "staging",
            "photography",
            "composition",
            "lighting",
            "color",
            "motion"
        }

        self.assertTrue(
            forbidden.isdisjoint(
                field_names
            )
        )


if __name__ == "__main__":
    unittest.main()
