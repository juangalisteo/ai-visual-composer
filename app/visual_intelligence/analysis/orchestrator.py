from app.domain import (
    ResolutionStatus,
    StoryboardScene,
    VisualAnalysisResult,
)
from app.visual_intelligence.analysis.inspector import VisualTruthInspector
from app.visual_intelligence.analysis.priority import VisualPriorityResolver
from app.visual_intelligence.analysis.rules import status_from_findings
from app.visual_intelligence.analysis.semantics import VisualSemanticsResolver
from app.visual_intelligence.analysis.support import specialized_trace


class VisualAnalysisOrchestrator:
    def __init__(
        self,
        inspector: VisualTruthInspector | None = None,
        semantics_resolver: VisualSemanticsResolver | None = None,
        priority_resolver: VisualPriorityResolver | None = None,
    ) -> None:
        self.inspector = inspector or VisualTruthInspector()
        self.semantics_resolver = (
            semantics_resolver
            or VisualSemanticsResolver()
        )
        self.priority_resolver = (
            priority_resolver
            or VisualPriorityResolver()
        )

    def analyze(
        self,
        scene: StoryboardScene
    ) -> VisualAnalysisResult:
        if not isinstance(
            scene,
            StoryboardScene
        ):
            raise TypeError(
                "VisualAnalysisOrchestrator expects a StoryboardScene."
            )

        inspection = self.inspector.inspect(
            scene
        )
        semantics = self.semantics_resolver.resolve(
            scene,
            inspection
        )
        priority = self.priority_resolver.resolve(
            scene,
            inspection,
            semantics
        )
        findings = inspection.findings
        trace = specialized_trace(
            "visual_analysis",
            (
                inspection.trace.entries
                if inspection.trace
                else ()
            )
            + (
                semantics.trace.entries
                if semantics.trace
                else ()
            )
            + (
                priority.trace.entries
                if priority.trace
                else ()
            ),
            (
                inspection.trace.evidences
                if inspection.trace
                else ()
            )
            + (
                semantics.trace.evidences
                if semantics.trace
                else ()
            )
            + (
                priority.trace.evidences
                if priority.trace
                else ()
            ),
        )
        return VisualAnalysisResult(
            inspection=inspection,
            semantics=semantics,
            priority=priority,
            findings=findings,
            trace=trace,
            status=self._status(
                findings
            ),
            version="visual-analysis-v1",
        )

    def _status(
        self,
        findings
    ) -> ResolutionStatus:
        return status_from_findings(
            findings
        )
