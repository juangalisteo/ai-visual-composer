import inspect
import unittest
from dataclasses import FrozenInstanceError, is_dataclass

from app.domain import (
    AttentionalIntention,
    CognitiveIntention,
    ColorSystem,
    CommunicativeIntention,
    CompositionPrinciples,
    ContinuityPrinciples,
    CreativeLimits,
    EmotionalIntention,
    ExplicitSymbols,
    Identity,
    Intention,
    LightingPrinciples,
    NarrativeChange,
    NarrativeConcepts,
    NarrativeConflict,
    NarrativeContinuity,
    NarrativeEntities,
    NarrativeEvent,
    NarrativeFacts,
    NarrativeFunction,
    NarrativeIntention,
    NarrativeReading,
    NarrativeRelations,
    NegativeIntention,
    PhotographyPrinciples,
    QualityCriteria,
    RealismAndAbstraction,
    SymbolicIntention,
    SymbolicSystem,
    TextureAndMateriality,
    TransformativeIntention,
    VisualBible,
    VisualBrief,
    VisualPhilosophy,
    CinematicLanguage,
)
from app.visual_direction import (
    EffectiveVisualBrief,
    VisualBriefFieldOrigin,
    VisualBriefTrace,
    VisualDirectionConflict,
    VisualDirectionInput,
    VisualDirector2,
)


def visual_bible(
    forbidden_symbols=()
):
    return VisualBible(
        philosophy=VisualPhilosophy(
            beauty="sober"
        ),
        identity=Identity(
            visual_statement="contemplative symbolic realism"
        ),
        cinematic_language=CinematicLanguage(
            rhythm="slow"
        ),
        realism_and_abstraction=RealismAndAbstraction(
            realism_level="grounded"
        ),
        symbolic_system=SymbolicSystem(
            allowed_symbols=(
                "key",
            ),
            forbidden_symbols=forbidden_symbols
        ),
        composition=CompositionPrinciples(
            hierarchy="one clear meaning first"
        ),
        photography=PhotographyPrinciples(
            point_of_view="observational"
        ),
        lighting=LightingPrinciples(
            atmosphere="subtle"
        ),
        color=ColorSystem(
            dominant_temperature="warm neutral"
        ),
        texture_and_materiality=TextureAndMateriality(
            detail="credible"
        ),
        continuity=ContinuityPrinciples(
            atmosphere="quiet",
            symbols="controlled recurrence"
        ),
        creative_limits=CreativeLimits(),
        quality=QualityCriteria(
            coherence="belongs to the whole",
            belonging="consistent with philosophy"
        ),
    )


def narrative_reading():
    return NarrativeReading(
        facts=NarrativeFacts(
            stated=(
                "A person gives an old key to another person.",
            )
        ),
        event=NarrativeEvent(
            action="gives",
            subject="person",
            object="old key",
            initial_state="key held by giver",
            final_state="key received"
        ),
        change=NarrativeChange(
            changes=(
                "key changes hands",
            ),
            change_type="transfer"
        ),
        function=NarrativeFunction(
            primary="threshold"
        ),
        entities=NarrativeEntities(
            characters=(
                "giver",
                "receiver",
            ),
            objects=(
                "old key",
            )
        ),
        relations=NarrativeRelations(
            relations=(
                "giver transfers key to receiver",
            )
        ),
        conflict=NarrativeConflict(
            tension="uncertain consequence"
        ),
        concepts=NarrativeConcepts(
            contextual=(
                "responsibility",
                "threshold",
            )
        ),
        explicit_symbols=ExplicitSymbols(
            symbols=(
                "old key",
            )
        ),
        continuity=NarrativeContinuity(
            prepares=(
                "future consequence of the key",
            )
        ),
    )


def intention():
    return Intention(
        communicative=CommunicativeIntention(
            understanding="receiving the key implies accepting responsibility"
        ),
        emotional=EmotionalIntention(
            desired_effect="contained solemnity",
            emotional_quality="charged stillness",
            intensity="restrained"
        ),
        cognitive=CognitiveIntention(
            question="what consequence has just been activated"
        ),
        narrative=NarrativeIntention(
            purpose="initiate a new responsibility",
            function="threshold event"
        ),
        symbolic=SymbolicIntention(
            meaning="the key acts as threshold and burden",
            allowed_readings=(
                "access",
                "responsibility",
            ),
            ambiguity="whether the gesture protects or compromises remains open"
        ),
        transformative=TransformativeIntention(
            before="physical exchange",
            after="point of no return",
            shift="object transfer becomes consequence"
        ),
        attentional=AttentionalIntention(
            focus="the act of accepting",
            priority="consequence over object"
        ),
        negative=NegativeIntention(
            avoid_interpretations=(
                "casual handoff",
                "romantic gesture",
            )
        ),
    )


class VisualDirectionTest(unittest.TestCase):

    def test_visual_direction_models_are_passive_dataclasses(self):
        for model in (
            VisualDirectionInput,
            VisualBriefFieldOrigin,
            VisualBriefTrace,
            VisualDirectionConflict,
            EffectiveVisualBrief,
        ):
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

    def test_effective_visual_brief_is_immutable(self):
        effective = VisualDirector2().resolve(
            VisualDirectionInput(
                visual_bible=visual_bible(),
                narrative_reading=narrative_reading(),
                intention=intention()
            )
        )

        with self.assertRaises(
            FrozenInstanceError
        ):
            effective.fingerprint = "changed"

    def test_resolves_visual_brief_from_three_cognitive_layers(self):
        effective = VisualDirector2().resolve(
            VisualDirectionInput(
                visual_bible=visual_bible(),
                narrative_reading=narrative_reading(),
                intention=intention()
            )
        )

        brief = effective.visual_brief

        self.assertIsInstance(
            brief,
            VisualBrief
        )
        self.assertEqual(
            brief.primary_subject,
            "person"
        )
        self.assertEqual(
            brief.secondary_subject,
            "old key"
        )
        self.assertEqual(
            brief.attention_focus,
            "the act of accepting"
        )
        self.assertEqual(
            brief.visual_priority,
            "consequence over object"
        )
        self.assertIn(
            "threshold and burden",
            brief.visual_reading
        )
        self.assertIn(
            "contemplative symbolic realism",
            brief.visual_bible_coherence
        )

    def test_visual_brief_contains_no_prompt_or_backend_fields(self):
        field_names = set(
            VisualBrief.__dataclass_fields__
        )

        forbidden = {
            "prompt",
            "positive_prompt",
            "negative_prompt",
            "payload",
            "workflow",
            "backend",
            "comfyui",
            "model",
        }

        self.assertTrue(
            forbidden.isdisjoint(
                field_names
            )
        )

    def test_resolution_is_deterministic(self):
        context = VisualDirectionInput(
            visual_bible=visual_bible(),
            narrative_reading=narrative_reading(),
            intention=intention()
        )

        first = VisualDirector2().resolve(
            context
        )
        second = VisualDirector2().resolve(
            context
        )

        self.assertEqual(
            first.visual_brief,
            second.visual_brief
        )
        self.assertEqual(
            first.fingerprint,
            second.fingerprint
        )

    def test_fingerprint_changes_when_effective_brief_changes(self):
        first = VisualDirector2().resolve(
            VisualDirectionInput(
                visual_bible=visual_bible(),
                narrative_reading=narrative_reading(),
                intention=intention()
            )
        )
        changed_intention = Intention(
            emotional=EmotionalIntention(
                desired_effect="quiet dread"
            )
        )
        second = VisualDirector2().resolve(
            VisualDirectionInput(
                visual_bible=visual_bible(),
                narrative_reading=narrative_reading(),
                intention=changed_intention
            )
        )

        self.assertNotEqual(
            first.fingerprint,
            second.fingerprint
        )

    def test_trace_records_field_origins(self):
        effective = VisualDirector2().resolve(
            VisualDirectionInput(
                visual_bible=visual_bible(),
                narrative_reading=narrative_reading(),
                intention=intention()
            )
        )

        origins = {
            origin.field: origin.source_layer
            for origin in effective.trace.field_origins
        }

        self.assertEqual(
            origins["primary_subject"],
            "narrative_reading"
        )
        self.assertEqual(
            origins["attention_focus"],
            "intention"
        )
        self.assertEqual(
            origins["scene_rhythm"],
            "visual_bible"
        )

    def test_detects_visual_bible_intention_conflict(self):
        conflicting = VisualDirector2().resolve(
            VisualDirectionInput(
                visual_bible=visual_bible(
                    forbidden_symbols=(
                        "responsibility",
                    )
                ),
                narrative_reading=narrative_reading(),
                intention=intention()
            )
        )

        self.assertEqual(
            conflicting.conflicts[0].conflict_type,
            "forbidden_symbolic_reading"
        )
        self.assertEqual(
            conflicting.conflicts[0].source_layers,
            (
                "visual_bible",
                "intention",
            )
        )

    def test_detects_missing_narrative_anchor_conflict(self):
        effective = VisualDirector2().resolve(
            VisualDirectionInput(
                visual_bible=visual_bible(),
                narrative_reading=NarrativeReading(),
                intention=Intention(
                    attentional=AttentionalIntention(
                        focus="acceptance"
                    )
                )
            )
        )

        self.assertEqual(
            effective.conflicts[0].conflict_type,
            "missing_narrative_anchor"
        )

    def test_visual_direction_has_no_runtime_dependencies(self):
        source = inspect.getsource(
            __import__(
                "app.visual_direction",
                fromlist=[
                    "x"
                ]
            )
        )
        forbidden = (
            "ImageBuilder",
            "ImagePromptSystem",
            "ComfyUIBackend",
            "ImageManifestWriter",
            "positive_prompt",
            "negative_prompt",
            "payload",
            "workflow",
            "manifest",
            "requests",
            "urllib",
            "FFmpeg",
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
