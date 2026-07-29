import inspect
import unittest
from dataclasses import FrozenInstanceError, is_dataclass
from pathlib import Path

from app.domain import (
    EffectiveVisualBrief,
    ColorPlan,
    CompositionPlan,
    LightingPlan,
    PhotographyPlan,
    StagingPlan,
    VisualStrategy,
)
from app.lighting_direction import (
    LightingDecisionTrace,
    LightingDirection,
    LightingDirectionTrace,
    LightingDirector,
)


def effective_brief():
    return EffectiveVisualBrief(
            visible_content="A person receives an old key.",
            felt_experience="contained solemnity",
            visual_priority="consequence over object",
            primary_subject="person",
            attention_focus="the act of accepting",
            dominant_visual_intention="initiate a new responsibility",
            visual_reading="the key acts as threshold and burden",
            symbolic_weight="access | responsibility",
            visual_continuity="quiet recurrence",
            visual_bible_coherence="contemplative symbolic realism",
            narrative_coherence="key changes hands",
            intention_coherence="accepting responsibility",
            visual_strategy=VisualStrategy(
                representation_approach="grounded symbolic image",
                realism_level="grounded"
            ),
            staging=StagingPlan(
                main_subject="receiver",
                environment="quiet interior",
                spatial_relationship="subject held close to the object"
            ),
            photography=PhotographyPlan(
                point_of_view="observational",
                depth="layered but calm",
                photographic_atmosphere="quiet photographic realism",
                light_volume_treatment="soft volume"
            ),
            composition=CompositionPlan(
                visual_hierarchy="gesture first",
                negative_space="controlled surrounding silence",
                figure_ground_relationship="clear separation"
            ),
            lighting=LightingPlan(
                source="motivated soft source",
                direction="sideward attention",
                quality="diffuse",
                hardness="soft",
                contrast="gentle contrast",
                motivation="credible interior light",
                atmosphere="subtle charged stillness",
                visibility="clear but restrained",
                volume="visible soft volume"
            ),
            color=ColorPlan(
                temperature="warm neutral",
                chromatic_contrast="cool shadows",
                harmony="soft gold harmony"
            ),
        fingerprint="visual-brief-fingerprint",
    )


class LightingDirectionTest(unittest.TestCase):

    def test_lighting_direction_models_are_passive_dataclasses(self):
        for model in (
            LightingDecisionTrace,
            LightingDirectionTrace,
            LightingDirection,
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

    def test_lighting_direction_is_immutable(self):
        direction = LightingDirector().resolve(
            effective_brief()
        )

        with self.assertRaises(
            FrozenInstanceError
        ):
            direction.dominant_lighting = "changed"

    def test_resolves_lighting_direction_from_effective_brief(self):
        direction = LightingDirector().resolve(
            effective_brief()
        )

        self.assertEqual(
            direction.dominant_lighting,
            "motivated soft source | credible interior light"
        )
        self.assertEqual(
            direction.luminous_atmosphere,
            "subtle charged stillness | quiet photographic realism | contained solemnity"
        )
        self.assertEqual(
            direction.perceived_contrast,
            "gentle contrast | consequence over object"
        )
        self.assertEqual(
            direction.softness_or_hardness,
            "diffuse | soft"
        )
        self.assertEqual(
            direction.luminous_hierarchy,
            "gesture first | person | the act of accepting"
        )

    def test_resolution_is_deterministic(self):
        effective = effective_brief()

        first = LightingDirector().resolve(
            effective
        )
        second = LightingDirector().resolve(
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
        first = LightingDirector().resolve(
            effective_brief()
        )
        changed = EffectiveVisualBrief(
                visible_content="A different resolved scene.",
                felt_experience="quiet dread",
            fingerprint="changed-brief",
        )
        second = LightingDirector().resolve(
            changed
        )

        self.assertNotEqual(
            first.fingerprint,
            second.fingerprint
        )

    def test_trace_records_origin_transformation_and_justification(self):
        direction = LightingDirector().resolve(
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
            decisions["conceptual_light_direction"].source_fields,
            (
                "EffectiveVisualBrief.lighting.direction",
                "EffectiveVisualBrief.attention_focus",
            )
        )
        self.assertEqual(
            decisions["conceptual_light_direction"].transformation,
            "select_and_combine_resolved_effective_brief_fields"
        )
        self.assertIn(
            "conceptual light orientation",
            decisions["conceptual_light_direction"].justification
        )

    def test_empty_input_does_not_invent_lighting_direction(self):
        direction = LightingDirector().resolve(
            EffectiveVisualBrief(visible_content="", fingerprint="empty")
        )

        self.assertEqual(
            direction.dominant_lighting,
            ""
        )
        self.assertEqual(
            direction.trace.decisions,
            ()
        )

    def test_lighting_direction_contains_no_technical_or_prompt_fields(self):
        field_names = set(
            LightingDirection.__dataclass_fields__
        )
        forbidden = {
            "prompt",
            "payload",
            "workflow",
            "backend",
            "lux",
            "kelvin",
            "intensity",
            "exposure",
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

    def test_lighting_direction_has_no_runtime_dependencies(self):
        source = inspect.getsource(
            __import__(
                "app.lighting_direction",
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

    def test_runtime_does_not_import_lighting_direction(self):
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
            "app.lighting_direction",
            source
        )


if __name__ == "__main__":
    unittest.main()
