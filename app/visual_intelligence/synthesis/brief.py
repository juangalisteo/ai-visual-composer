from app.domain import (
    CertaintyLevel,
    DerivationKind,
    EffectiveVisualBrief,
    VisualAnalysisResult,
    VisualConflictReport,
    VisualReasoningResult,
)
from app.visual_intelligence.synthesis.support import (
    ensure_inputs,
    evidence_for,
    merge_evidences,
    merge_findings,
    specialized_trace,
    trace_entry,
    tuple_without_unknown,
)


class EffectiveVisualBriefSynthesizer:
    component_name = "EffectiveVisualBriefSynthesizer"

    def synthesize(
        self,
        analysis: VisualAnalysisResult,
        reasoning: VisualReasoningResult,
        conflicts: VisualConflictReport
    ) -> EffectiveVisualBrief:
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
                "EffectiveVisualBriefSynthesizer expects a VisualConflictReport."
            )

        evidences = self._evidences(
            analysis,
            reasoning,
            conflicts
        )
        entries = self._trace_entries(
            analysis,
            reasoning,
            conflicts
        )
        findings = merge_findings(
            analysis.findings,
            reasoning.findings,
            conflicts.findings
        )

        return EffectiveVisualBrief(
            primary_identity=(
                analysis.semantics.primary_subject
                if analysis.semantics.primary_subject != "unknown"
                else "unknown"
            ),
            secondary_identities=analysis.semantics.secondary_subjects,
            primary_actions=tuple_without_unknown(
                (
                    analysis.semantics.observable_action,
                )
            ),
            secondary_actions=tuple_without_unknown(
                (
                    analysis.semantics.visual_state,
                )
            ),
            narrative_objectives=tuple_without_unknown(
                (
                    reasoning.scene_intent.emotional_function,
                    reasoning.scene_intent.narrative_tension,
                )
            ),
            visual_priorities=tuple_without_unknown(
                (
                    analysis.priority.primary_priority,
                )
                + analysis.priority.secondary_priorities
            ),
            semantic_hierarchy=analysis.priority.visual_hierarchy,
            continuity=reasoning.continuity,
            restrictions=reasoning.strategy.visual_limits,
            strategy=reasoning.strategy,
            subtext=reasoning.scene_intent.visual_subtext,
            emotional_function=reasoning.scene_intent.emotional_function,
            uncertainty=reasoning.scene_intent.uncertainty,
            conflicts=conflicts.conflicts,
            findings=findings,
            evidences=evidences,
            trace=specialized_trace(
                "effective_visual_brief",
                entries,
                evidences
            ),
        )

    def _evidences(
        self,
        analysis: VisualAnalysisResult,
        reasoning: VisualReasoningResult,
        conflicts: VisualConflictReport
    ):
        return merge_evidences(
            analysis.semantics.evidences,
            analysis.priority.evidences,
            reasoning.scene_intent.evidences,
            reasoning.strategy.evidences,
            reasoning.continuity.evidences,
            (
                evidence_for(
                    self.component_name,
                    "VisualConflictReport.conflicts",
                    conflicts.conflicts,
                    conflicts.fingerprint,
                    DerivationKind.AGGREGATED,
                    CertaintyLevel.EXPLICIT,
                    "conflicts_preserved_in_effective_brief",
                ),
            ),
        )

    def _trace_entries(
        self,
        analysis: VisualAnalysisResult,
        reasoning: VisualReasoningResult,
        conflicts: VisualConflictReport
    ):
        return (
            trace_entry(
                self.component_name,
                "VisualAnalysisResult.semantics.primary_subject",
                analysis.semantics.primary_subject,
                analysis.fingerprint,
                "synthesize_primary_identity",
                "EffectiveVisualBrief.primary_identity",
                DerivationKind.AGGREGATED,
                analysis.semantics.ambiguity_level,
            ),
            trace_entry(
                self.component_name,
                "VisualAnalysisResult.priority.visual_hierarchy",
                analysis.priority.visual_hierarchy,
                analysis.fingerprint,
                "synthesize_visual_priorities",
                "EffectiveVisualBrief.visual_priorities",
                DerivationKind.AGGREGATED,
                CertaintyLevel.EXPLICIT,
            ),
            trace_entry(
                self.component_name,
                "VisualReasoningResult.scene_intent",
                reasoning.scene_intent.fingerprint,
                reasoning.fingerprint,
                "synthesize_scene_intent",
                "EffectiveVisualBrief.narrative_objectives",
                DerivationKind.AGGREGATED,
                reasoning.scene_intent.uncertainty,
            ),
            trace_entry(
                self.component_name,
                "VisualReasoningResult.strategy",
                reasoning.strategy.fingerprint,
                reasoning.fingerprint,
                "synthesize_strategy",
                "EffectiveVisualBrief.strategy",
                DerivationKind.AGGREGATED,
                CertaintyLevel.EXPLICIT,
            ),
            trace_entry(
                self.component_name,
                "VisualReasoningResult.continuity",
                reasoning.continuity.fingerprint,
                reasoning.fingerprint,
                "synthesize_continuity",
                "EffectiveVisualBrief.continuity",
                DerivationKind.AGGREGATED,
                CertaintyLevel.EXPLICIT,
            ),
            trace_entry(
                self.component_name,
                "VisualConflictReport.conflicts",
                conflicts.conflicts,
                conflicts.fingerprint,
                "preserve_conflicts",
                "EffectiveVisualBrief.conflicts",
                DerivationKind.AGGREGATED,
                CertaintyLevel.EXPLICIT,
            ),
        )
