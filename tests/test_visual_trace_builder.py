import unittest

from app.domain import VisualIntelligenceTrace
from app.visual_intelligence import (
    EffectiveVisualBriefSynthesizer,
    VisualConflictResolver,
    VisualIntelligenceTraceBuilder,
)
from tests.test_visual_synthesis_helpers import (
    analysis_and_reasoning,
    complete_scene,
    error_scene,
)


def build_trace(scene):
    analysis, reasoning = analysis_and_reasoning(
        scene
    )
    conflicts = VisualConflictResolver().resolve(
        analysis,
        reasoning
    )
    brief = EffectiveVisualBriefSynthesizer().synthesize(
        analysis,
        reasoning,
        conflicts
    )
    return VisualIntelligenceTraceBuilder().build(
        analysis,
        reasoning,
        conflicts,
        brief
    )


class VisualIntelligenceTraceBuilderTest(unittest.TestCase):

    def test_builds_unified_visual_intelligence_trace(self):
        trace = build_trace(
            complete_scene()
        )

        self.assertIsInstance(
            trace,
            VisualIntelligenceTrace
        )
        self.assertTrue(
            trace.sources
        )
        self.assertTrue(
            trace.traces
        )
        self.assertTrue(
            trace.evidences
        )
        self.assertIn(
            "VisualAnalysisResult",
            trace.pipeline_history
        )
        self.assertIn(
            "EffectiveVisualBrief",
            trace.pipeline_history
        )

    def test_trace_preserves_findings_and_conflict_references(self):
        trace = build_trace(
            error_scene()
        )

        self.assertTrue(
            trace.findings
        )
        self.assertTrue(
            trace.conflict_references
        )

    def test_trace_records_rules_and_resolvers(self):
        trace = build_trace(
            complete_scene()
        )

        self.assertIn(
            "synthesize_primary_identity",
            trace.rules_applied
        )
        self.assertIn(
            "VisualIntelligenceTraceBuilder",
            trace.resolver_references
        )

    def test_repeated_trace_building_is_deterministic(self):
        first = build_trace(
            complete_scene()
        )
        second = build_trace(
            complete_scene()
        )

        self.assertEqual(
            first,
            second
        )
        self.assertEqual(
            first.fingerprint,
            second.fingerprint
        )


if __name__ == "__main__":
    unittest.main()
