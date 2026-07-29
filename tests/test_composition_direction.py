import inspect
import unittest
from dataclasses import FrozenInstanceError, is_dataclass
from pathlib import Path

from app.composition_direction import (
    CompositionDecisionTrace,
    CompositionDirection,
    CompositionDirectionTrace,
    CompositionDirector,
)
from app.domain import (
    EffectiveVisualBrief,
    CompositionPlan,
    LightingPlan,
    MotionSense,
    PhotographyPlan,
    StagingPlan,
)


def effective_brief():
    return EffectiveVisualBrief(
            visible_content="A person receives an old key.",
            felt_experience="contained solemnity",
            narrative_composition="threshold moment centered on the exchange",
            visual_priority="gesture before object",
            primary_subject="receiver",
            secondary_subject="giver",
            attention_focus="the key passing between hands",
            dominant_visual_intention="acceptance of responsibility",
            visual_reading="the eye moves from hands to faces",
            scene_rhythm="slow held rhythm",
            symbolic_weight="key as threshold and burden",
            visual_continuity="recurring central object",
            intention_coherence="responsibility accepted quietly",
            staging=StagingPlan(
                main_subject="receiver",
                environment="quiet interior",
                action_or_state="exchange held in stillness",
                spatial_relationship="two figures close around the object",
                narrative_distribution="meaning concentrated between both figures"
            ),
            photography=PhotographyPlan(
                point_of_view="observational",
                depth="layered but calm"
            ),
            composition=CompositionPlan(
                visual_hierarchy="hands first, faces second",
                framing="contained central framing",
                balance="quiet asymmetrical balance",
                negative_space="restrained silence around the exchange",
                reading_direction="hands to faces",
                spatial_tension="soft tension between giver and receiver",
                figure_ground_relationship="clear subject separation"
            ),
            lighting=LightingPlan(
                source="motivated soft source",
                volume="soft visible volume"
            ),
            motion=MotionSense(
                latent_energy="contained transfer energy",
                rhythm="slow visual pulse",
                direction="inward movement",
                stability="stable held frame"
            ),
            continuity_relationship="object carries continuity into next scene",
        fingerprint="visual-brief-fingerprint",
    )


class CompositionDirectionTest(unittest.TestCase):

    def test_composition_direction_models_are_passive_dataclasses(self):
        for model in (
            CompositionDecisionTrace,
            CompositionDirectionTrace,
            CompositionDirection,
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

    def test_composition_direction_is_immutable(self):
        direction = CompositionDirector().resolve(
            effective_brief()
        )

        with self.assertRaises(
            FrozenInstanceError
        ):
            direction.dominant_composition = "changed"

    def test_resolves_composition_direction_from_effective_brief(self):
        direction = CompositionDirector().resolve(
            effective_brief()
        )

        self.assertEqual(
            direction.dominant_composition,
            "hands first, faces second | threshold moment centered on the exchange | gesture before object"
        )
        self.assertEqual(
            direction.visual_balance,
            "quiet asymmetrical balance | clear subject separation"
        )
        self.assertEqual(
            direction.spatial_distribution,
            "meaning concentrated between both figures | two figures close around the object | quiet asymmetrical balance"
        )
        self.assertEqual(
            direction.compositional_hierarchy,
            "hands first, faces second | receiver | giver | the key passing between hands"
        )
        self.assertEqual(
            direction.visual_reading_direction,
            "hands to faces | the key passing between hands | the eye moves from hands to faces"
        )

    def test_resolution_is_deterministic(self):
        effective = effective_brief()

        first = CompositionDirector().resolve(
            effective
        )
        second = CompositionDirector().resolve(
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
        first = CompositionDirector().resolve(
            effective_brief()
        )
        changed = EffectiveVisualBrief(
                visible_content="A different resolved scene.",
                visual_priority="solitary figure",
            fingerprint="changed-brief",
        )
        second = CompositionDirector().resolve(
            changed
        )

        self.assertNotEqual(
            first.fingerprint,
            second.fingerprint
        )

    def test_trace_records_origin_transformation_and_justification(self):
        direction = CompositionDirector().resolve(
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
            decisions["visual_reading_direction"].source_fields,
            (
                "EffectiveVisualBrief.composition.reading_direction",
                "EffectiveVisualBrief.attention_focus",
                "EffectiveVisualBrief.visual_reading",
            )
        )
        self.assertEqual(
            decisions["visual_reading_direction"].transformation,
            "select_and_combine_resolved_effective_brief_fields"
        )
        self.assertIn(
            "read visually",
            decisions["visual_reading_direction"].justification
        )

    def test_empty_input_does_not_invent_composition_direction(self):
        direction = CompositionDirector().resolve(
            EffectiveVisualBrief(visible_content="", fingerprint="empty")
        )

        self.assertEqual(
            direction.dominant_composition,
            ""
        )
        self.assertEqual(
            direction.trace.decisions,
            ()
        )

    def test_composition_direction_contains_no_technical_or_prompt_fields(self):
        field_names = set(
            CompositionDirection.__dataclass_fields__
        )
        forbidden = {
            "prompt",
            "payload",
            "workflow",
            "backend",
            "coordinate",
            "position_x",
            "position_y",
            "render",
            "engine",
            "lens",
            "focal",
        }

        self.assertTrue(
            forbidden.isdisjoint(
                {
                    field.lower()
                    for field in field_names
                }
            )
        )

    def test_composition_direction_has_no_runtime_dependencies(self):
        source = inspect.getsource(
            __import__(
                "app.composition_direction",
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

    def test_runtime_does_not_import_composition_direction(self):
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
            "app.composition_direction",
            source
        )


if __name__ == "__main__":
    unittest.main()
