import inspect
import unittest
from dataclasses import FrozenInstanceError, is_dataclass
from pathlib import Path

from app.domain import (
    CompositionPlan,
    LightingPlan,
    MotionSense,
    PhotographyPlan,
    StagingPlan,
    VisualBrief,
    VisualStrategy,
)
from app.movement_direction import (
    MovementDecisionTrace,
    MovementDirection,
    MovementDirectionTrace,
    MovementDirector,
)
from app.visual_direction import (
    EffectiveVisualBrief,
    VisualBriefTrace,
)


def effective_visual_brief():
    return EffectiveVisualBrief(
        visual_brief=VisualBrief(
            visible_content="A person receives an old key.",
            felt_experience="contained solemnity",
            visual_priority="gesture before object",
            primary_subject="receiver",
            attention_focus="the key passing between hands",
            dominant_visual_intention="acceptance of responsibility",
            visual_reading="the eye moves from hands to faces",
            scene_rhythm="slow held rhythm",
            symbolic_weight="access and responsibility",
            visual_continuity="recurring central object",
            visual_bible_coherence="contemplative symbolic realism",
            narrative_coherence="key changes hands",
            intention_coherence="responsibility accepted quietly",
            visual_strategy=VisualStrategy(
                representation_approach="grounded symbolic image",
                realism_level="grounded"
            ),
            staging=StagingPlan(
                main_subject="receiver",
                action_or_state="exchange held in stillness",
                spatial_relationship="two figures close around the object"
            ),
            photography=PhotographyPlan(
                point_of_view="observational",
                emotional_distance="near but restrained"
            ),
            composition=CompositionPlan(
                visual_hierarchy="hands first, faces second",
                balance="quiet asymmetrical balance",
                reading_direction="hands to faces",
                spatial_tension="soft tension between giver and receiver",
                figure_ground_relationship="clear subject separation"
            ),
            lighting=LightingPlan(
                source="motivated soft source",
                atmosphere="subtle charged stillness"
            ),
            motion=MotionSense(
                latent_energy="contained transfer energy",
                rhythm="slow visual pulse",
                stillness="charged stillness",
                direction="inward movement",
                stability="stable held frame",
                progression_or_suspension="suspended before consequence",
                visual_breathing="quiet breathing space"
            ),
            continuity_relationship="object carries continuity into next scene",
        ),
        trace=VisualBriefTrace(),
        conflicts=(),
        fingerprint="visual-brief-fingerprint",
        source_id="scene_001",
        source_version="1.0.0",
    )


class MovementDirectionTest(unittest.TestCase):

    def test_movement_direction_models_are_passive_dataclasses(self):
        for model in (
            MovementDecisionTrace,
            MovementDirectionTrace,
            MovementDirection,
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

    def test_movement_direction_is_immutable(self):
        direction = MovementDirector().resolve(
            effective_visual_brief()
        )

        with self.assertRaises(
            FrozenInstanceError
        ):
            direction.dominant_movement = "changed"

    def test_resolves_movement_direction_from_effective_visual_brief(self):
        direction = MovementDirector().resolve(
            effective_visual_brief()
        )

        self.assertEqual(
            direction.dominant_movement,
            "inward movement | contained transfer energy | exchange held in stillness"
        )
        self.assertEqual(
            direction.movement_energy,
            "contained transfer energy | slow held rhythm | acceptance of responsibility"
        )
        self.assertEqual(
            direction.stability,
            "stable held frame | quiet asymmetrical balance | observational"
        )
        self.assertEqual(
            direction.displacement_rhythm,
            "slow visual pulse | slow held rhythm | hands to faces"
        )
        self.assertEqual(
            direction.spatial_coherence,
            "two figures close around the object | clear subject separation | key changes hands"
        )

    def test_resolution_is_deterministic(self):
        effective = effective_visual_brief()

        first = MovementDirector().resolve(
            effective
        )
        second = MovementDirector().resolve(
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
        first = MovementDirector().resolve(
            effective_visual_brief()
        )
        changed = EffectiveVisualBrief(
            visual_brief=VisualBrief(
                visible_content="A different resolved scene.",
                scene_rhythm="accelerating rhythm"
            ),
            trace=VisualBriefTrace(),
            conflicts=(),
            fingerprint="changed-brief",
        )
        second = MovementDirector().resolve(
            changed
        )

        self.assertNotEqual(
            first.fingerprint,
            second.fingerprint
        )

    def test_trace_records_origin_transformation_and_justification(self):
        direction = MovementDirector().resolve(
            effective_visual_brief()
        )
        decisions = {
            decision.field: decision
            for decision in direction.trace.decisions
        }

        self.assertEqual(
            direction.trace.source_visual_brief_fingerprint,
            "visual-brief-fingerprint"
        )
        self.assertEqual(
            decisions["narrative_movement_direction"].source_fields,
            (
                "VisualBrief.motion.direction",
                "VisualBrief.visual_reading",
                "VisualBrief.dominant_visual_intention",
            )
        )
        self.assertEqual(
            decisions["narrative_movement_direction"].transformation,
            "select_and_combine_resolved_visual_brief_fields"
        )
        self.assertIn(
            "without adding action",
            decisions["narrative_movement_direction"].justification
        )

    def test_empty_input_does_not_invent_movement_direction(self):
        direction = MovementDirector().resolve(
            EffectiveVisualBrief(
                visual_brief=VisualBrief(
                    visible_content=""
                ),
                trace=VisualBriefTrace(),
                conflicts=(),
                fingerprint="empty",
            )
        )

        self.assertEqual(
            direction.dominant_movement,
            ""
        )
        self.assertEqual(
            direction.trace.decisions,
            ()
        )

    def test_movement_direction_contains_no_technical_or_prompt_fields(self):
        field_names = set(
            MovementDirection.__dataclass_fields__
        )
        forbidden = {
            "prompt",
            "payload",
            "workflow",
            "backend",
            "keyframe",
            "fps",
            "curve",
            "coordinate",
            "velocity",
            "easing",
            "render",
            "engine",
        }

        self.assertTrue(
            forbidden.isdisjoint(
                {
                    field.lower()
                    for field in field_names
                }
            )
        )

    def test_movement_direction_has_no_runtime_dependencies(self):
        source = inspect.getsource(
            __import__(
                "app.movement_direction",
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

    def test_runtime_does_not_import_movement_direction(self):
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
            "app.movement_direction",
            source
        )


if __name__ == "__main__":
    unittest.main()
