import inspect
import unittest
from dataclasses import FrozenInstanceError, is_dataclass
from pathlib import Path

from app.color_direction import (
    ColorDecisionTrace,
    ColorDirection,
    ColorDirectionTrace,
    ColorDirector,
)
from app.domain import (
    ColorPlan,
    CompositionPlan,
    LightingPlan,
    PhotographyPlan,
    StagingPlan,
    VisualBrief,
    VisualStrategy,
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
            secondary_subject="giver",
            attention_focus="the key passing between hands",
            dominant_visual_intention="acceptance of responsibility",
            visual_reading="the key acts as threshold and burden",
            symbolic_weight="access and responsibility",
            visual_continuity="recurring central object",
            visual_bible_coherence="contemplative symbolic realism",
            narrative_coherence="key changes hands",
            intention_coherence="responsibility accepted quietly",
            visual_strategy=VisualStrategy(
                representation_approach="grounded symbolic image",
                realism_level="grounded",
                symbolism_degree="restrained symbolism",
                world_style="quiet premium realism"
            ),
            staging=StagingPlan(
                main_subject="receiver",
                environment="quiet interior",
                spatial_relationship="two figures close around the object"
            ),
            photography=PhotographyPlan(
                point_of_view="observational",
                photographic_atmosphere="quiet photographic realism"
            ),
            composition=CompositionPlan(
                visual_hierarchy="hands first, faces second",
                balance="quiet asymmetrical balance",
                spatial_tension="soft tension between giver and receiver",
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
                palette=(
                    "muted amber",
                    "soft umber",
                ),
                saturation="restrained saturation",
                chromatic_contrast="subtle cool shadows",
                harmony="soft gold harmony",
                rupture="faint metallic interruption",
                emotional_evolution="warmth becomes responsibility",
                visual_identity_relationship="earth-toned contemplative identity"
            ),
            continuity_relationship="object carries continuity into next scene",
        ),
        trace=VisualBriefTrace(),
        conflicts=(),
        fingerprint="visual-brief-fingerprint",
        source_id="scene_001",
        source_version="1.0.0",
    )


class ColorDirectionTest(unittest.TestCase):

    def test_color_direction_models_are_passive_dataclasses(self):
        for model in (
            ColorDecisionTrace,
            ColorDirectionTrace,
            ColorDirection,
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

    def test_color_direction_is_immutable(self):
        direction = ColorDirector().resolve(
            effective_visual_brief()
        )

        with self.assertRaises(
            FrozenInstanceError
        ):
            direction.dominant_palette = "changed"

    def test_resolves_color_direction_from_effective_visual_brief(self):
        direction = ColorDirector().resolve(
            effective_visual_brief()
        )

        self.assertEqual(
            direction.dominant_palette,
            "muted amber | soft umber | soft gold harmony | contemplative symbolic realism"
        )
        self.assertEqual(
            direction.color_harmony,
            "soft gold harmony | quiet premium realism"
        )
        self.assertEqual(
            direction.chromatic_contrast,
            "subtle cool shadows | faint metallic interruption | gesture before object"
        )
        self.assertEqual(
            direction.emotional_temperature,
            "warm restraint | contained solemnity | acceptance of responsibility"
        )
        self.assertEqual(
            direction.visual_coherence,
            "contemplative symbolic realism | key changes hands | responsibility accepted quietly"
        )

    def test_resolution_is_deterministic(self):
        effective = effective_visual_brief()

        first = ColorDirector().resolve(
            effective
        )
        second = ColorDirector().resolve(
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
        first = ColorDirector().resolve(
            effective_visual_brief()
        )
        changed = EffectiveVisualBrief(
            visual_brief=VisualBrief(
                visible_content="A different resolved scene.",
                visual_priority="distant horizon"
            ),
            trace=VisualBriefTrace(),
            conflicts=(),
            fingerprint="changed-brief",
        )
        second = ColorDirector().resolve(
            changed
        )

        self.assertNotEqual(
            first.fingerprint,
            second.fingerprint
        )

    def test_trace_records_origin_transformation_and_justification(self):
        direction = ColorDirector().resolve(
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
            decisions["chromatic_symbolism"].source_fields,
            (
                "VisualBrief.symbolic_weight",
                "VisualBrief.visual_reading",
                "VisualBrief.color.visual_identity_relationship",
            )
        )
        self.assertEqual(
            decisions["chromatic_symbolism"].transformation,
            "select_and_combine_resolved_visual_brief_fields"
        )
        self.assertIn(
            "without adding symbols",
            decisions["chromatic_symbolism"].justification
        )

    def test_empty_input_does_not_invent_color_direction(self):
        direction = ColorDirector().resolve(
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
            direction.dominant_palette,
            ""
        )
        self.assertEqual(
            direction.trace.decisions,
            ()
        )

    def test_color_direction_contains_no_technical_or_prompt_fields(self):
        field_names = set(
            ColorDirection.__dataclass_fields__
        )
        forbidden = {
            "prompt",
            "payload",
            "workflow",
            "backend",
            "lut",
            "hex",
            "rgb",
            "hsl",
            "kelvin",
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

    def test_color_direction_has_no_runtime_dependencies(self):
        source = inspect.getsource(
            __import__(
                "app.color_direction",
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

    def test_runtime_does_not_import_color_direction(self):
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
            "app.color_direction",
            source
        )


if __name__ == "__main__":
    unittest.main()
