from app.domain import (
    CertaintyLevel,
    DerivationKind,
    FindingSeverity,
    StoryboardScene,
    VisualInspectionResult,
)
from app.visual_intelligence.analysis.rules import (
    REQUIRED_VISUAL_TRUTH_FIELDS,
    SEQUENCE_FIELDS,
    VISUAL_TRUTH_FIELDS,
    clean,
    is_ambiguous,
    tuple_values,
    visual_truth_value,
    visual_truth_values,
)
from app.visual_intelligence.analysis.support import (
    evidence_for,
    finding_for,
    specialized_trace,
    trace_entry,
)


class VisualTruthInspector:
    component_name = "VisualTruthInspector"

    def inspect(
        self,
        scene: StoryboardScene
    ) -> VisualInspectionResult:
        if not isinstance(
            scene,
            StoryboardScene
        ):
            raise TypeError(
                "VisualTruthInspector expects a StoryboardScene."
            )

        missing_fields = self._missing_fields(
            scene
        )
        ambiguous_fields = self._ambiguous_fields(
            scene
        )
        findings = (
            self._findings(
                scene,
                missing_fields,
                ambiguous_fields
            )
        )
        evidences = self._evidences(
            scene
        )
        entries = self._trace_entries(
            scene
        )

        return VisualInspectionResult(
            completeness=self._completeness(
                scene,
                missing_fields
            ),
            consistency=self._consistency(
                findings
            ),
            visual_density=self._density(
                scene
            ),
            specificity=self._specificity(
                scene,
                ambiguous_fields
            ),
            missing_fields=missing_fields,
            ambiguous_fields=ambiguous_fields,
            findings=findings,
            trace=specialized_trace(
                "visual_inspection",
                entries,
                evidences
            ),
        )

    def _missing_fields(
        self,
        scene: StoryboardScene
    ) -> tuple[str, ...]:
        return tuple(
            field_name
            for field_name in REQUIRED_VISUAL_TRUTH_FIELDS
            if not self._field_has_value(
                scene,
                field_name
            )
        )

    def _ambiguous_fields(
        self,
        scene: StoryboardScene
    ) -> tuple[str, ...]:
        ambiguous = []
        for field_name in (
            "visible_subject",
            "visible_action",
            "visible_environment",
            "filmable_interpretation",
        ):
            if is_ambiguous(
                clean(
                    visual_truth_value(
                        scene,
                        field_name
                    )
                )
            ):
                ambiguous.append(
                    field_name
                )
        return tuple(
            ambiguous
        )

    def _findings(
        self,
        scene: StoryboardScene,
        missing_fields: tuple[str, ...],
        ambiguous_fields: tuple[str, ...]
    ):
        findings = []
        if not visual_truth_values(
            scene
        ):
            evidence = evidence_for(
                self.component_name,
                "visual_truth",
                "",
                DerivationKind.CLASSIFIED,
                CertaintyLevel.EXPLICIT,
                "visual_truth_empty",
            )
            findings.append(
                finding_for(
                    "VISUAL_TRUTH_EMPTY_SCENE",
                    "completeness",
                    FindingSeverity.BLOCKING,
                    "Visual Truth contains no visual data.",
                    evidence,
                    (
                        "StoryboardScene",
                    ),
                )
            )
        for field_name in missing_fields:
            evidence = evidence_for(
                self.component_name,
                field_name,
                "",
                DerivationKind.CLASSIFIED,
                CertaintyLevel.EXPLICIT,
                "required_field_missing",
            )
            findings.append(
                finding_for(
                    "VISUAL_TRUTH_REQUIRED_FIELD_MISSING",
                    "completeness",
                    FindingSeverity.WARNING,
                    f"Required Visual Truth field is missing: {field_name}.",
                    evidence,
                    (
                        f"StoryboardScene.{field_name}",
                    ),
                )
            )
        for field_name in ambiguous_fields:
            value = visual_truth_value(
                scene,
                field_name
            )
            evidence = evidence_for(
                self.component_name,
                field_name,
                value,
                DerivationKind.CLASSIFIED,
                CertaintyLevel.WEAK,
                "field_ambiguous",
            )
            findings.append(
                finding_for(
                    "VISUAL_TRUTH_FIELD_AMBIGUOUS",
                    "specificity",
                    FindingSeverity.WARNING,
                    f"Visual Truth field is ambiguous: {field_name}.",
                    evidence,
                    (
                        f"StoryboardScene.{field_name}",
                    ),
                )
            )
        if (
            clean(
                scene.visible_action
            )
            and not clean(
                scene.visible_subject
            )
        ):
            evidence = evidence_for(
                self.component_name,
                "visible_action",
                scene.visible_action,
                DerivationKind.CLASSIFIED,
                CertaintyLevel.STRONG,
                "action_without_subject",
            )
            findings.append(
                finding_for(
                    "VISUAL_TRUTH_DIRECT_INCONSISTENCY",
                    "consistency",
                    FindingSeverity.ERROR,
                    "Visible action exists without a visible subject.",
                    evidence,
                    (
                        "StoryboardScene.visible_action",
                        "StoryboardScene.visible_subject",
                    ),
                )
            )
        if (
            scene.spatial_relationships
            and not (
                clean(
                    scene.visible_subject
                )
                or clean(
                    scene.visible_environment
                )
                or tuple_values(
                    scene.key_objects
                )
            )
        ):
            evidence = evidence_for(
                self.component_name,
                "spatial_relationships",
                scene.spatial_relationships,
                DerivationKind.CLASSIFIED,
                CertaintyLevel.STRONG,
                "spatial_relationship_without_elements",
            )
            findings.append(
                finding_for(
                    "VISUAL_TRUTH_DIRECT_INCONSISTENCY",
                    "consistency",
                    FindingSeverity.ERROR,
                    "Spatial relationships exist without visible elements.",
                    evidence,
                    (
                        "StoryboardScene.spatial_relationships",
                    ),
                )
            )
        if self._specificity(
            scene,
            ambiguous_fields
        ) in (
            "absent",
            "general",
        ) and visual_truth_values(
            scene
        ):
            evidence = evidence_for(
                self.component_name,
                "visual_truth",
                visual_truth_values(
                    scene
                ),
                DerivationKind.CLASSIFIED,
                CertaintyLevel.MODERATE,
                "low_specificity",
            )
            findings.append(
                finding_for(
                    "VISUAL_TRUTH_LOW_SPECIFICITY",
                    "specificity",
                    FindingSeverity.WARNING,
                    "Visual Truth has low specificity.",
                    evidence,
                    (
                        "StoryboardScene",
                    ),
                )
            )
        return tuple(
            findings
        )

    def _evidences(
        self,
        scene: StoryboardScene
    ):
        evidences = []
        for field_name in VISUAL_TRUTH_FIELDS:
            value = visual_truth_value(
                scene,
                field_name
            )
            if self._field_has_value(
                scene,
                field_name
            ):
                evidences.append(
                    evidence_for(
                        self.component_name,
                        field_name,
                        value,
                        DerivationKind.COPIED,
                        CertaintyLevel.EXPLICIT,
                        "visual_truth_field_present",
                    )
                )
        return tuple(
            evidences
        )

    def _trace_entries(
        self,
        scene: StoryboardScene
    ):
        return tuple(
            trace_entry(
                self.component_name,
                field_name,
                visual_truth_value(
                    scene,
                    field_name
                ),
                "inspect_visual_truth_field",
                f"VisualInspectionResult.{field_name}",
                DerivationKind.CLASSIFIED,
                CertaintyLevel.EXPLICIT,
            )
            for field_name in VISUAL_TRUTH_FIELDS
            if self._field_has_value(
                scene,
                field_name
            )
        )

    def _completeness(
        self,
        scene: StoryboardScene,
        missing_fields: tuple[str, ...]
    ) -> str:
        if not visual_truth_values(
            scene
        ):
            return "empty"
        if not missing_fields:
            return "complete"
        present_required = len(
            REQUIRED_VISUAL_TRUTH_FIELDS
        ) - len(
            missing_fields
        )
        if present_required >= 2:
            return "partial"
        return "minimal"

    def _consistency(
        self,
        findings
    ) -> str:
        if any(
            finding.category == "consistency"
            and finding.severity == FindingSeverity.ERROR
            for finding in findings
        ):
            return "inconsistent"
        return "consistent"

    def _density(
        self,
        scene: StoryboardScene
    ) -> str:
        score = 0
        for field_name in (
            "visible_subject",
            "visible_action",
            "visible_environment",
            "time_context",
            "abstract_source",
            "filmable_interpretation",
        ):
            if clean(
                visual_truth_value(
                    scene,
                    field_name
                )
            ):
                score += 1
        for field_name in SEQUENCE_FIELDS:
            score += len(
                tuple_values(
                    visual_truth_value(
                        scene,
                        field_name
                    )
                )
            )
        if score == 0:
            return "empty"
        if score <= 2:
            return "sparse"
        if score <= 5:
            return "moderate"
        if score <= 10:
            return "dense"
        return "saturated"

    def _specificity(
        self,
        scene: StoryboardScene,
        ambiguous_fields: tuple[str, ...]
    ) -> str:
        values = visual_truth_values(
            scene
        )
        if not values:
            return "absent"
        if ambiguous_fields:
            return "general"
        longest = max(
            len(
                value.split()
            )
            for value in values
        )
        total = sum(
            len(
                value.split()
            )
            for value in values
        )
        if longest >= 5 or total >= 12:
            return "detailed"
        return "concrete"

    def _field_has_value(
        self,
        scene: StoryboardScene,
        field_name: str
    ) -> bool:
        value = visual_truth_value(
            scene,
            field_name
        )
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
