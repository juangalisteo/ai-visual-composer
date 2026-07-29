from app.domain import (
    ResolutionStatus,
    VisualAnalysisResult,
    VisualReasoningResult,
)
from app.visual_intelligence.analysis.rules import status_from_findings
from app.visual_intelligence.reasoning.continuity import SequenceContinuityResolver
from app.visual_intelligence.reasoning.intent import SceneIntentResolver
from app.visual_intelligence.reasoning.strategy import VisualStrategyResolver
from app.visual_intelligence.reasoning.support import (
    ensure_analysis,
    merge_findings,
    specialized_trace,
)


class VisualReasoningOrchestrator:
    def __init__(
        self,
        scene_intent_resolver: SceneIntentResolver | None = None,
        strategy_resolver: VisualStrategyResolver | None = None,
        continuity_resolver: SequenceContinuityResolver | None = None,
    ) -> None:
        self.scene_intent_resolver = (
            scene_intent_resolver
            or SceneIntentResolver()
        )
        self.strategy_resolver = (
            strategy_resolver
            or VisualStrategyResolver()
        )
        self.continuity_resolver = (
            continuity_resolver
            or SequenceContinuityResolver()
        )

    def reason(
        self,
        analysis: VisualAnalysisResult
    ) -> VisualReasoningResult:
        ensure_analysis(
            analysis,
            "VisualReasoningOrchestrator"
        )

        scene_intent = self.scene_intent_resolver.resolve(
            analysis
        )
        strategy = self.strategy_resolver.resolve(
            analysis,
            scene_intent
        )
        continuity = self.continuity_resolver.resolve(
            analysis
        )
        findings = merge_findings(
            analysis.findings,
            strategy.declared_conflicts,
            continuity.detected_risks
        )
        trace = specialized_trace(
            "visual_reasoning",
            (
                scene_intent.trace.entries
                if scene_intent.trace
                else ()
            )
            + (
                strategy.trace.entries
                if strategy.trace
                else ()
            )
            + (
                continuity.trace.entries
                if continuity.trace
                else ()
            ),
            (
                scene_intent.trace.evidences
                if scene_intent.trace
                else ()
            )
            + (
                strategy.trace.evidences
                if strategy.trace
                else ()
            )
            + (
                continuity.trace.evidences
                if continuity.trace
                else ()
            ),
        )
        return VisualReasoningResult(
            scene_intent=scene_intent,
            strategy=strategy,
            continuity=continuity,
            findings=findings,
            trace=trace,
            status=self._status(
                findings
            ),
            version="visual-reasoning-v1",
        )

    def _status(
        self,
        findings
    ) -> ResolutionStatus:
        return status_from_findings(
            findings
        )
