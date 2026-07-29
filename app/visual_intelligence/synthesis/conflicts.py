from app.domain import (
    CertaintyLevel,
    DerivationKind,
    FindingSeverity,
    ResolutionStatus,
    SourceReference,
    VisualAnalysisResult,
    VisualConflict,
    VisualConflictReport,
    VisualIntelligenceFinding,
    VisualReasoningResult,
)
from app.visual_intelligence.analysis.rules import status_from_findings
from app.visual_intelligence.synthesis.support import (
    ensure_inputs,
    evidence_for,
    merge_findings,
    source_reference,
    specialized_trace,
    trace_entry,
)


class VisualConflictResolver:
    component_name = "VisualConflictResolver"

    def resolve(
        self,
        analysis: VisualAnalysisResult,
        reasoning: VisualReasoningResult
    ) -> VisualConflictReport:
        ensure_inputs(
            analysis,
            reasoning,
            self.component_name
        )

        conflicts = self._conflicts(
            analysis,
            reasoning
        )
        findings = merge_findings(
            analysis.findings,
            reasoning.findings,
            tuple(
                self._finding_from_conflict(
                    conflict
                )
                for conflict in conflicts
            )
        )
        evidences = tuple(
            evidence
            for conflict in conflicts
            for evidence in conflict.evidences
        )
        entries = tuple(
            entry
            for conflict in conflicts
            if conflict.trace
            for entry in conflict.trace.entries
        )

        return VisualConflictReport(
            conflicts=conflicts,
            findings=findings,
            trace=specialized_trace(
                "visual_conflict_report",
                entries,
                evidences
            ),
            status=self._status(
                findings
            ),
            version="visual-conflict-report-v1",
        )

    def _conflicts(
        self,
        analysis: VisualAnalysisResult,
        reasoning: VisualReasoningResult
    ) -> tuple[VisualConflict, ...]:
        conflicts = []
        for finding in merge_findings(
            analysis.findings,
            reasoning.findings,
            reasoning.strategy.declared_conflicts,
            reasoning.continuity.detected_risks
        ):
            conflicts.append(
                self._conflict_from_finding(
                    analysis,
                    reasoning,
                    finding
                )
            )
        if (
            reasoning.strategy.resources_to_avoid
            and not reasoning.strategy.visual_limits
        ):
            conflicts.append(
                self._strategy_constraint_conflict(
                    analysis,
                    reasoning
                )
            )
        return tuple(
            conflicts
        )

    def _conflict_from_finding(
        self,
        analysis: VisualAnalysisResult,
        reasoning: VisualReasoningResult,
        finding: VisualIntelligenceFinding
    ) -> VisualConflict:
        evidence = (
            finding.evidences[0]
            if finding.evidences
            else evidence_for(
                self.component_name,
                "VisualReasoningResult.findings",
                finding.code,
                reasoning.fingerprint,
                DerivationKind.CLASSIFIED,
                CertaintyLevel.MODERATE,
                "conflict_from_finding_without_evidence",
            )
        )
        origin = SourceReference(
            component=self.component_name,
            field=finding.category,
            path="VisualReasoningResult.findings",
            value=finding.code,
            source_fingerprint=reasoning.fingerprint,
        )
        trace = specialized_trace(
            "visual_conflict",
            (
                trace_entry(
                    self.component_name,
                    "VisualReasoningResult.findings",
                    finding.code,
                    reasoning.fingerprint,
                    "classify_existing_finding_as_visual_conflict",
                    "VisualConflict.conflict",
                    DerivationKind.CLASSIFIED,
                    evidence.certainty,
                ),
            ),
            (
                evidence,
            ),
        )
        return VisualConflict(
            conflict=finding.code,
            category=finding.category,
            severity=finding.severity,
            origin=origin,
            involved_components=self._involved_components(
                evidence,
                analysis,
                reasoning
            ),
            passive_recommendation="preserve_conflict_for_synthesis",
            evidences=(
                evidence,
            ),
            trace=trace,
        )

    def _strategy_constraint_conflict(
        self,
        analysis: VisualAnalysisResult,
        reasoning: VisualReasoningResult
    ) -> VisualConflict:
        evidence = evidence_for(
            self.component_name,
            "VisualReasoningResult.strategy.resources_to_avoid",
            reasoning.strategy.resources_to_avoid,
            reasoning.fingerprint,
            DerivationKind.CLASSIFIED,
            CertaintyLevel.STRONG,
            "avoidance_resource_without_visual_limit",
        )
        origin = source_reference(
            self.component_name,
            "VisualReasoningResult.strategy.resources_to_avoid",
            reasoning.strategy.resources_to_avoid,
            reasoning.fingerprint
        )
        trace = specialized_trace(
            "visual_conflict",
            (
                trace_entry(
                    self.component_name,
                    "VisualReasoningResult.strategy.resources_to_avoid",
                    reasoning.strategy.resources_to_avoid,
                    reasoning.fingerprint,
                    "classify_strategy_constraint_conflict",
                    "VisualConflict.conflict",
                    DerivationKind.CLASSIFIED,
                    CertaintyLevel.STRONG,
                ),
            ),
            (
                evidence,
            ),
        )
        return VisualConflict(
            conflict="VISUAL_STRATEGY_AVOIDANCE_WITHOUT_LIMIT",
            category="visual_strategy",
            severity=FindingSeverity.INFO,
            origin=origin,
            involved_components=(
                "VisualStrategyResolver",
                self.component_name,
            ),
            passive_recommendation="preserve_declared_avoidance",
            evidences=(
                evidence,
            ),
            trace=trace,
        )

    def _finding_from_conflict(
        self,
        conflict: VisualConflict
    ) -> VisualIntelligenceFinding:
        return VisualIntelligenceFinding(
            code=conflict.conflict,
            category=conflict.category,
            severity=conflict.severity,
            message="Visual conflict preserved by synthesis.",
            evidences=conflict.evidences,
            affected_paths=(
                conflict.origin.path,
            ),
        )

    def _involved_components(
        self,
        evidence,
        analysis: VisualAnalysisResult,
        reasoning: VisualReasoningResult
    ) -> tuple[str, ...]:
        components = (
            evidence.responsible_component,
            self.component_name,
        )
        if evidence.source.source_fingerprint == analysis.fingerprint:
            components += (
                "VisualAnalysisResult",
            )
        if evidence.source.source_fingerprint == reasoning.fingerprint:
            components += (
                "VisualReasoningResult",
            )
        return tuple(
            dict.fromkeys(
                item
                for item in components
                if item
            )
        )

    def _status(
        self,
        findings
    ) -> ResolutionStatus:
        return status_from_findings(
            findings
        )
