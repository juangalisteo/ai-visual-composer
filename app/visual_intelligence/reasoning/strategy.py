from app.domain import (
    CertaintyLevel,
    DerivationKind,
    FindingSeverity,
    VisualAnalysisResult,
    VisualIntelligenceStrategy,
    VisualSceneIntent,
)
from app.visual_intelligence.analysis.rules import clean
from app.visual_intelligence.reasoning.support import (
    ensure_analysis,
    evidence_for,
    specialized_trace,
    trace_entry,
    trace_values_for_field,
)


class VisualStrategyResolver:
    component_name = "VisualStrategyResolver"

    def resolve(
        self,
        analysis: VisualAnalysisResult,
        scene_intent: VisualSceneIntent
    ) -> VisualIntelligenceStrategy:
        ensure_analysis(
            analysis,
            self.component_name
        )
        if not isinstance(
            scene_intent,
            VisualSceneIntent
        ):
            raise TypeError(
                "VisualStrategyResolver expects a VisualSceneIntent."
            )

        approach = self._representation_approach(
            analysis
        )
        realism = self._realism_level(
            analysis
        )
        symbolism = self._symbolism_degree(
            scene_intent
        )
        limits = trace_values_for_field(
            analysis,
            "visual_constraints"
        )
        avoid = self._resources_to_avoid(
            limits
        )
        conflicts = self._declared_conflicts(
            analysis
        )
        evidences = self._evidences(
            analysis,
            scene_intent,
            approach,
            realism,
            symbolism
        )
        entries = self._trace_entries(
            analysis,
            approach,
            realism,
            symbolism
        )

        return VisualIntelligenceStrategy(
            representation_approach=approach,
            realism_level=realism,
            symbolism_degree=symbolism,
            visual_limits=limits,
            resources_to_avoid=avoid,
            declared_conflicts=conflicts,
            evidences=evidences,
            trace=specialized_trace(
                "visual_strategy",
                entries,
                evidences
            ),
        )

    def _representation_approach(
        self,
        analysis: VisualAnalysisResult
    ) -> str:
        if analysis.inspection.completeness == "empty":
            return "preserve absence without enrichment"
        if analysis.inspection.specificity in (
            "detailed",
            "concrete",
        ):
            return "represent explicit Visual Truth directly"
        return "preserve ambiguity without enrichment"

    def _realism_level(
        self,
        analysis: VisualAnalysisResult
    ) -> str:
        if analysis.inspection.visual_density in (
            "dense",
            "saturated",
        ):
            return "source-constrained high detail"
        if analysis.inspection.visual_density in (
            "moderate",
            "sparse",
        ):
            return "source-constrained"
        return "unspecified"

    def _symbolism_degree(
        self,
        scene_intent: VisualSceneIntent
    ) -> str:
        subtext = clean(
            scene_intent.visual_subtext
        )
        if subtext and subtext != "unknown":
            return "evidence-bound"
        return "unspecified"

    def _resources_to_avoid(
        self,
        limits: tuple[str, ...]
    ) -> tuple[str, ...]:
        return tuple(
            limit
            for limit in limits
            if clean(
                limit
            ).lower().startswith(
                (
                    "no ",
                    "sin ",
                    "avoid ",
                    "without ",
                )
            )
        )

    def _declared_conflicts(
        self,
        analysis: VisualAnalysisResult
    ):
        return tuple(
            finding
            for finding in analysis.findings
            if finding.severity in (
                FindingSeverity.ERROR,
                FindingSeverity.BLOCKING,
            )
        )

    def _evidences(
        self,
        analysis: VisualAnalysisResult,
        scene_intent: VisualSceneIntent,
        approach: str,
        realism: str,
        symbolism: str
    ):
        certainty = (
            CertaintyLevel.WEAK
            if analysis.findings
            else CertaintyLevel.STRONG
        )
        return (
            evidence_for(
                self.component_name,
                "VisualAnalysisResult.inspection.specificity",
                approach,
                analysis,
                DerivationKind.INFERRED,
                certainty,
                "representation_approach_from_inspection",
            ),
            evidence_for(
                self.component_name,
                "VisualAnalysisResult.inspection.visual_density",
                realism,
                analysis,
                DerivationKind.INFERRED,
                certainty,
                "realism_level_from_visual_density",
            ),
            evidence_for(
                self.component_name,
                "VisualSceneIntent.visual_subtext",
                symbolism,
                analysis,
                DerivationKind.INFERRED,
                scene_intent.uncertainty,
                "symbolism_degree_from_scene_intent",
            ),
        )

    def _trace_entries(
        self,
        analysis: VisualAnalysisResult,
        approach: str,
        realism: str,
        symbolism: str
    ):
        certainty = (
            CertaintyLevel.WEAK
            if analysis.findings
            else CertaintyLevel.STRONG
        )
        return (
            trace_entry(
                self.component_name,
                "VisualAnalysisResult.inspection.specificity",
                approach,
                analysis,
                "derive_representation_approach",
                "VisualIntelligenceStrategy.representation_approach",
                DerivationKind.INFERRED,
                certainty,
            ),
            trace_entry(
                self.component_name,
                "VisualAnalysisResult.inspection.visual_density",
                realism,
                analysis,
                "derive_realism_level",
                "VisualIntelligenceStrategy.realism_level",
                DerivationKind.INFERRED,
                certainty,
            ),
            trace_entry(
                self.component_name,
                "VisualSceneIntent.visual_subtext",
                symbolism,
                analysis,
                "derive_symbolism_degree",
                "VisualIntelligenceStrategy.symbolism_degree",
                DerivationKind.INFERRED,
                certainty,
            ),
        )
