from app.domain import (
    CertaintyLevel,
    DerivationKind,
    VisualAnalysisResult,
    VisualSceneIntent,
)
from app.visual_intelligence.analysis.rules import clean
from app.visual_intelligence.reasoning.support import (
    ensure_analysis,
    evidence_for,
    specialized_trace,
    trace_entry,
)


class SceneIntentResolver:
    component_name = "SceneIntentResolver"

    def resolve(
        self,
        analysis: VisualAnalysisResult
    ) -> VisualSceneIntent:
        ensure_analysis(
            analysis,
            self.component_name
        )

        emotional_function = self._emotional_function(
            analysis
        )
        narrative_tension = self._narrative_tension(
            analysis
        )
        visual_subtext = self._visual_subtext(
            analysis
        )
        uncertainty = self._uncertainty(
            analysis
        )
        evidences = self._evidences(
            analysis,
            emotional_function,
            narrative_tension,
            visual_subtext,
            uncertainty
        )
        entries = self._trace_entries(
            analysis,
            emotional_function,
            narrative_tension,
            visual_subtext,
            uncertainty
        )

        return VisualSceneIntent(
            emotional_function=emotional_function,
            narrative_tension=narrative_tension,
            visual_subtext=visual_subtext,
            uncertainty=uncertainty,
            evidences=evidences,
            trace=specialized_trace(
                "scene_intent",
                entries,
                evidences
            ),
        )

    def _emotional_function(
        self,
        analysis: VisualAnalysisResult
    ) -> str:
        focus = clean(
            analysis.priority.attention_focus
        )
        if focus:
            return f"hold attention on {focus}"
        subject = clean(
            analysis.semantics.primary_subject
        )
        if subject and subject != "unknown":
            return f"hold attention on {subject}"
        return "unknown"

    def _narrative_tension(
        self,
        analysis: VisualAnalysisResult
    ) -> str:
        action = clean(
            analysis.semantics.observable_action
        )
        if action and analysis.semantics.narrative_objects:
            return "object-driven observable tension"
        if action:
            return "action-driven observable tension"
        if clean(
            analysis.semantics.visual_state
        ):
            return "state-driven visual tension"
        return "unknown"

    def _visual_subtext(
        self,
        analysis: VisualAnalysisResult
    ) -> str:
        primary = clean(
            analysis.priority.primary_priority
        )
        action = clean(
            analysis.semantics.observable_action
        )
        state = clean(
            analysis.semantics.visual_state
        )
        if primary and primary != "unknown" and action:
            return f"{primary} carries the observable action"
        if state:
            return state
        return "unknown"

    def _uncertainty(
        self,
        analysis: VisualAnalysisResult
    ) -> CertaintyLevel:
        if analysis.inspection.completeness == "empty":
            return CertaintyLevel.UNKNOWN
        return analysis.semantics.ambiguity_level

    def _evidences(
        self,
        analysis: VisualAnalysisResult,
        emotional_function: str,
        narrative_tension: str,
        visual_subtext: str,
        uncertainty: CertaintyLevel
    ):
        return (
            evidence_for(
                self.component_name,
                "VisualAnalysisResult.priority.attention_focus",
                emotional_function,
                analysis,
                DerivationKind.INFERRED,
                uncertainty,
                "emotional_function_from_attention_focus",
            ),
            evidence_for(
                self.component_name,
                "VisualAnalysisResult.semantics.observable_action",
                narrative_tension,
                analysis,
                DerivationKind.INFERRED,
                uncertainty,
                "narrative_tension_from_observable_action",
            ),
            evidence_for(
                self.component_name,
                "VisualAnalysisResult.priority.primary_priority",
                visual_subtext,
                analysis,
                DerivationKind.INFERRED,
                uncertainty,
                "visual_subtext_from_primary_priority",
            ),
        )

    def _trace_entries(
        self,
        analysis: VisualAnalysisResult,
        emotional_function: str,
        narrative_tension: str,
        visual_subtext: str,
        uncertainty: CertaintyLevel
    ):
        return (
            trace_entry(
                self.component_name,
                "VisualAnalysisResult.priority.attention_focus",
                emotional_function,
                analysis,
                "derive_scene_emotional_function",
                "VisualSceneIntent.emotional_function",
                DerivationKind.INFERRED,
                uncertainty,
            ),
            trace_entry(
                self.component_name,
                "VisualAnalysisResult.semantics.observable_action",
                narrative_tension,
                analysis,
                "derive_scene_narrative_tension",
                "VisualSceneIntent.narrative_tension",
                DerivationKind.INFERRED,
                uncertainty,
            ),
            trace_entry(
                self.component_name,
                "VisualAnalysisResult.priority.primary_priority",
                visual_subtext,
                analysis,
                "derive_scene_visual_subtext",
                "VisualSceneIntent.visual_subtext",
                DerivationKind.INFERRED,
                uncertainty,
            ),
        )
