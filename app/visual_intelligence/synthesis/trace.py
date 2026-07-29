from app.domain import (
    EffectiveVisualBrief,
    SpecializedTrace,
    VisualAnalysisResult,
    VisualConflictReport,
    VisualIntelligenceTrace,
    VisualReasoningResult,
)
from app.visual_intelligence.synthesis.support import (
    ensure_inputs,
    merge_evidences,
    merge_findings,
    merge_sources,
    sources_from_trace,
)


class VisualIntelligenceTraceBuilder:
    component_name = "VisualIntelligenceTraceBuilder"

    def build(
        self,
        analysis: VisualAnalysisResult,
        reasoning: VisualReasoningResult,
        conflicts: VisualConflictReport,
        brief: EffectiveVisualBrief
    ) -> VisualIntelligenceTrace:
        ensure_inputs(
            analysis,
            reasoning,
            self.component_name
        )
        if not isinstance(
            conflicts,
            VisualConflictReport
        ):
            raise TypeError(
                "VisualIntelligenceTraceBuilder expects a VisualConflictReport."
            )
        if not isinstance(
            brief,
            EffectiveVisualBrief
        ):
            raise TypeError(
                "VisualIntelligenceTraceBuilder expects an EffectiveVisualBrief."
            )

        traces = self._traces(
            analysis,
            reasoning,
            conflicts,
            brief
        )
        evidences = merge_evidences(
            *(
                trace.evidences
                for trace in traces
            )
        )
        sources = merge_sources(
            *(
                sources_from_trace(
                    trace
                )
                for trace in traces
            )
        )

        return VisualIntelligenceTrace(
            sources=sources,
            traces=traces,
            evidences=evidences,
            findings=merge_findings(
                analysis.findings,
                reasoning.findings,
                conflicts.findings,
                brief.findings
            ),
            rules_applied=self._rules_applied(
                traces
            ),
            conflict_references=tuple(
                conflict.fingerprint
                for conflict in conflicts.conflicts
            ),
            resolver_references=(
                "VisualAnalysisOrchestrator",
                "VisualReasoningOrchestrator",
                "VisualConflictResolver",
                "EffectiveVisualBriefSynthesizer",
                self.component_name,
            ),
            pipeline_history=(
                "VisualAnalysisResult",
                "VisualReasoningResult",
                "VisualConflictReport",
                "EffectiveVisualBrief",
                "VisualIntelligenceTrace",
            ),
        )

    def _traces(
        self,
        analysis: VisualAnalysisResult,
        reasoning: VisualReasoningResult,
        conflicts: VisualConflictReport,
        brief: EffectiveVisualBrief
    ) -> tuple[SpecializedTrace, ...]:
        return tuple(
            trace
            for trace in (
                analysis.trace,
                reasoning.trace,
                conflicts.trace,
                brief.trace,
            )
            if trace is not None
        )

    def _rules_applied(
        self,
        traces: tuple[SpecializedTrace, ...]
    ) -> tuple[str, ...]:
        rules = []
        for trace in traces:
            for entry in trace.entries:
                if entry.operation not in rules:
                    rules.append(
                        entry.operation
                    )
        return tuple(
            rules
        )
