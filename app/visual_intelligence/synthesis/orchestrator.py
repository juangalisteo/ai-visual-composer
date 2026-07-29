from app.domain import (
    ResolutionStatus,
    VisualAnalysisResult,
    VisualReasoningResult,
    VisualSynthesisResult,
)
from app.visual_intelligence.analysis.rules import status_from_findings
from app.visual_intelligence.synthesis.brief import EffectiveVisualBriefSynthesizer
from app.visual_intelligence.synthesis.conflicts import VisualConflictResolver
from app.visual_intelligence.synthesis.support import ensure_inputs, merge_findings
from app.visual_intelligence.synthesis.trace import VisualIntelligenceTraceBuilder


class VisualSynthesisOrchestrator:
    def __init__(
        self,
        conflict_resolver: VisualConflictResolver | None = None,
        brief_synthesizer: EffectiveVisualBriefSynthesizer | None = None,
        trace_builder: VisualIntelligenceTraceBuilder | None = None,
    ) -> None:
        self.conflict_resolver = (
            conflict_resolver
            or VisualConflictResolver()
        )
        self.brief_synthesizer = (
            brief_synthesizer
            or EffectiveVisualBriefSynthesizer()
        )
        self.trace_builder = (
            trace_builder
            or VisualIntelligenceTraceBuilder()
        )

    def synthesize(
        self,
        analysis: VisualAnalysisResult,
        reasoning: VisualReasoningResult,
    ) -> VisualSynthesisResult:
        ensure_inputs(
            analysis,
            reasoning,
            "VisualSynthesisOrchestrator"
        )

        conflicts = self.conflict_resolver.resolve(
            analysis,
            reasoning
        )
        brief = self.brief_synthesizer.synthesize(
            analysis,
            reasoning,
            conflicts,
        )
        trace = self.trace_builder.build(
            analysis,
            reasoning,
            conflicts,
            brief
        )
        findings = merge_findings(
            conflicts.findings,
            brief.findings,
            trace.findings
        )

        return VisualSynthesisResult(
            brief=brief,
            conflicts=conflicts,
            trace=trace,
            findings=findings,
            status=self._status(
                findings
            ),
            version="visual-synthesis-v1",
        )

    def _status(
        self,
        findings
    ) -> ResolutionStatus:
        return status_from_findings(
            findings
        )
