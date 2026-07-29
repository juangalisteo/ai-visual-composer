import inspect
import unittest
from dataclasses import FrozenInstanceError, is_dataclass
from pathlib import Path

from app.cinematic_direction import create_cinematic_direction_set
from app.color_direction import ColorDirection
from app.composition_direction import CompositionDirection
from app.continuity_direction import ContinuityDirection
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
from app.lighting_direction import LightingDirection
from app.movement_direction import MovementDirection
from app.photography_direction import PhotographyDirection
from app.prompt_translation import (
    BackendPrompt,
    BackendPromptInstruction,
    BackendPromptTrace,
    BackendPromptTraceItem,
    PromptBudgetExceededError,
    PromptBudgetPolicy,
    PromptCompilationMetrics,
    PromptTranslator,
)
from app.visual_intelligence import VisualSynthesisOrchestrator
from tests.test_visual_synthesis_helpers import (
    analysis_and_reasoning,
    complete_scene,
)


def effective_brief():
    return EffectiveVisualBrief(
            visible_content="A person receives an old key.",
            visible_subject="person receiving an old key",
            visible_action="old key changes hands",
            visible_environment="quiet interior",
            time_context="late evening",
            key_objects=(
                "old key",
                "sealed letter",
            ),
            spatial_relationships=(
                "key between both hands",
            ),
            continuity_links=(
                "same old key",
            ),
            abstract_source="responsibility transferred",
            filmable_interpretation="a key changes hands in silence",
            visual_constraints=(
                "no readable text",
            ),
            visual_truth_status="structured",
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
            continuity_relationship="continues the threshold motif",
        fingerprint="visual-brief-fingerprint",
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


def all_trace_source_fields(
    prompt
):
    fields = []
    for item in prompt.trace.items:
        fields.extend(
            item.source_fields
        )
    return tuple(
        fields
    )


def instruction_by_source_field(
    prompt,
    source_field
):
    for instruction in prompt.instructions:
        if source_field in instruction.source_field:
            return instruction
    for instruction, trace_item in zip(
        prompt.instructions,
        prompt.trace.items,
    ):
        if source_field in trace_item.source_fields:
            return instruction
    raise AssertionError(
        f"Source field not found in prompt trace: {source_field}"
    )


class PromptTranslationTest(unittest.TestCase):

    def test_prompt_translation_models_are_passive_dataclasses(self):
        for model in (
            PromptBudgetPolicy,
            PromptCompilationMetrics,
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
            effective_brief()
        )

        with self.assertRaises(
            FrozenInstanceError
        ):
            prompt.fingerprint = "changed"

    def test_translates_visual_synthesis_result_from_canonical_brief(self):
        analysis, reasoning = analysis_and_reasoning(
            complete_scene()
        )
        synthesis_result = VisualSynthesisOrchestrator().synthesize(
            analysis,
            reasoning
        )

        prompt = PromptTranslator().translate_visual_synthesis_result(
            synthesis_result
        )

        source_fields = all_trace_source_fields(
            prompt
        )

        self.assertIn(
            "VisualSynthesisResult.brief.primary_identity",
            source_fields,
        )
        self.assertIn(
            "VisualSynthesisResult.brief.visual_priorities",
            source_fields,
        )
        self.assertEqual(
            synthesis_result.brief.fingerprint,
            prompt.trace.source_effective_brief_fingerprint,
        )

    def test_translates_effective_brief_fields_into_backend_neutral_instructions(self):
        prompt = PromptTranslator().translate(
            effective_brief()
        )

        self.assertIn(
            "person receiving an old key",
            prompt.compiled_prompt
        )
        self.assertIn(
            "old key changes hands",
            prompt.compiled_prompt
        )
        self.assertIn(
            "quiet interior",
            prompt.compiled_prompt
        )
        self.assertIn(
            "old key",
            prompt.compiled_prompt
        )
        self.assertEqual(
            instruction_by_source_field(
                prompt,
                "EffectiveVisualBrief.visual_constraints",
            ).category,
            "constraints"
        )
        self.assertIn(
            "a key changes hands in silence",
            prompt.compiled_prompt
        )
        self.assertNotIn(
            "structured",
            prompt.compiled_prompt,
        )
        self.assertEqual(
            instruction_by_source_field(
                prompt,
                "EffectiveVisualBrief.photography.point_of_view",
            ).category,
            "photography"
        )
        self.assertIn(
            "deep graphite",
            prompt.compiled_prompt
        )
        self.assertIn(
            "avoid spectacle",
            prompt.compiled_prompt
        )

    def test_translation_preserves_meaning_without_new_decisions(self):
        prompt = PromptTranslator().translate(
            effective_brief()
        )

        self.assertIn(
            "threshold event",
            prompt.compiled_prompt
        )
        self.assertIn(
            "consequence over object",
            prompt.compiled_prompt
        )
        self.assertIn(
            "the key acts as threshold and burden",
            prompt.compiled_prompt
        )
        self.assertNotIn(
            "ComfyUI",
            prompt.compiled_prompt
        )
        self.assertNotIn(
            "Flux",
            prompt.compiled_prompt
        )

    def test_translation_is_deterministic(self):
        effective = effective_brief()

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
            effective_brief(),
            cinematic_direction_set=cinematic_direction_set(),
        )

        self.assertIn(
            "CinematicDirectionSet.photography.dominant_photographic_language",
            all_trace_source_fields(
                prompt
            )
        )
        self.assertEqual(
            instruction_by_source_field(
                prompt,
                "CinematicDirectionSet.photography.dominant_photographic_language",
            ).category,
            "photography"
        )
        self.assertIn(
            "muted amber",
            prompt.compiled_prompt
        )
        self.assertIn(
            "EffectiveVisualBrief.visible_content",
            all_trace_source_fields(
                prompt
            )
        )

    def test_cinematic_translation_trace_keeps_direction_and_set_fingerprints(self):
        direction_set = cinematic_direction_set()
        prompt = PromptTranslator().translate(
            effective_brief(),
            cinematic_direction_set=direction_set,
        )
        source_fields = all_trace_source_fields(
            prompt
        )

        self.assertIn(
            "CinematicDirectionSet.photography.dominant_photographic_language",
            source_fields,
        )
        self.assertIn(
            "CinematicDirectionSet.photography.fingerprint",
            source_fields,
        )
        self.assertIn(
            "CinematicDirectionSet.fingerprint",
            source_fields,
        )
        self.assertIn(
            "semantic_prompt_compilation",
            {
                item.transformation
                for item in prompt.trace.items
            },
        )
        self.assertNotEqual(
            direction_set.fingerprint,
            ""
        )

    def test_cinematic_translation_is_deterministic(self):
        effective = effective_brief()
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
        effective = effective_brief()
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
            effective_brief()
        )
        changed = EffectiveVisualBrief(
                visible_content="A different visible event.",
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
            effective_brief()
        )
        source_fields = all_trace_source_fields(
            prompt
        )

        self.assertEqual(
            prompt.trace.source_effective_brief_fingerprint,
            "visual-brief-fingerprint"
        )
        self.assertIn(
            "EffectiveVisualBrief.visible_content",
            source_fields,
        )
        self.assertIn(
            "EffectiveVisualBrief.color.palette",
            source_fields,
        )
        self.assertEqual(
            {
                item.transformation
                for item in prompt.trace.items
            },
            {
                "semantic_prompt_compilation",
            },
        )

    def test_compiled_prompt_stays_within_backend_budget(self):
        prompt = PromptTranslator().translate(
            effective_brief(),
            cinematic_direction_set=cinematic_direction_set(),
        )

        self.assertTrue(
            prompt.compiled_prompt
        )
        self.assertLessEqual(
            prompt.metrics.prompt_token_count,
            prompt.budget_policy.hard_prompt_tokens,
        )
        self.assertEqual(
            prompt.metrics.token_count_method,
            "conservative_estimate",
        )

    def test_semantic_compaction_prevents_oversized_flux_prompts(self):
        long_fragment = (
            "a grounded live action person receiving an ancient key in a quiet interior "
            "with restrained solemnity and no readable text "
        )
        brief = EffectiveVisualBrief(
            visible_content=long_fragment * 80,
            visible_subject=long_fragment * 40,
            visible_action=long_fragment * 30,
            visible_environment=long_fragment * 30,
            filmable_interpretation=long_fragment * 30,
            visual_constraints=(
                "no readable text",
                "no logos",
            ),
            fingerprint="oversized-brief",
        )

        policy = PromptBudgetPolicy(
            target_prompt_tokens=20,
            warning_prompt_tokens=40,
            hard_prompt_tokens=384,
        )
        prompt = PromptTranslator(
            budget_policy=policy
        ).translate(
            brief
        )

        self.assertLessEqual(
            prompt.metrics.prompt_token_count,
            prompt.budget_policy.hard_prompt_tokens,
        )
        self.assertTrue(
            prompt.metrics.compactation_applied
        )
        self.assertIn(
            "priority_compaction",
            prompt.metrics.compactation_stages,
        )

    def test_compiled_prompt_excludes_internal_metadata(self):
        prompt = PromptTranslator().translate(
            effective_brief(),
            cinematic_direction_set=cinematic_direction_set(),
        )
        forbidden = (
            "EffectiveVisualBrief",
            "CinematicDirectionSet",
            "fingerprint",
            "BackendPrompt",
            "Trace",
            "schema_version",
            "visual-brief-fingerprint",
            "photography-fingerprint",
        )

        for item in forbidden:
            with self.subTest(
                item=item
            ):
                self.assertNotIn(
                    item,
                    prompt.compiled_prompt
                )

    def test_unsatisfiable_budget_raises_structured_error(self):
        policy = PromptBudgetPolicy(
            target_prompt_tokens=1,
            warning_prompt_tokens=1,
            hard_prompt_tokens=1,
        )

        with self.assertRaises(
            PromptBudgetExceededError
        ) as context:
            PromptTranslator(
                budget_policy=policy
            ).translate(
                EffectiveVisualBrief(
                    visible_subject="person receiving ancient key",
                    visual_constraints=("no readable text",),
                    fingerprint="tight-budget",
                )
            )

        self.assertEqual(
            context.exception.code,
            "PROMPT_BUDGET_UNSATISFIABLE",
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
