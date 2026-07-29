import unittest

from app.domain import (
    FindingSeverity,
    VisualConflictReport,
    VisualIntelligenceStrategy,
    VisualReasoningResult,
)
from app.visual_intelligence import (
    VisualConflictResolver,
    VisualReasoningOrchestrator,
)
from tests.test_visual_synthesis_helpers import (
    analysis_and_reasoning,
    blocking_scene,
    complete_scene,
    error_scene,
    severities,
    warning_scene,
)


class VisualConflictResolverTest(unittest.TestCase):

    def test_builds_empty_conflict_report_when_no_conflicts_exist(self):
        analysis, reasoning = analysis_and_reasoning(
            complete_scene()
        )

        report = VisualConflictResolver().resolve(
            analysis,
            reasoning
        )

        self.assertIsInstance(
            report,
            VisualConflictReport
        )
        self.assertEqual(
            report.conflicts,
            ()
        )
        self.assertEqual(
            report.findings,
            ()
        )
        self.assertTrue(
            report.fingerprint
        )

    def test_preserves_warning_conflicts_from_reasoning(self):
        analysis, reasoning = analysis_and_reasoning(
            warning_scene()
        )

        report = VisualConflictResolver().resolve(
            analysis,
            reasoning
        )

        self.assertIn(
            FindingSeverity.WARNING,
            severities(
                report.findings
            )
        )
        self.assertEqual(
            report.conflicts[0].severity,
            FindingSeverity.WARNING
        )

    def test_preserves_error_conflicts_from_analysis_and_reasoning(self):
        analysis, reasoning = analysis_and_reasoning(
            error_scene()
        )

        report = VisualConflictResolver().resolve(
            analysis,
            reasoning
        )

        self.assertIn(
            FindingSeverity.ERROR,
            severities(
                report.findings
            )
        )
        self.assertIn(
            FindingSeverity.ERROR,
            tuple(
                conflict.severity
                for conflict in report.conflicts
            )
        )

    def test_preserves_blocking_conflicts(self):
        analysis, reasoning = analysis_and_reasoning(
            blocking_scene()
        )

        report = VisualConflictResolver().resolve(
            analysis,
            reasoning
        )

        self.assertIn(
            FindingSeverity.BLOCKING,
            severities(
                report.findings
            )
        )

    def test_supports_info_conflict_classification(self):
        analysis, reasoning = analysis_and_reasoning(
            complete_scene()
        )
        reasoning = VisualReasoningResult(
            scene_intent=reasoning.scene_intent,
            strategy=VisualIntelligenceStrategy(
                representation_approach=(
                    reasoning.strategy.representation_approach
                ),
                resources_to_avoid=(
                    "sin texto legible",
                ),
            ),
            continuity=reasoning.continuity,
            trace=reasoning.trace,
        )

        report = VisualConflictResolver().resolve(
            analysis,
            reasoning
        )

        self.assertIn(
            FindingSeverity.INFO,
            severities(
                report.findings
            )
        )

    def test_conflict_trace_preserves_evidence_source_reference(self):
        analysis, reasoning = analysis_and_reasoning(
            error_scene()
        )

        report = VisualConflictResolver().resolve(
            analysis,
            reasoning
        )

        self.assertTrue(
            report.trace.entries
        )
        self.assertTrue(
            report.trace.evidences
        )
        self.assertTrue(
            report.conflicts[0].origin.source_fingerprint
        )

    def test_repeated_conflict_resolution_is_deterministic(self):
        analysis, reasoning = analysis_and_reasoning(
            warning_scene()
        )
        resolver = VisualConflictResolver()

        first = resolver.resolve(
            analysis,
            reasoning
        )
        second = resolver.resolve(
            analysis,
            reasoning
        )

        self.assertEqual(
            first,
            second
        )
        self.assertEqual(
            first.fingerprint,
            second.fingerprint
        )

    def test_rejects_invalid_inputs(self):
        analysis, reasoning = analysis_and_reasoning(
            complete_scene()
        )

        with self.assertRaises(
            TypeError
        ):
            VisualConflictResolver().resolve(
                analysis,
                "invalid"
            )


if __name__ == "__main__":
    unittest.main()
