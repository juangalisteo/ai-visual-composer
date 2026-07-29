import inspect
import unittest
from dataclasses import FrozenInstanceError, is_dataclass
from pathlib import Path

from app.continuity_direction import (
    ContinuityDecisionTrace,
    ContinuityDirection,
    ContinuityDirectionTrace,
    ContinuityDirector,
)
from app.domain import (
    EffectiveVisualBrief,
    ColorPlan,
    CompositionPlan,
    LightingPlan,
    MotionSense,
    PhotographyPlan,
    StagingPlan,
    VisualStrategy,
)


def effective_brief():
    return EffectiveVisualBrief(
            visible_content="A person receives an old key.",
            visual_priority="gesture before object",
            primary_subject="receiver",
            secondary_subject="giver",
            attention_focus="the old key",
            visual_reading="the key links this scene to the next threshold",
            symbolic_weight="key as threshold and burden",
            visual_continuity="recurring central object",
            visual_bible_coherence="contemplative symbolic realism",
            narrative_coherence="key changes hands",
            intention_coherence="responsibility accepted quietly",
            visual_strategy=VisualStrategy(
                representation_approach="grounded symbolic image",
                realism_level="grounded",
                world_style="quiet premium realism"
            ),
            staging=StagingPlan(
                main_subject="receiver",
                environment="quiet interior",
                spatial_relationship="two figures close around the object",
                significant_objects=(
                    "old key",
                ),
                human_presence="same grounded figures"
            ),
            photography=PhotographyPlan(
                point_of_view="observational"
            ),
            composition=CompositionPlan(
                visual_hierarchy="hands first, faces second",
                balance="quiet asymmetrical balance",
                figure_ground_relationship="clear subject separation"
            ),
            lighting=LightingPlan(
                source="motivated soft source",
                motivation="credible interior light",
                atmosphere="subtle charged stillness",
                visibility="clear but restrained"
            ),
            color=ColorPlan(
                temperature="warm restraint",
                harmony="soft gold harmony",
                emotional_evolution="warmth becomes responsibility",
                visual_identity_relationship="earth-toned contemplative identity"
            ),
            motion=MotionSense(
                latent_energy="contained transfer energy",
                rhythm="slow visual pulse",
                stability="stable held frame",
                progression_or_suspension="suspended before consequence"
            ),
            continuity_relationship="object carries continuity into next scene",
        fingerprint="visual-brief-fingerprint",
    )


class ContinuityDirectionTest(unittest.TestCase):

    def test_continuity_direction_models_are_passive_dataclasses(self):
        for model in (
            ContinuityDecisionTrace,
            ContinuityDirectionTrace,
            ContinuityDirection,
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

    def test_continuity_direction_is_immutable(self):
        direction = ContinuityDirector().resolve(
            effective_brief()
        )

        with self.assertRaises(
            FrozenInstanceError
        ):
            direction.visual_continuity = "changed"

    def test_resolves_continuity_direction_from_effective_brief(self):
        direction = ContinuityDirector().resolve(
            effective_brief()
        )

        self.assertEqual(
            direction.visual_continuity,
            "recurring central object | object carries continuity into next scene | contemplative symbolic realism"
        )
        self.assertEqual(
            direction.identity_persistence,
            "contemplative symbolic realism | earth-toned contemplative identity | quiet premium realism"
        )
        self.assertEqual(
            direction.character_consistency,
            "receiver | giver | same grounded figures"
        )
        self.assertEqual(
            direction.key_element_preservation,
            "key as threshold and burden | the old key | old key"
        )
        self.assertEqual(
            direction.visual_transition,
            "object carries continuity into next scene | warmth becomes responsibility | suspended before consequence"
        )

    def test_resolution_is_deterministic(self):
        effective = effective_brief()

        first = ContinuityDirector().resolve(
            effective
        )
        second = ContinuityDirector().resolve(
            effective
        )

        self.assertEqual(
            first,
            second
        )
        self.assertEqual(
            first.fingerprint,
            second.fingerprint
        )

    def test_fingerprint_changes_when_effective_brief_changes(self):
        first = ContinuityDirector().resolve(
            effective_brief()
        )
        changed = EffectiveVisualBrief(
                visible_content="A different resolved scene.",
                visual_continuity="new continuity cue",
            fingerprint="changed-brief",
        )
        second = ContinuityDirector().resolve(
            changed
        )

        self.assertNotEqual(
            first.fingerprint,
            second.fingerprint
        )

    def test_trace_records_origin_transformation_and_justification(self):
        direction = ContinuityDirector().resolve(
            effective_brief()
        )
        decisions = {
            decision.field: decision
            for decision in direction.trace.decisions
        }

        self.assertEqual(
            direction.trace.source_effective_brief_fingerprint,
            "visual-brief-fingerprint"
        )
        self.assertEqual(
            decisions["visual_transition"].source_fields,
            (
                "EffectiveVisualBrief.continuity_relationship",
                "EffectiveVisualBrief.color.emotional_evolution",
                "EffectiveVisualBrief.motion.progression_or_suspension",
            )
        )
        self.assertEqual(
            decisions["visual_transition"].transformation,
            "select_and_combine_resolved_effective_brief_fields"
        )
        self.assertIn(
            "visual transition",
            decisions["visual_transition"].justification
        )

    def test_empty_input_does_not_invent_continuity_direction(self):
        direction = ContinuityDirector().resolve(
            EffectiveVisualBrief(visible_content="", fingerprint="empty")
        )

        self.assertEqual(
            direction.visual_continuity,
            ""
        )
        self.assertEqual(
            direction.trace.decisions,
            ()
        )

    def test_continuity_direction_contains_no_technical_or_prompt_fields(self):
        field_names = set(
            ContinuityDirection.__dataclass_fields__
        )
        forbidden = {
            "prompt",
            "payload",
            "workflow",
            "backend",
            "keyframe",
            "coordinate",
            "render",
            "engine",
            "provider",
        }

        self.assertTrue(
            forbidden.isdisjoint(
                {
                    field.lower()
                    for field in field_names
                }
            )
        )

    def test_continuity_direction_has_no_runtime_dependencies(self):
        source = inspect.getsource(
            __import__(
                "app.continuity_direction",
                fromlist=[
                    "x"
                ]
            )
        )
        forbidden = (
            "VisualBible",
            "NarrativeReading",
            "Intention",
            "PromptTranslator",
            "BackendPrompt",
            "BackendAdapter",
            "ImageBuilder",
            "ImagePromptSystem",
            "ComfyUIBackend",
            "ImageManifestWriter",
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

    def test_runtime_does_not_import_continuity_direction(self):
        source = ""
        for directory in (
            "app/modules",
            "app/managers",
            "app/controllers",
            "app/core",
        ):
            for path in Path(
                directory
            ).rglob(
                "*.py"
            ):
                source += path.read_text(
                    encoding="utf-8"
                )

        self.assertNotIn(
            "app.continuity_direction",
            source
        )


if __name__ == "__main__":
    unittest.main()
