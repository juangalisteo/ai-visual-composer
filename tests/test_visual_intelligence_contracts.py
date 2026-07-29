import inspect
import unittest
from dataclasses import FrozenInstanceError, asdict, is_dataclass, replace
from pathlib import Path

from app.domain import (
    CertaintyLevel,
    DerivationKind,
    FindingSeverity,
    ResolutionStatus,
    ResolutionTraceEntry,
    SourceReference,
    VisualIntelligenceEvidence,
    VisualIntelligenceFinding,
    VisualIntelligenceResolutionResult,
    deterministic_fingerprint,
)


def source_reference(
    value="persona adulta"
):
    return SourceReference(
        component="StoryboardSceneAdapter",
        field="visible_subject",
        path="StoryboardScene.visible_subject",
        value=value,
        source_fingerprint="source-fingerprint",
    )


def evidence():
    return VisualIntelligenceEvidence(
        source=source_reference(),
        derivation_kind=DerivationKind.COPIED,
        certainty=CertaintyLevel.EXPLICIT,
        explanation_code="visual_truth_field_preserved",
        responsible_component="VisualTruthInspector",
        details=(
            "field_present",
        ),
    )


def finding():
    return VisualIntelligenceFinding(
        code="visual_truth_present",
        category="completeness",
        severity=FindingSeverity.INFO,
        message="Visual Truth field is present.",
        evidences=(
            evidence(),
        ),
        affected_paths=(
            "StoryboardScene.visible_subject",
        ),
    )


def trace_entry():
    return ResolutionTraceEntry(
        component="VisualTruthInspector",
        sources=(
            source_reference(),
        ),
        operation="inspect_source_field",
        output_path="VisualIntelligenceInspection.visible_subject",
        derivation_kind=DerivationKind.COPIED,
        certainty=CertaintyLevel.EXPLICIT,
    )


class VisualIntelligenceContractsTest(unittest.TestCase):

    def test_core_contracts_are_passive_frozen_dataclasses(self):
        for model in (
            SourceReference,
            VisualIntelligenceEvidence,
            VisualIntelligenceFinding,
            ResolutionTraceEntry,
            VisualIntelligenceResolutionResult,
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

    def test_contracts_are_immutable(self):
        reference = source_reference()

        with self.assertRaises(
            FrozenInstanceError
        ):
            reference.component = "Changed"

    def test_source_reference_has_deterministic_fingerprint(self):
        first = source_reference()
        second = source_reference()

        self.assertEqual(
            first,
            second
        )
        self.assertEqual(
            first.fingerprint,
            second.fingerprint
        )

    def test_source_reference_fingerprint_changes_on_relevant_change(self):
        first = source_reference()
        second = source_reference(
            value="llave antigua"
        )

        self.assertNotEqual(
            first.fingerprint,
            second.fingerprint
        )

    def test_evidence_preserves_source_derivation_certainty_and_owner(self):
        item = evidence()

        self.assertEqual(
            item.source.path,
            "StoryboardScene.visible_subject"
        )
        self.assertEqual(
            item.derivation_kind,
            DerivationKind.COPIED
        )
        self.assertEqual(
            item.certainty,
            CertaintyLevel.EXPLICIT
        )
        self.assertEqual(
            item.responsible_component,
            "VisualTruthInspector"
        )
        self.assertTrue(
            item.fingerprint
        )

    def test_finding_collects_evidence_without_runtime_state(self):
        item = finding()

        self.assertEqual(
            item.code,
            "visual_truth_present"
        )
        self.assertEqual(
            item.severity,
            FindingSeverity.INFO
        )
        self.assertEqual(
            item.evidences,
            (
                evidence(),
            )
        )
        self.assertEqual(
            item.affected_paths,
            (
                "StoryboardScene.visible_subject",
            )
        )

    def test_resolution_trace_entry_reconstructs_derivation(self):
        item = trace_entry()

        self.assertEqual(
            item.component,
            "VisualTruthInspector"
        )
        self.assertEqual(
            item.operation,
            "inspect_source_field"
        )
        self.assertEqual(
            item.output_path,
            "VisualIntelligenceInspection.visible_subject"
        )
        self.assertEqual(
            item.sources,
            (
                source_reference(),
            )
        )

    def test_base_resolution_result_shares_metadata_without_erasing_payload(self):
        result_payload = (
            "visible_subject",
            "visible_action",
        )
        result = VisualIntelligenceResolutionResult(
            result=result_payload,
            findings=(
                finding(),
            ),
            trace=(
                trace_entry(),
            ),
            status=ResolutionStatus.READY,
            version="visual-intelligence-core-v1",
        )

        self.assertEqual(
            result.result,
            result_payload
        )
        self.assertEqual(
            result.status,
            ResolutionStatus.READY
        )
        self.assertEqual(
            result.schema_version,
            "1.0.0"
        )
        self.assertTrue(
            result.fingerprint
        )

    def test_resolution_result_fingerprint_is_deterministic(self):
        first = VisualIntelligenceResolutionResult(
            result=(
                "a",
                "b",
            ),
            findings=(
                finding(),
            ),
            trace=(
                trace_entry(),
            ),
        )
        second = VisualIntelligenceResolutionResult(
            result=(
                "a",
                "b",
            ),
            findings=(
                finding(),
            ),
            trace=(
                trace_entry(),
            ),
        )

        self.assertEqual(
            first.fingerprint,
            second.fingerprint
        )

    def test_resolution_result_fingerprint_changes_on_result_change(self):
        first = VisualIntelligenceResolutionResult(
            result=(
                "a",
                "b",
            )
        )
        second = VisualIntelligenceResolutionResult(
            result=(
                "a",
                "changed",
            )
        )

        self.assertNotEqual(
            first.fingerprint,
            second.fingerprint
        )

    def test_fingerprint_is_stable_for_equivalent_serializations(self):
        first = deterministic_fingerprint(
            "example",
            {
                "b": 2,
                "a": 1,
            }
        )
        second = deterministic_fingerprint(
            "example",
            {
                "a": 1,
                "b": 2,
            }
        )

        self.assertEqual(
            first,
            second
        )

    def test_asdict_serialization_is_stable_and_readable(self):
        serialized = asdict(
            evidence()
        )

        self.assertEqual(
            serialized["derivation_kind"],
            DerivationKind.COPIED
        )
        self.assertEqual(
            serialized["certainty"],
            CertaintyLevel.EXPLICIT
        )
        self.assertEqual(
            serialized["source"]["path"],
            "StoryboardScene.visible_subject"
        )

    def test_rejects_invalid_enum_values(self):
        with self.assertRaises(
            ValueError
        ):
            VisualIntelligenceEvidence(
                source=source_reference(),
                derivation_kind="copied",
                certainty=CertaintyLevel.EXPLICIT,
                explanation_code="invalid",
                responsible_component="VisualTruthInspector",
            )

    def test_rejects_invalid_sequences(self):
        with self.assertRaises(
            ValueError
        ):
            VisualIntelligenceFinding(
                code="invalid",
                category="invalid",
                severity=FindingSeverity.ERROR,
                message="Invalid evidence container.",
                evidences=[
                    evidence(),
                ],
            )

    def test_rejects_missing_required_text(self):
        with self.assertRaises(
            ValueError
        ):
            SourceReference(
                component="",
                path="StoryboardScene.visible_subject",
            )

    def test_replace_does_not_mutate_original_contract(self):
        original = source_reference()
        changed = replace(
            original,
            value="changed"
        )

        self.assertEqual(
            original.value,
            "persona adulta"
        )
        self.assertEqual(
            changed.value,
            "changed"
        )
        self.assertNotEqual(
            original.fingerprint,
            changed.fingerprint
        )

    def test_enums_define_only_core_semantics(self):
        self.assertEqual(
            tuple(
                item.value
                for item in DerivationKind
            ),
            (
                "copied",
                "normalized",
                "inferred",
                "classified",
                "prioritized",
                "aggregated",
            )
        )
        self.assertEqual(
            tuple(
                item.value
                for item in CertaintyLevel
            ),
            (
                "explicit",
                "strong",
                "moderate",
                "weak",
                "unknown",
            )
        )
        self.assertEqual(
            tuple(
                item.value
                for item in FindingSeverity
            ),
            (
                "info",
                "warning",
                "error",
                "blocking",
            )
        )

    def test_contracts_contain_no_backend_runtime_or_prompt_fields(self):
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
            SourceReference,
            VisualIntelligenceEvidence,
            VisualIntelligenceFinding,
            ResolutionTraceEntry,
            VisualIntelligenceResolutionResult,
        ):
            with self.subTest(
                model=model.__name__
            ):
                field_names = {
                    field.lower()
                    for field in model.__dataclass_fields__
                }
                self.assertTrue(
                    forbidden.isdisjoint(
                        field_names
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

    def test_runtime_backend_and_prompt_layers_do_not_import_visual_intelligence_contracts(self):
        paths_with_import = []
        for root in (
            "app/modules",
            "app/prompt_translation",
            "app/backend_adapters",
            "app/visual_quality",
        ):
            for path in Path(
                root
            ).rglob(
                "*.py"
            ):
                source = path.read_text(
                    encoding="utf-8"
                )
                if "visual_intelligence" in source:
                    paths_with_import.append(
                        path.as_posix()
                    )

        self.assertEqual(
            [],
            paths_with_import
        )


if __name__ == "__main__":
    unittest.main()
