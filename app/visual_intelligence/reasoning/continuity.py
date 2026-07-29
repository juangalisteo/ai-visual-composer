from app.domain import (
    CertaintyLevel,
    DerivationKind,
    FindingSeverity,
    SequenceContinuity,
    VisualAnalysisResult,
)
from app.visual_intelligence.analysis.rules import clean, dedupe
from app.visual_intelligence.reasoning.support import (
    ensure_analysis,
    evidence_for,
    finding_for,
    specialized_trace,
    trace_entry,
    trace_values_for_field,
)


class SequenceContinuityResolver:
    component_name = "SequenceContinuityResolver"

    def resolve(
        self,
        analysis: VisualAnalysisResult
    ) -> SequenceContinuity:
        ensure_analysis(
            analysis,
            self.component_name
        )

        characters = self._character_continuity(
            analysis
        )
        objects = self._object_continuity(
            analysis
        )
        locations = self._location_continuity(
            analysis
        )
        relationships = trace_values_for_field(
            analysis,
            "continuity_links"
        )
        visual = self._visual_continuity(
            analysis,
            relationships
        )
        risks = self._risks(
            analysis,
            relationships
        )
        evidences = self._evidences(
            analysis,
            characters,
            objects,
            locations,
            relationships
        )
        entries = self._trace_entries(
            analysis,
            characters,
            objects,
            locations,
            relationships
        )

        return SequenceContinuity(
            character_continuity=characters,
            object_continuity=objects,
            location_continuity=locations,
            visual_continuity=visual,
            scene_relationships=relationships,
            detected_risks=risks,
            evidences=evidences,
            trace=specialized_trace(
                "sequence_continuity",
                entries,
                evidences
            ),
        )

    def _character_continuity(
        self,
        analysis: VisualAnalysisResult
    ) -> tuple[str, ...]:
        subject = clean(
            analysis.semantics.primary_subject
        )
        if subject and subject != "unknown":
            return (
                subject,
            )
        return ()

    def _object_continuity(
        self,
        analysis: VisualAnalysisResult
    ) -> tuple[str, ...]:
        return tuple(
            item
            for item in analysis.semantics.narrative_objects
            if clean(
                item
            )
        )

    def _location_continuity(
        self,
        analysis: VisualAnalysisResult
    ) -> tuple[str, ...]:
        return dedupe(
            (
                analysis.semantics.active_environment,
                analysis.semantics.contextual_environment,
            )
        )

    def _visual_continuity(
        self,
        analysis: VisualAnalysisResult,
        relationships: tuple[str, ...]
    ) -> tuple[str, ...]:
        return dedupe(
            relationships
            + analysis.semantics.spatial_relationships
        )

    def _risks(
        self,
        analysis: VisualAnalysisResult,
        relationships: tuple[str, ...]
    ):
        if relationships or analysis.semantics.spatial_relationships:
            return ()
        evidence = evidence_for(
            self.component_name,
            "VisualAnalysisResult.trace.continuity_links",
            "",
            analysis,
            DerivationKind.CLASSIFIED,
            CertaintyLevel.MODERATE,
            "sequence_continuity_links_absent",
        )
        return (
            finding_for(
                "SEQUENCE_CONTINUITY_LINKS_ABSENT",
                "sequence_continuity",
                FindingSeverity.WARNING,
                "No explicit sequence continuity links were found.",
                evidence,
                (
                    "VisualAnalysisResult.trace",
                ),
            ),
        )

    def _evidences(
        self,
        analysis: VisualAnalysisResult,
        characters: tuple[str, ...],
        objects: tuple[str, ...],
        locations: tuple[str, ...],
        relationships: tuple[str, ...]
    ):
        return (
            evidence_for(
                self.component_name,
                "VisualAnalysisResult.semantics.primary_subject",
                characters,
                analysis,
                DerivationKind.CLASSIFIED,
                CertaintyLevel.EXPLICIT if characters else CertaintyLevel.UNKNOWN,
                "character_continuity_from_primary_subject",
            ),
            evidence_for(
                self.component_name,
                "VisualAnalysisResult.semantics.narrative_objects",
                objects,
                analysis,
                DerivationKind.CLASSIFIED,
                CertaintyLevel.EXPLICIT if objects else CertaintyLevel.UNKNOWN,
                "object_continuity_from_narrative_objects",
            ),
            evidence_for(
                self.component_name,
                "VisualAnalysisResult.semantics.active_environment",
                locations,
                analysis,
                DerivationKind.CLASSIFIED,
                CertaintyLevel.EXPLICIT if locations else CertaintyLevel.UNKNOWN,
                "location_continuity_from_environment",
            ),
            evidence_for(
                self.component_name,
                "VisualAnalysisResult.trace.continuity_links",
                relationships,
                analysis,
                DerivationKind.CLASSIFIED,
                CertaintyLevel.EXPLICIT if relationships else CertaintyLevel.UNKNOWN,
                "scene_relationships_from_continuity_links",
            ),
        )

    def _trace_entries(
        self,
        analysis: VisualAnalysisResult,
        characters: tuple[str, ...],
        objects: tuple[str, ...],
        locations: tuple[str, ...],
        relationships: tuple[str, ...]
    ):
        return (
            trace_entry(
                self.component_name,
                "VisualAnalysisResult.semantics.primary_subject",
                characters,
                analysis,
                "classify_character_continuity",
                "SequenceContinuity.character_continuity",
                DerivationKind.CLASSIFIED,
                CertaintyLevel.EXPLICIT if characters else CertaintyLevel.UNKNOWN,
            ),
            trace_entry(
                self.component_name,
                "VisualAnalysisResult.semantics.narrative_objects",
                objects,
                analysis,
                "classify_object_continuity",
                "SequenceContinuity.object_continuity",
                DerivationKind.CLASSIFIED,
                CertaintyLevel.EXPLICIT if objects else CertaintyLevel.UNKNOWN,
            ),
            trace_entry(
                self.component_name,
                "VisualAnalysisResult.semantics.active_environment",
                locations,
                analysis,
                "classify_location_continuity",
                "SequenceContinuity.location_continuity",
                DerivationKind.CLASSIFIED,
                CertaintyLevel.EXPLICIT if locations else CertaintyLevel.UNKNOWN,
            ),
            trace_entry(
                self.component_name,
                "VisualAnalysisResult.trace.continuity_links",
                relationships,
                analysis,
                "classify_scene_relationships",
                "SequenceContinuity.scene_relationships",
                DerivationKind.CLASSIFIED,
                CertaintyLevel.EXPLICIT if relationships else CertaintyLevel.UNKNOWN,
            ),
        )
