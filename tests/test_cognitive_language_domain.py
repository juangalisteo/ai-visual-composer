import inspect
import unittest
from dataclasses import FrozenInstanceError, fields, is_dataclass

import app.domain as domain
from app.domain import (
    ColorPlan,
    CompositionPlan,
    GenerationTranslation,
    GlobalIntent,
    LightingPlan,
    MotionSense,
    NarrativeFacts,
    NarrativeReading,
    PhotographyPlan,
    SceneIntent,
    StagingPlan,
    VisualBrief,
    VisualStrategy,
)


COGNITIVE_MODELS = (
    NarrativeReading,
    GlobalIntent,
    SceneIntent,
    VisualStrategy,
    StagingPlan,
    PhotographyPlan,
    CompositionPlan,
    LightingPlan,
    ColorPlan,
    MotionSense,
    VisualBrief,
    GenerationTranslation,
)


class CognitiveLanguageDomainTest(unittest.TestCase):

    def test_all_cognitive_models_are_frozen_dataclasses(self):
        for model in COGNITIVE_MODELS:
            with self.subTest(
                model=model.__name__
            ):
                self.assertTrue(
                    is_dataclass(
                        model
                    )
                )
                self.assertTrue(
                    model.__dataclass_params__.frozen
                )

    def test_all_cognitive_models_can_be_constructed(self):
        strategy = VisualStrategy(
            representation_approach="grounded symbolic image"
        )
        staging = StagingPlan(
            main_subject="reflective object"
        )
        photography = PhotographyPlan(
            point_of_view="observational"
        )
        composition = CompositionPlan(
            visual_hierarchy="subject first"
        )
        lighting = LightingPlan(
            source="motivated soft source"
        )
        color = ColorPlan(
            temperature="warm neutral"
        )
        motion = MotionSense(
            latent_energy="still"
        )

        instances = (
            NarrativeReading(
                facts=NarrativeFacts(
                    stated=(
                        "A thought is presented.",
                    )
                )
            ),
            GlobalIntent(
                expressive_purpose="Create contemplative clarity."
            ),
            SceneIntent(
                emotional_function="hold a pause"
            ),
            strategy,
            staging,
            photography,
            composition,
            lighting,
            color,
            motion,
            VisualBrief(
                visible_content="reflective object",
                visual_strategy=strategy,
                staging=staging,
                photography=photography,
                composition=composition,
                lighting=lighting,
                color=color,
                motion=motion
            ),
            GenerationTranslation(
                target_backend="generic"
            ),
        )

        self.assertEqual(
            len(
                COGNITIVE_MODELS
            ),
            len(
                instances
            )
        )

    def test_models_are_immutable(self):
        reading = NarrativeReading(
            facts=NarrativeFacts(
                stated=(
                    "A scene happens.",
                )
            )
        )

        with self.assertRaises(
            FrozenInstanceError
        ):
            reading.facts = NarrativeFacts()

    def test_public_domain_imports_expose_cognitive_models(self):
        for model in COGNITIVE_MODELS:
            with self.subTest(
                model=model.__name__
            ):
                self.assertIs(
                    getattr(
                        domain,
                        model.__name__
                    ),
                    model
                )

    def test_models_have_no_backend_or_runtime_dependencies(self):
        source = inspect.getsource(
            domain
        ) + inspect.getsource(
            __import__(
                "app.domain.visual_generation",
                fromlist=[
                    "x"
                ]
            )
        )

        forbidden = (
            "ComfyUI",
            "Flux",
            "HTTP",
            "ImageBuilder",
            "ImagePromptSystem",
            "ComfyUIBackend",
            "ImageManifestWriter",
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

    def test_visual_brief_composes_plans_without_cycles(self):
        strategy = VisualStrategy(
            representation_approach="restrained realism"
        )
        staging = StagingPlan(
            main_subject="person reading"
        )
        photography = PhotographyPlan(
            point_of_view="respectful distance"
        )
        composition = CompositionPlan(
            visual_hierarchy="person and book"
        )
        lighting = LightingPlan(
            source="window light"
        )
        color = ColorPlan(
            temperature="soft warm"
        )
        motion = MotionSense(
            latent_energy="quiet"
        )
        brief = VisualBrief(
            visible_content="person reading beside a window",
            visual_strategy=strategy,
            staging=staging,
            photography=photography,
            composition=composition,
            lighting=lighting,
            color=color,
            motion=motion
        )

        self.assertIs(
            brief.visual_strategy,
            strategy
        )
        self.assertNotIn(
            "visual_brief",
            {
                field.name
                for field in fields(
                    VisualStrategy
                )
            }
        )

    def test_field_ownership_uses_distinct_names_for_shared_concepts(self):
        self.assertIn(
            "global_energy",
            GlobalIntent.__dataclass_fields__
        )
        self.assertIn(
            "emotional_intensity",
            SceneIntent.__dataclass_fields__
        )
        self.assertIn(
            "latent_energy",
            MotionSense.__dataclass_fields__
        )
        self.assertIn(
            "scale_treatment",
            VisualStrategy.__dataclass_fields__
        )
        self.assertIn(
            "frame_scale",
            CompositionPlan.__dataclass_fields__
        )

    def test_ambiguous_generic_fields_are_not_used_in_cognitive_models(self):
        forbidden = {
            "data",
            "info",
            "metadata",
            "notes",
            "settings",
            "options",
            "constraints",
        }

        for model in COGNITIVE_MODELS:
            field_names = {
                field.name
                for field in fields(
                    model
                )
            }

            with self.subTest(
                model=model.__name__
            ):
                self.assertTrue(
                    forbidden.isdisjoint(
                        field_names
                    )
                )

    def test_obsolete_stage_b_models_are_not_public_exports(self):
        obsolete_names = (
            "NarrativeAnalysis",
            "GlobalIntention",
            "LocalIntention",
            "VisualPlan",
        )

        for name in obsolete_names:
            with self.subTest(
                name=name
            ):
                self.assertFalse(
                    hasattr(
                        domain,
                        name
                    )
                )


if __name__ == "__main__":
    unittest.main()
