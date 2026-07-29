from app.domain import (
    CertaintyLevel,
    DerivationKind,
    StoryboardScene,
    VisualInspectionResult,
    VisualPriority,
    VisualSemantics,
)
from app.visual_intelligence.analysis.rules import clean, dedupe
from app.visual_intelligence.analysis.support import (
    evidence_for,
    specialized_trace,
    trace_entry,
)


class VisualPriorityResolver:
    component_name = "VisualPriorityResolver"

    def resolve(
        self,
        scene: StoryboardScene,
        inspection: VisualInspectionResult,
        semantics: VisualSemantics
    ) -> VisualPriority:
        if not isinstance(
            scene,
            StoryboardScene
        ):
            raise TypeError(
                "VisualPriorityResolver expects a StoryboardScene."
            )
        if not isinstance(
            inspection,
            VisualInspectionResult
        ):
            raise TypeError(
                "VisualPriorityResolver expects a VisualInspectionResult."
            )
        if not isinstance(
            semantics,
            VisualSemantics
        ):
            raise TypeError(
                "VisualPriorityResolver expects VisualSemantics."
            )

        hierarchy = self._hierarchy(
            semantics
        )
        primary = hierarchy[0] if hierarchy else "unknown"
        secondary = hierarchy[1:]
        evidences = self._evidences(
            scene,
            semantics,
            primary
        )
        entries = self._trace_entries(
            scene,
            primary
        )

        return VisualPriority(
            primary_priority=primary,
            secondary_priorities=secondary,
            attention_focus=(
                primary
                if primary != "unknown"
                else ""
            ),
            supporting_elements=self._supporting_elements(
                semantics,
                primary
            ),
            visual_hierarchy=hierarchy,
            evidences=evidences,
            trace=specialized_trace(
                "visual_priority",
                entries,
                evidences
            ),
        )

    def _hierarchy(
        self,
        semantics: VisualSemantics
    ) -> tuple[str, ...]:
        action = clean(
            semantics.observable_action
        )
        objects = semantics.narrative_objects
        object_in_action = tuple(
            item
            for item in objects
            if item and item.lower() in action.lower()
        )
        candidates = (
            object_in_action
            + (
                clean(
                    semantics.primary_subject
                ),
            )
            + objects
            + (
                action,
                clean(
                    semantics.active_environment
                ),
            )
        )
        return tuple(
            item
            for item in dedupe(
                candidates
            )
            if item != "unknown"
        )

    def _supporting_elements(
        self,
        semantics: VisualSemantics,
        primary: str
    ) -> tuple[str, ...]:
        return tuple(
            item
            for item in dedupe(
                semantics.narrative_objects
                + (
                    semantics.active_environment,
                    semantics.contextual_environment,
                )
            )
            if item and item != primary
        )

    def _evidences(
        self,
        scene: StoryboardScene,
        semantics: VisualSemantics,
        primary: str
    ):
        field_name = (
            "key_objects"
            if primary in semantics.narrative_objects
            else "visible_subject"
            if primary == semantics.primary_subject
            else "visible_action"
            if primary == semantics.observable_action
            else "visible_environment"
        )
        value = getattr(
            scene,
            field_name
        )
        return (
            evidence_for(
                self.component_name,
                field_name,
                value,
                DerivationKind.PRIORITIZED,
                CertaintyLevel.STRONG
                if primary != "unknown"
                else CertaintyLevel.UNKNOWN,
                "primary_priority_from_visual_semantics",
                (
                    f"primary_priority={primary}",
                ),
            ),
        )

    def _trace_entries(
        self,
        scene: StoryboardScene,
        primary: str
    ):
        field_name = "visible_subject"
        if primary in scene.key_objects:
            field_name = "key_objects"
        elif primary == clean(
            scene.visible_action
        ):
            field_name = "visible_action"
        elif primary == clean(
            scene.visible_environment
        ):
            field_name = "visible_environment"
        return (
            trace_entry(
                self.component_name,
                field_name,
                getattr(
                    scene,
                    field_name
                ),
                "prioritize_visual_elements",
                "VisualPriority.primary_priority",
                DerivationKind.PRIORITIZED,
                CertaintyLevel.STRONG
                if primary != "unknown"
                else CertaintyLevel.UNKNOWN,
            ),
        )
