from app.domain import (
    CertaintyLevel,
    ColorPlan,
    CompositionPlan,
    DerivationKind,
    EffectiveVisualBrief,
    LightingPlan,
    MotionSense,
    PhotographyPlan,
    StagingPlan,
    VisualStrategy,
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
        conflicts: VisualConflictReport,
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
            visible_content=self._visible_content(
                analysis
            ),
            visible_subject=analysis.semantics.primary_subject,
            visible_action=analysis.semantics.observable_action,
            visible_environment=analysis.semantics.active_environment,
            time_context=analysis.semantics.contextual_environment,
            key_objects=analysis.semantics.narrative_objects,
            spatial_relationships=analysis.semantics.spatial_relationships,
            continuity_links=(
                reasoning.continuity.character_continuity
                + reasoning.continuity.object_continuity
                + reasoning.continuity.location_continuity
                + reasoning.continuity.visual_continuity
                + reasoning.continuity.scene_relationships
            ),
            abstract_source=reasoning.scene_intent.visual_subtext,
            filmable_interpretation=self._filmable_interpretation(
                analysis
            ),
            visual_constraints=reasoning.strategy.visual_limits,
            visual_truth_status=analysis.inspection.completeness,
            felt_experience=reasoning.scene_intent.emotional_function,
            narrative_composition=reasoning.scene_intent.narrative_tension,
            visual_priority=analysis.priority.primary_priority,
            primary_identity=(
                analysis.semantics.primary_subject
                if analysis.semantics.primary_subject != "unknown"
                else "unknown"
            ),
            primary_subject=analysis.semantics.primary_subject,
            secondary_subject=self._secondary_subject(
                analysis
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
            attention_focus=analysis.priority.attention_focus,
            dominant_visual_intention=reasoning.strategy.representation_approach,
            visual_reading=reasoning.scene_intent.visual_subtext,
            scene_rhythm=reasoning.scene_intent.narrative_tension,
            symbolic_weight=reasoning.strategy.symbolism_degree,
            visual_continuity=" | ".join(
                reasoning.continuity.visual_continuity
            ),
            visual_bible_coherence=reasoning.strategy.realism_level,
            narrative_coherence=analysis.inspection.consistency,
            intention_coherence=reasoning.scene_intent.emotional_function,
            visual_strategy=VisualStrategy(
                representation_approach=reasoning.strategy.representation_approach,
                realism_level=reasoning.strategy.realism_level,
                symbolism_degree=reasoning.strategy.symbolism_degree,
                visual_limits=reasoning.strategy.visual_limits,
                resources_to_avoid=reasoning.strategy.resources_to_avoid,
            ),
            staging=StagingPlan(
                main_subject=analysis.semantics.primary_subject,
                environment=analysis.semantics.active_environment,
                action_or_state=analysis.semantics.observable_action,
                spatial_relationship=" | ".join(
                    analysis.semantics.spatial_relationships
                ),
                significant_objects=analysis.semantics.narrative_objects,
                human_presence=analysis.semantics.primary_subject,
                narrative_distribution=" | ".join(
                    analysis.priority.visual_hierarchy
                ),
            ),
            photography=PhotographyPlan(
                point_of_view=analysis.priority.attention_focus,
                emotional_distance=reasoning.scene_intent.emotional_function,
                depth=" | ".join(
                    analysis.semantics.spatial_relationships
                ),
                photographic_atmosphere=analysis.semantics.contextual_environment,
                photographic_realism=reasoning.strategy.realism_level,
            ),
            composition=CompositionPlan(
                visual_hierarchy=" | ".join(
                    analysis.priority.visual_hierarchy
                ),
                framing=analysis.priority.attention_focus,
                frame_scale=analysis.priority.primary_priority,
                reading_direction=" | ".join(
                    analysis.semantics.spatial_relationships
                ),
                figure_ground_relationship=analysis.semantics.active_environment,
            ),
            lighting=LightingPlan(
                source=analysis.semantics.contextual_environment or "unknown",
                motivation=reasoning.scene_intent.emotional_function,
                atmosphere=analysis.semantics.contextual_environment,
                visibility=analysis.inspection.specificity,
            ),
            color=ColorPlan(
                temperature=analysis.semantics.contextual_environment or "unknown",
                harmony=reasoning.scene_intent.emotional_function,
                visual_identity_relationship=reasoning.strategy.realism_level,
            ),
            motion=MotionSense(
                latent_energy=reasoning.scene_intent.narrative_tension or "unknown",
                rhythm=reasoning.scene_intent.narrative_tension,
                stillness=analysis.semantics.visual_state,
                direction=analysis.semantics.observable_action,
                progression_or_suspension=reasoning.scene_intent.visual_subtext,
            ),
            continuity_relationship=" | ".join(
                reasoning.continuity.scene_relationships
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
            conflicts=conflicts,
            findings=findings,
            evidences=evidences,
            trace=specialized_trace(
                "effective_brief",
                entries,
                evidences
            ),
        )

    def _visible_content(
        self,
        analysis: VisualAnalysisResult
    ) -> str:
        return " | ".join(
            tuple_without_unknown(
                (
                    analysis.semantics.primary_subject,
                    analysis.semantics.observable_action,
                    analysis.semantics.active_environment,
                    analysis.semantics.contextual_environment,
                )
            )
        )

    def _filmable_interpretation(
        self,
        analysis: VisualAnalysisResult
    ) -> str:
        if analysis.semantics.filmable_interpretation:
            return analysis.semantics.filmable_interpretation
        return " | ".join(
            tuple_without_unknown(
                (
                    analysis.semantics.primary_subject,
                    analysis.semantics.observable_action,
                    analysis.semantics.active_environment,
                )
            )
        )

    def _secondary_subject(
        self,
        analysis: VisualAnalysisResult
    ) -> str:
        candidates = (
            analysis.semantics.secondary_subjects
            + analysis.semantics.narrative_objects
        )
        if candidates:
            return candidates[0]
        return ""

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
