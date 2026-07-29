import inspect
import unittest
from dataclasses import FrozenInstanceError, asdict, is_dataclass, replace
from pathlib import Path

from app.domain import (
    CertaintyLevel,
    DerivationKind,
    FindingSeverity,
    ResolutionTraceEntry,
    SequenceContinuity,
    SourceReference,
    SpecializedTrace,
    VisualConflict,
    VisualInspectionResult,
    VisualIntelligenceEvidence,
    VisualIntelligenceFinding,
    VisualIntelligenceResolutionResult,
    VisualIntelligenceStrategy,
    VisualPriority,
    VisualReasoningResult,
    VisualSceneIntent,
    VisualSemantics,
)


def source_reference(
    path="StoryboardScene.visible_subject",
    value="persona adulta"
):
    return SourceReference(
        component="StoryboardSceneAdapter",
        field="visible_subject",
        path=path,
        value=value,
        source_fingerprint="source-fingerprint",
    )


def evidence():
    return VisualIntelligenceEvidence(
        source=source_reference(),
        derivation_kind=DerivationKind.COPIED,
        certainty=CertaintyLevel.EXPLICIT,
        explanation_code="visual_truth_field_used",
        responsible_component="VisualSemanticsResolver",
    )


def finding(
    severity=FindingSeverity.INFO
):
    return VisualIntelligenceFinding(
        code="field_present",
        category="inspection",
        severity=severity,
        message="Field is available.",
        evidences=(
            evidence(),
        ),
        affected_paths=(
            "StoryboardScene.visible_subject",
        ),
    )


def trace_entry():
    return ResolutionTraceEntry(
        component="VisualSemanticsResolver",
        sources=(
            source_reference(),
        ),
        operation="preserve_visual_semantic_role",
        output_path="VisualSemantics.primary_subject",
        derivation_kind=DerivationKind.CLASSIFIED,
        certainty=CertaintyLevel.STRONG,
    )


def specialized_trace():
    return SpecializedTrace(
        resolution_type="visual_semantics",
        entries=(
            trace_entry(),
        ),
        evidences=(
            evidence(),
        ),
    )


class VisualIntelligenceSpecializedContractsTest(unittest.TestCase):

    def test_specialized_contracts_are_passive_frozen_dataclasses(self):
        for model in (
            SpecializedTrace,
            VisualInspectionResult,
            VisualSemantics,
            VisualPriority,
            VisualReasoningResult,
            VisualSceneIntent,
            VisualIntelligenceStrategy,
            SequenceContinuity,
            VisualConflict,
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

    def test_specialized_contracts_are_immutable(self):
        semantics = VisualSemantics(
            primary_subject="persona adulta"
        )

        with self.assertRaises(
            FrozenInstanceError
        ):
            semantics.primary_subject = "changed"

    def test_specialized_trace_reuses_core_trace_and_evidence(self):
        trace = specialized_trace()

        self.assertEqual(
            trace.resolution_type,
            "visual_semantics"
        )
        self.assertEqual(
            trace.entries,
            (
                trace_entry(),
            )
        )
        self.assertEqual(
            trace.evidences,
            (
                evidence(),
            )
        )
        self.assertTrue(
            trace.fingerprint
        )

    def test_visual_inspection_result_represents_state_without_inspection_logic(self):
        result = VisualInspectionResult(
            completeness="complete",
            consistency="consistent",
            visual_density="medium",
            specificity="high",
            missing_fields=(
                "time_context",
            ),
            ambiguous_fields=(
                "visible_environment",
            ),
            findings=(
                finding(),
            ),
            trace=specialized_trace(),
        )

        self.assertEqual(
            result.completeness,
            "complete"
        )
        self.assertEqual(
            result.missing_fields,
            (
                "time_context",
            )
        )
        self.assertEqual(
            result.findings,
            (
                finding(),
            )
        )

    def test_visual_semantics_represents_passive_semantic_roles(self):
        semantics = VisualSemantics(
            primary_subject="persona adulta",
            secondary_subjects=(
                "archivista",
            ),
            narrative_objects=(
                "llave antigua",
            ),
            active_environment="archivo subterraneo",
            contextual_environment="noche lluviosa",
            observable_action="recibe una llave",
            visual_state="expectante",
            spatial_relationships=(
                "la llave queda entre ambas manos",
            ),
            ambiguity_level=CertaintyLevel.MODERATE,
            evidences=(
                evidence(),
            ),
            trace=specialized_trace(),
        )

        self.assertEqual(
            semantics.primary_subject,
            "persona adulta"
        )
        self.assertEqual(
            semantics.ambiguity_level,
            CertaintyLevel.MODERATE
        )
        self.assertEqual(
            semantics.narrative_objects,
            (
                "llave antigua",
            )
        )

    def test_visual_priority_represents_priority_without_composition(self):
        priority = VisualPriority(
            primary_priority="llave antigua",
            secondary_priorities=(
                "manos",
            ),
            attention_focus="intercambio de la llave",
            supporting_elements=(
                "mesa de archivo",
            ),
            visual_hierarchy=(
                "llave antigua",
                "manos",
                "archivo",
            ),
            evidences=(
                evidence(),
            ),
        )

        self.assertEqual(
            priority.primary_priority,
            "llave antigua"
        )
        self.assertNotIn(
            "framing",
            priority.__dataclass_fields__
        )

    def test_visual_scene_intent_represents_intent_without_inventing_it(self):
        intent = VisualSceneIntent(
            emotional_function="revelar confianza",
            narrative_tension="contenida",
            visual_subtext="entrega de responsabilidad",
            uncertainty=CertaintyLevel.WEAK,
            evidences=(
                evidence(),
            ),
        )

        self.assertEqual(
            intent.emotional_function,
            "revelar confianza"
        )
        self.assertEqual(
            intent.uncertainty,
            CertaintyLevel.WEAK
        )

    def test_visual_intelligence_strategy_avoids_existing_visual_strategy_duplication(self):
        strategy = VisualIntelligenceStrategy(
            representation_approach="realismo simbolico sobrio",
            realism_level="high",
            symbolism_degree="moderate",
            visual_limits=(
                "no logos",
            ),
            resources_to_avoid=(
                "texto legible",
            ),
            declared_conflicts=(
                finding(
                    severity=FindingSeverity.WARNING
                ),
            ),
            evidences=(
                evidence(),
            ),
        )

        self.assertEqual(
            strategy.representation_approach,
            "realismo simbolico sobrio"
        )
        self.assertEqual(
            strategy.declared_conflicts[0].severity,
            FindingSeverity.WARNING
        )

    def test_sequence_continuity_represents_continuity_without_memory_logic(self):
        continuity = SequenceContinuity(
            character_continuity=(
                "misma investigadora",
            ),
            object_continuity=(
                "misma llave antigua",
            ),
            location_continuity=(
                "archivo subterraneo",
            ),
            visual_continuity=(
                "misma atmosfera nocturna",
            ),
            scene_relationships=(
                "continua escena anterior",
            ),
            detected_risks=(
                finding(
                    severity=FindingSeverity.WARNING
                ),
            ),
        )

        self.assertEqual(
            continuity.object_continuity,
            (
                "misma llave antigua",
            )
        )
        self.assertEqual(
            continuity.detected_risks[0].severity,
            FindingSeverity.WARNING
        )

    def test_visual_conflict_represents_conflict_without_resolution_logic(self):
        conflict = VisualConflict(
            conflict="restriction_conflict",
            category="visual_constraints",
            severity=FindingSeverity.ERROR,
            origin=source_reference(
                path="StoryboardScene.visual_constraints",
                value="no text"
            ),
            involved_components=(
                "VisualStrategyResolver",
                "VisualConflictResolver",
            ),
            passive_recommendation="mark_for_review",
            evidences=(
                evidence(),
            ),
            trace=specialized_trace(),
        )

        self.assertEqual(
            conflict.category,
            "visual_constraints"
        )
        self.assertEqual(
            conflict.passive_recommendation,
            "mark_for_review"
        )

    def test_visual_reasoning_result_groups_reasoning_outputs(self):
        result = VisualReasoningResult(
            scene_intent=VisualSceneIntent(
                emotional_function="hold attention on llave antigua"
            ),
            strategy=VisualIntelligenceStrategy(
                representation_approach="represent explicit Visual Truth directly"
            ),
            continuity=SequenceContinuity(
                object_continuity=(
                    "llave antigua",
                )
            ),
            findings=(
                finding(),
            ),
            trace=specialized_trace(),
        )

        self.assertEqual(
            result.scene_intent.emotional_function,
            "hold attention on llave antigua"
        )
        self.assertEqual(
            result.continuity.object_continuity,
            (
                "llave antigua",
            )
        )
        self.assertTrue(
            result.fingerprint
        )

    def test_specialized_contracts_have_deterministic_fingerprints(self):
        first = VisualSemantics(
            primary_subject="persona adulta",
            narrative_objects=(
                "llave antigua",
            ),
        )
        second = VisualSemantics(
            primary_subject="persona adulta",
            narrative_objects=(
                "llave antigua",
            ),
        )

        self.assertEqual(
            first.fingerprint,
            second.fingerprint
        )

    def test_specialized_fingerprint_changes_on_relevant_change(self):
        first = VisualPriority(
            primary_priority="llave antigua"
        )
        second = VisualPriority(
            primary_priority="rostro"
        )

        self.assertNotEqual(
            first.fingerprint,
            second.fingerprint
        )

    def test_replace_recomputes_specialized_fingerprint(self):
        original = VisualSceneIntent(
            emotional_function="revelar confianza"
        )
        changed = replace(
            original,
            emotional_function="ocultar tension"
        )

        self.assertNotEqual(
            original.fingerprint,
            changed.fingerprint
        )

    def test_specialized_serialization_keeps_core_contracts(self):
        serialized = asdict(
            VisualConflict(
                conflict="restriction_conflict",
                category="visual_constraints",
                severity=FindingSeverity.ERROR,
                origin=source_reference(),
                evidences=(
                    evidence(),
                ),
            )
        )

        self.assertEqual(
            serialized["severity"],
            FindingSeverity.ERROR
        )
        self.assertEqual(
            serialized["origin"]["path"],
            "StoryboardScene.visible_subject"
        )
        self.assertEqual(
            serialized["evidences"][0]["derivation_kind"],
            DerivationKind.COPIED
        )

    def test_specialized_result_can_use_core_resolution_result(self):
        semantics = VisualSemantics(
            primary_subject="persona adulta"
        )
        result = VisualIntelligenceResolutionResult(
            result=semantics,
            trace=(
                trace_entry(),
            ),
        )

        self.assertIs(
            result.result,
            semantics
        )
        self.assertTrue(
            result.fingerprint
        )

    def test_rejects_invalid_core_types(self):
        with self.assertRaises(
            ValueError
        ):
            VisualInspectionResult(
                completeness="complete",
                consistency="consistent",
                findings=[
                    finding(),
                ],
            )

    def test_rejects_invalid_optional_trace(self):
        with self.assertRaises(
            ValueError
        ):
            VisualSemantics(
                primary_subject="persona adulta",
                trace="invalid",
            )

    def test_rejects_invalid_enum_on_specialized_contract(self):
        with self.assertRaises(
            ValueError
        ):
            VisualConflict(
                conflict="restriction_conflict",
                category="visual_constraints",
                severity="error",
                origin=source_reference(),
            )

    def test_contracts_contain_no_backend_runtime_prompt_or_payload_fields(self):
        forbidden = {
            "prompt",
            "payload",
            "workflow",
            "backend",
            "runtime",
            "comfyui",
            "manifest",
            "image_builder",
        }
        for model in (
            SpecializedTrace,
            VisualInspectionResult,
            VisualSemantics,
            VisualPriority,
            VisualReasoningResult,
            VisualSceneIntent,
            VisualIntelligenceStrategy,
            SequenceContinuity,
            VisualConflict,
        ):
            with self.subTest(
                model=model.__name__
            ):
                self.assertTrue(
                    forbidden.isdisjoint(
                        {
                            field.lower()
                            for field in model.__dataclass_fields__
                        }
                    )
                )

    def test_visual_intelligence_domain_has_no_forbidden_dependencies(self):
        source = inspect.getsource(
            __import__(
                "app.domain.visual_intelligence",
                fromlist=[
                    "x"
                ]
            )
        )
        forbidden = (
            "ImageBuilder",
            "RuntimeCognitiveAdapter",
            "PromptTranslator",
            "BackendPrompt",
            "ComfyUI",
            "VisualQuality",
            "VideoBuilder",
            "workflow",
            "requests",
            "urllib",
        )

        for item in forbidden:
            with self.subTest(
                item=item
            ):
                self.assertNotIn(
                    item,
                    source
                )

    def test_no_runtime_layers_import_visual_intelligence_specialized_contracts(self):
        forbidden_paths = []
        forbidden_roots = (
            "app/modules",
            "app/prompt_translation",
            "app/backend_adapters",
            "app/visual_quality",
        )
        for root in forbidden_roots:
            for path in Path(
                root
            ).rglob(
                "*.py"
            ):
                source = path.read_text(
                    encoding="utf-8"
                )
                if "VisualInspectionResult" in source:
                    forbidden_paths.append(
                        path.as_posix()
                    )

        self.assertEqual(
            [],
            forbidden_paths
        )

    def test_no_resolver_classes_are_defined_for_ip3_1b(self):
        source = Path(
            "app/domain/visual_intelligence.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertNotIn(
            "class VisualTruthInspector",
            source
        )
        self.assertNotIn(
            "class VisualSemanticsResolver",
            source
        )
        self.assertNotIn(
            "def resolve",
            source
        )


if __name__ == "__main__":
    unittest.main()
