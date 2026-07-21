import inspect
import unittest
from dataclasses import FrozenInstanceError, fields, is_dataclass

import app.domain as domain
from app.domain import (
    AttentionalIntention,
    CognitiveIntention,
    CommunicativeIntention,
    EmotionalIntention,
    Intention,
    IntentionLevel,
    NarrativeIntention,
    NegativeIntention,
    SymbolicIntention,
    TransformativeIntention,
)


INTENTION_MODELS = (
    CommunicativeIntention,
    EmotionalIntention,
    CognitiveIntention,
    NarrativeIntention,
    SymbolicIntention,
    TransformativeIntention,
    AttentionalIntention,
    NegativeIntention,
    Intention,
)


class IntentionDomainTest(unittest.TestCase):

    def test_intention_models_are_frozen_dataclasses(self):
        for model in INTENTION_MODELS:
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

    def test_intention_level_supports_official_hierarchy(self):
        self.assertEqual(
            IntentionLevel.WORK.value,
            "work"
        )
        self.assertEqual(
            IntentionLevel.SEQUENCE.value,
            "sequence"
        )
        self.assertEqual(
            IntentionLevel.SCENE.value,
            "scene"
        )
        self.assertEqual(
            IntentionLevel.BEAT.value,
            "beat"
        )

    def test_dimensions_are_optional(self):
        intention = Intention(
            communicative=CommunicativeIntention(
                understanding="The key carries responsibility."
            )
        )

        self.assertEqual(
            intention.communicative.understanding,
            "The key carries responsibility."
        )
        self.assertIsNone(
            intention.emotional
        )
        self.assertIsNone(
            intention.negative
        )

    def test_negative_intention_represents_interpretive_exclusions(self):
        negative = NegativeIntention(
            avoid_interpretations=(
                "casual handoff",
            ),
            avoid_effects=(
                "lightness",
            ),
            avoid_meaning_drift=(
                "the key as decoration only",
            )
        )

        self.assertEqual(
            negative.avoid_interpretations,
            (
                "casual handoff",
            )
        )
        self.assertEqual(
            negative.avoid_effects,
            (
                "lightness",
            )
        )

    def test_intention_is_only_an_aggregator(self):
        self.assertEqual(
            tuple(
                field.name
                for field in fields(
                    Intention
                )
            ),
            (
                "communicative",
                "emotional",
                "cognitive",
                "narrative",
                "symbolic",
                "transformative",
                "attentional",
                "negative",
            )
        )

    def test_intention_is_immutable(self):
        intention = Intention()

        with self.assertRaises(
            FrozenInstanceError
        ):
            intention.communicative = CommunicativeIntention()

    def test_public_domain_exports_intention_models(self):
        for model in INTENTION_MODELS:
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
        self.assertIs(
            domain.IntentionLevel,
            IntentionLevel
        )

    def test_intention_domain_has_no_runtime_or_visual_terms(self):
        source = inspect.getsource(
            __import__(
                "app.domain.intention",
                fromlist=[
                    "x"
                ]
            )
        )
        forbidden = (
            "ImageBuilder",
            "VisualDirector",
            "ComfyUI",
            "Flux",
            "payload",
            "workflow",
            "backend",
            "runtime",
            "camera",
            "lighting",
            "composition",
            "manifest",
            "requests",
            "urllib",
        )
        lowered = source.lower()

        for item in forbidden:
            with self.subTest(
                item=item
            ):
                self.assertNotIn(
                    item.lower(),
                    lowered
                )

    def test_intention_models_have_no_custom_public_methods(self):
        for model in INTENTION_MODELS:
            public_callables = [
                name
                for name, value in model.__dict__.items()
                if not name.startswith(
                    "_"
                )
                and callable(
                    value
                )
            ]

            with self.subTest(
                model=model.__name__
            ):
                self.assertEqual(
                    public_callables,
                    []
                )


if __name__ == "__main__":
    unittest.main()
