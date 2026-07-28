import inspect
import unittest
from dataclasses import FrozenInstanceError, fields, is_dataclass

import app.domain as domain
from app.domain import (
    ExplicitSymbols,
    NarrativeChange,
    NarrativeConcepts,
    NarrativeConfidence,
    NarrativeConflict,
    NarrativeContext,
    NarrativeContinuity,
    NarrativeEntities,
    NarrativeEvent,
    NarrativeFacts,
    NarrativeFunction,
    NarrativeReading,
    NarrativeRelations,
)


NARRATIVE_READING_MODELS = (
    NarrativeFacts,
    NarrativeEvent,
    NarrativeContext,
    NarrativeChange,
    NarrativeFunction,
    NarrativeEntities,
    NarrativeRelations,
    NarrativeConflict,
    NarrativeConcepts,
    ExplicitSymbols,
    NarrativeContinuity,
    NarrativeReading,
)


class NarrativeReadingDomainTest(unittest.TestCase):

    def test_all_narrative_reading_models_are_frozen_dataclasses(self):
        for model in NARRATIVE_READING_MODELS:
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

    def test_narrative_confidence_declares_knowledge_origin(self):
        self.assertEqual(
            NarrativeConfidence.EXPLICIT.value,
            "explicit"
        )
        self.assertEqual(
            NarrativeConfidence.CONTEXTUAL.value,
            "contextual"
        )
        self.assertEqual(
            NarrativeConfidence.INFERRED.value,
            "inferred"
        )

    def test_narrative_reading_can_be_composed(self):
        facts = NarrativeFacts(
            stated=(
                "A person finds an old key.",
            ),
            existing_elements=(
                "person",
                "old key",
                "abandoned house",
            )
        )
        event = NarrativeEvent(
            action="finds",
            subject="person",
            object="old key",
            initial_state="key unknown",
            final_state="key discovered"
        )
        context = NarrativeContext(
            known_context="abandoned house",
            confidence=NarrativeConfidence.CONTEXTUAL
        )
        change = NarrativeChange(
            changes=(
                "old key enters the narrative",
            ),
            remains=(
                "house remains abandoned",
            ),
            change_type="factual"
        )
        function = NarrativeFunction(
            primary="discovery",
            secondary=(
                "setup",
            )
        )
        entities = NarrativeEntities(
            characters=(
                "person",
            ),
            objects=(
                "old key",
            ),
            places=(
                "abandoned house",
            )
        )
        relations = NarrativeRelations(
            relations=(
                "person finds old key",
                "house contains old key",
            )
        )
        conflict = NarrativeConflict(
            tension="uncertainty"
        )
        concepts = NarrativeConcepts(
            explicit=(
                "discovery",
            ),
            contextual=(
                "abandonment",
                "past",
            )
        )
        symbols = ExplicitSymbols(
            symbols=(
                "old key",
            )
        )
        continuity = NarrativeContinuity(
            prepares=(
                "possible later use of the key",
            )
        )
        reading = NarrativeReading(
            facts=facts,
            event=event,
            context=context,
            change=change,
            function=function,
            entities=entities,
            relations=relations,
            conflict=conflict,
            concepts=concepts,
            explicit_symbols=symbols,
            continuity=continuity
        )

        self.assertIs(
            reading.facts,
            facts
        )
        self.assertEqual(
            reading.event.action,
            "finds"
        )
        self.assertEqual(
            reading.function.primary,
            "discovery"
        )
        self.assertEqual(
            reading.continuity.prepares,
            (
                "possible later use of the key",
            )
        )

    def test_narrative_reading_is_immutable(self):
        reading = NarrativeReading()

        with self.assertRaises(
            FrozenInstanceError
        ):
            reading.facts = NarrativeFacts(
                stated=(
                    "changed",
                )
            )

    def test_narrative_reading_is_only_an_aggregator(self):
        self.assertEqual(
            tuple(
                field.name
                for field in fields(
                    NarrativeReading
                )
            ),
            (
                "facts",
                "event",
                "context",
                "change",
                "function",
                "entities",
                "relations",
                "conflict",
                "concepts",
                "explicit_symbols",
                "continuity",
            )
        )

    def test_public_domain_imports_expose_narrative_reading_models(self):
        for model in NARRATIVE_READING_MODELS:
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
            domain.NarrativeConfidence,
            NarrativeConfidence
        )

    def test_narrative_reading_domain_has_no_backend_runtime_or_prompt_terms(self):
        source = inspect.getsource(
            __import__(
                "app.domain.narrative_reading",
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
            "prompt",
            "payload",
            "workflow",
            "backend",
            "runtime",
            "camera",
            "lighting",
            "color_palette",
            "visual_bible",
            "output_path",
            "file_path",
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

    def test_narrative_reading_models_have_no_custom_public_methods(self):
        for model in NARRATIVE_READING_MODELS:
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

    def test_narrative_event_owns_only_approved_fields(self):
        self.assertEqual(
            tuple(
                field.name
                for field in fields(
                    NarrativeEvent
                )
            ),
            (
                "action",
                "subject",
                "object",
                "initial_state",
                "final_state",
                "environment",
                "time_context",
                "key_objects",
                "spatial_relationships",
                "continuity_links",
                "abstract_source",
                "visual_constraints",
                "visual_truth_status",
                "source_model",
                "confidence",
            )
        )

    def test_narrative_concepts_distinguish_explicit_and_contextual(self):
        concepts = NarrativeConcepts(
            explicit=(
                "discovery",
            ),
            contextual=(
                "mystery",
            )
        )

        self.assertEqual(
            concepts.explicit,
            (
                "discovery",
            )
        )
        self.assertEqual(
            concepts.contextual,
            (
                "mystery",
            )
        )


if __name__ == "__main__":
    unittest.main()
