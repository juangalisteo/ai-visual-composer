from app.domain import (
    CertaintyLevel,
    DerivationKind,
    StoryboardScene,
    VisualInspectionResult,
    VisualSemantics,
)
from app.visual_intelligence.analysis.rules import clean, tuple_values
from app.visual_intelligence.analysis.support import (
    evidence_for,
    specialized_trace,
    trace_entry,
)


class VisualSemanticsResolver:
    component_name = "VisualSemanticsResolver"

    def resolve(
        self,
        scene: StoryboardScene,
        inspection: VisualInspectionResult
    ) -> VisualSemantics:
        if not isinstance(
            scene,
            StoryboardScene
        ):
            raise TypeError(
                "VisualSemanticsResolver expects a StoryboardScene."
            )
        if not isinstance(
            inspection,
            VisualInspectionResult
        ):
            raise TypeError(
                "VisualSemanticsResolver expects a VisualInspectionResult."
            )

        evidences = self._evidences(
            scene,
            inspection
        )
        entries = self._trace_entries(
            scene
        )
        return VisualSemantics(
            primary_subject=clean(
                scene.visible_subject
            ) or "unknown",
            secondary_subjects=(),
            narrative_objects=tuple_values(
                scene.key_objects
            ),
            active_environment=clean(
                scene.visible_environment
            ),
            contextual_environment=clean(
                scene.time_context
            ),
            observable_action=clean(
                scene.visible_action
            ),
            visual_state=(
                ""
                if clean(
                    scene.visible_action
                )
                else clean(
                    scene.filmable_interpretation
                )
            ),
            filmable_interpretation=clean(
                scene.filmable_interpretation
            ),
            spatial_relationships=tuple_values(
                scene.spatial_relationships
            ),
            ambiguity_level=self._ambiguity_level(
                inspection
            ),
            evidences=evidences,
            trace=specialized_trace(
                "visual_semantics",
                entries,
                evidences
            ),
        )

    def _ambiguity_level(
        self,
        inspection: VisualInspectionResult
    ) -> CertaintyLevel:
        if inspection.ambiguous_fields:
            return CertaintyLevel.WEAK
        if inspection.missing_fields:
            return CertaintyLevel.MODERATE
        return CertaintyLevel.EXPLICIT

    def _evidences(
        self,
        scene: StoryboardScene,
        inspection: VisualInspectionResult
    ):
        evidences = []
        mappings = (
            (
                "visible_subject",
                scene.visible_subject,
                "primary_subject_from_visible_subject",
            ),
            (
                "key_objects",
                scene.key_objects,
                "narrative_objects_from_key_objects",
            ),
            (
                "visible_environment",
                scene.visible_environment,
                "active_environment_from_visible_environment",
            ),
            (
                "time_context",
                scene.time_context,
                "contextual_environment_from_time_context",
            ),
            (
                "visible_action",
                scene.visible_action,
                "observable_action_from_visible_action",
            ),
            (
                "spatial_relationships",
                scene.spatial_relationships,
                "spatial_relationships_preserved",
            ),
        )
        for field_name, value, code in mappings:
            if _has_value(
                value
            ):
                evidences.append(
                    evidence_for(
                        self.component_name,
                        field_name,
                        value,
                        DerivationKind.CLASSIFIED,
                        CertaintyLevel.EXPLICIT,
                        code,
                    )
                )
        for field_name in inspection.ambiguous_fields:
            evidences.append(
                evidence_for(
                    self.component_name,
                    field_name,
                    field_name,
                    DerivationKind.CLASSIFIED,
                    CertaintyLevel.WEAK,
                    "ambiguity_inherited_from_inspection",
                )
            )
        return tuple(
            evidences
        )

    def _trace_entries(
        self,
        scene: StoryboardScene
    ):
        entries = []
        mappings = (
            (
                "visible_subject",
                scene.visible_subject,
                "VisualSemantics.primary_subject",
            ),
            (
                "key_objects",
                scene.key_objects,
                "VisualSemantics.narrative_objects",
            ),
            (
                "visible_environment",
                scene.visible_environment,
                "VisualSemantics.active_environment",
            ),
            (
                "time_context",
                scene.time_context,
                "VisualSemantics.contextual_environment",
            ),
            (
                "visible_action",
                scene.visible_action,
                "VisualSemantics.observable_action",
            ),
            (
                "spatial_relationships",
                scene.spatial_relationships,
                "VisualSemantics.spatial_relationships",
            ),
        )
        for field_name, value, output_path in mappings:
            if _has_value(
                value
            ):
                entries.append(
                    trace_entry(
                        self.component_name,
                        field_name,
                        value,
                        "classify_visual_semantic_role",
                        output_path,
                        DerivationKind.CLASSIFIED,
                        CertaintyLevel.EXPLICIT,
                    )
                )
        return tuple(
            entries
        )


def _has_value(
    value
) -> bool:
    if isinstance(
        value,
        tuple
    ):
        return bool(
            tuple_values(
                value
            )
        )
    return bool(
        clean(
            value
        )
    )
