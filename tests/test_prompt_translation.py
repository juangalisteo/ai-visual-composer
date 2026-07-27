import inspect
import unittest
from dataclasses import FrozenInstanceError, is_dataclass
from pathlib import Path

from app.cinematic_direction import create_cinematic_direction_set
from app.color_direction import ColorDirection
from app.composition_direction import CompositionDirection
from app.continuity_direction import ContinuityDirection
from app.domain import (
    ColorPlan,
    CompositionPlan,
    LightingPlan,
    MotionSense,
    PhotographyPlan,
    StagingPlan,
    VisualBrief,
    VisualStrategy,
)
from app.lighting_direction import LightingDirection
from app.movement_direction import MovementDirection
from app.photography_direction import PhotographyDirection
from app.prompt_translation import (
    BackendPrompt,
    BackendPromptInstruction,
    BackendPromptTrace,
    BackendPromptTraceItem,
    PromptTranslator,
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
            narrative_composition="threshold event",
            visual_priority="consequence over object",
            primary_subject="person",
            secondary_subject="old key",
            attention_focus="the act of accepting",
            dominant_visual_intention="initiate a new responsibility",
            visual_reading="the key acts as threshold and burden",
            scene_rhythm="slow | restrained",
            symbolic_weight="access | responsibility",
            visual_continuity="quiet recurrence",
            visual_bible_coherence="contemplative symbolic realism",
            narrative_coherence="key changes hands",
            intention_coherence="accepting responsibility",
            visual_strategy=VisualStrategy(
                representation_approach="grounded symbolic image",
                realism_level="grounded",
                symbolism_degree="restrained",
                visual_limits=(
                    "avoid spectacle",
                    "avoid spectacle",
                )
            ),
            staging=StagingPlan(
                main_subject="receiver",
                environment="quiet interior",
                significant_objects=(
                    "old key",
                )
            ),
            photography=PhotographyPlan(
                point_of_view="observational",
                emotional_distance="respectful"
            ),
            composition=CompositionPlan(
                visual_hierarchy="gesture first",
                framing="balanced"
            ),
            lighting=LightingPlan(
                source="motivated soft source",
                quality="diffuse"
            ),
            color=ColorPlan(
                temperature="warm neutral",
                palette=(
                    "deep graphite",
                    "soft gold",
                )
            ),
            motion=MotionSense(
                latent_energy="contained",
                rhythm="slow"
            ),
            continuity_relationship="continues the threshold motif"
        ),
        trace=VisualBriefTrace(),
        conflicts=(),
        fingerprint="visual-brief-fingerprint",
        source_id="scene_001",
        source_version="1.0.0",
    )


def cinematic_direction_set():
    return create_cinematic_direction_set(
        photography=PhotographyDirection(
            dominant_photographic_language="observational intimacy",
            fingerprint="photography-fingerprint"
        ),
        lighting=LightingDirection(
            dominant_lighting="motivated soft source",
            fingerprint="lighting-fingerprint"
        ),
        composition=CompositionDirection(
            dominant_composition="hands first",
            fingerprint="composition-fingerprint"
        ),
        color=ColorDirection(
            dominant_palette="muted amber",
            fingerprint="color-fingerprint"
        ),
        movement=MovementDirection(
            dominant_movement="inward movement",
            fingerprint="movement-fingerprint"
        ),
        continuity=ContinuityDirection(
            visual_continuity="recurring object",
            fingerprint="continuity-fingerprint"
        ),
    )


class PromptTranslationTest(unittest.TestCase):

    def test_prompt_translation_models_are_passive_dataclasses(self):
        for model in (
            BackendPromptInstruction,
            BackendPromptTraceItem,
            BackendPromptTrace,
            BackendPrompt,
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

    def test_backend_prompt_is_immutable(self):
        prompt = PromptTranslator().translate(
            effective_visual_brief()
        )

        with self.assertRaises(
            FrozenInstanceError
        ):
            prompt.fingerprint = "changed"

    def test_translates_visual_brief_fields_into_backend_neutral_instructions(self):
        prompt = PromptTranslator().translate(
            effective_visual_brief()
        )
        by_source = {
            instruction.source_field: instruction
            for instruction in prompt.instructions
        }

        self.assertEqual(
            by_source["VisualBrief.visible_content"].value,
            "A person receives an old key."
        )
        self.assertEqual(
            by_source["VisualBrief.photography.point_of_view"].category,
            "photography"
        )
        self.assertEqual(
            by_source["VisualBrief.color.palette"].value,
            "deep graphite | soft gold"
        )
        self.assertEqual(
            by_source["VisualBrief.visual_strategy.visual_limits"].value,
            "avoid spectacle"
        )

    def test_translation_preserves_meaning_without_new_decisions(self):
        prompt = PromptTranslator().translate(
            effective_visual_brief()
        )
        values = tuple(
            instruction.value
            for instruction in prompt.instructions
        )

        self.assertIn(
            "threshold event",
            values
        )
        self.assertIn(
            "consequence over object",
            values
        )
        self.assertIn(
            "the key acts as threshold and burden",
            values
        )
        self.assertNotIn(
            "ComfyUI",
            values
        )
        self.assertNotIn(
            "Flux",
            values
        )

    def test_translation_is_deterministic(self):
        effective = effective_visual_brief()

        first = PromptTranslator().translate(
            effective
        )
        second = PromptTranslator().translate(
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

    def test_cinematic_set_enriches_translation_when_provided(self):
        prompt = PromptTranslator().translate(
            effective_visual_brief(),
            cinematic_direction_set=cinematic_direction_set(),
        )
        by_source = {
            instruction.source_field: instruction
            for instruction in prompt.instructions
        }

        self.assertEqual(
            by_source["CinematicDirectionSet.photography.dominant_photographic_language"].value,
            "observational intimacy"
        )
        self.assertEqual(
            by_source["CinematicDirectionSet.photography.dominant_photographic_language"].category,
            "cinematic_photography"
        )
        self.assertEqual(
            by_source["CinematicDirectionSet.color.dominant_palette"].value,
            "muted amber"
        )
        self.assertIn(
            "VisualBrief.visible_content",
            by_source
        )

    def test_cinematic_translation_trace_keeps_direction_and_set_fingerprints(self):
        direction_set = cinematic_direction_set()
        prompt = PromptTranslator().translate(
            effective_visual_brief(),
            cinematic_direction_set=direction_set,
        )
        trace = {
            item.instruction_id: item
            for item in prompt.trace.items
        }

        self.assertEqual(
            trace["cinematic_photography_dominant_photographic_language"].source_fields,
            (
                "CinematicDirectionSet.photography.dominant_photographic_language",
                "CinematicDirectionSet.photography.fingerprint",
                "CinematicDirectionSet.fingerprint",
            )
        )
        self.assertEqual(
            trace["cinematic_photography_dominant_photographic_language"].transformation,
            "translate_cinematic_direction_field"
        )
        self.assertNotEqual(
            direction_set.fingerprint,
            ""
        )

    def test_cinematic_translation_is_deterministic(self):
        effective = effective_visual_brief()
        direction_set = cinematic_direction_set()

        first = PromptTranslator().translate(
            effective,
            cinematic_direction_set=direction_set,
        )
        second = PromptTranslator().translate(
            effective,
            cinematic_direction_set=direction_set,
        )

        self.assertEqual(
            first,
            second
        )
        self.assertEqual(
            first.fingerprint,
            second.fingerprint
        )

    def test_cinematic_translation_fingerprint_changes_when_direction_set_changes(self):
        effective = effective_visual_brief()
        first = PromptTranslator().translate(
            effective,
            cinematic_direction_set=cinematic_direction_set(),
        )
        changed_set = create_cinematic_direction_set(
            photography=PhotographyDirection(
                dominant_photographic_language="distant observation",
                fingerprint="changed-photography-fingerprint"
            )
        )
        second = PromptTranslator().translate(
            effective,
            cinematic_direction_set=changed_set,
        )

        self.assertNotEqual(
            first.fingerprint,
            second.fingerprint
        )

    def test_fingerprint_changes_when_effective_brief_changes(self):
        first = PromptTranslator().translate(
            effective_visual_brief()
        )
        changed = EffectiveVisualBrief(
            visual_brief=VisualBrief(
                visible_content="A different visible event."
            ),
            trace=VisualBriefTrace(),
            conflicts=(),
            fingerprint="changed-brief",
        )
        second = PromptTranslator().translate(
            changed
        )

        self.assertNotEqual(
            first.fingerprint,
            second.fingerprint
        )

    def test_trace_records_source_fields_and_transformations(self):
        prompt = PromptTranslator().translate(
            effective_visual_brief()
        )
        trace = {
            item.instruction_id: item
            for item in prompt.trace.items
        }

        self.assertEqual(
            prompt.trace.source_visual_brief_fingerprint,
            "visual-brief-fingerprint"
        )
        self.assertEqual(
            trace["visible_content"].source_fields,
            (
                "VisualBrief.visible_content",
            )
        )
        self.assertEqual(
            trace["color_palette"].transformation,
            "normalize_sequence"
        )

    def test_output_contains_no_backend_specific_fields(self):
        field_names = (
            set(
                BackendPrompt.__dataclass_fields__
            )
            | set(
                BackendPromptInstruction.__dataclass_fields__
            )
        )
        forbidden = {
            "comfyui",
            "flux",
            "sdxl",
            "midjourney",
            "payload",
            "workflow",
            "node",
            "url",
            "endpoint",
            "api_key",
        }

        self.assertTrue(
            forbidden.isdisjoint(
                {
                    field.lower()
                    for field in field_names
                }
            )
        )

    def test_prompt_translation_has_no_runtime_dependencies(self):
        source = inspect.getsource(
            __import__(
                "app.prompt_translation",
                fromlist=[
                    "x"
                ]
            )
        )
        forbidden = (
            "VisualBible",
            "NarrativeReading",
            "Intention",
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
            "Flux",
            "ComfyUI",
        )

        for item in forbidden:
            with self.subTest(
                item=item
            ):
                self.assertNotIn(
                    item,
                    source
                )

    def test_runtime_imports_prompt_translation_only_from_image_builder(self):
        paths_with_import = []
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
                source = path.read_text(
                    encoding="utf-8"
                )
                if "app.prompt_translation" in source:
                    paths_with_import.append(
                        path.as_posix()
                    )

        self.assertEqual(
            [
                "app/modules/images/image_builder.py",
            ],
            paths_with_import
        )


if __name__ == "__main__":
    unittest.main()
