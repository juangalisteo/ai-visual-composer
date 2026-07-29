from app.domain import (
    CertaintyLevel,
    DerivationKind,
    FindingSeverity,
    ResolutionTraceEntry,
    SourceReference,
    SpecializedTrace,
    VisualIntelligenceEvidence,
    VisualIntelligenceFinding,
)
from app.visual_intelligence.analysis.rules import clean


def source_reference(
    component: str,
    field_name: str,
    value,
    source_fingerprint: str = ""
) -> SourceReference:
    return SourceReference(
        component=component,
        field=field_name,
        path=f"StoryboardScene.{field_name}",
        value=_stable_value(
            value
        ),
        source_fingerprint=source_fingerprint,
    )


def evidence_for(
    component: str,
    field_name: str,
    value,
    derivation_kind: DerivationKind,
    certainty: CertaintyLevel,
    explanation_code: str,
    details: tuple[str, ...] = ()
) -> VisualIntelligenceEvidence:
    return VisualIntelligenceEvidence(
        source=source_reference(
            component,
            field_name,
            value
        ),
        derivation_kind=derivation_kind,
        certainty=certainty,
        explanation_code=explanation_code,
        responsible_component=component,
        details=details,
    )


def trace_entry(
    component: str,
    field_name: str,
    value,
    operation: str,
    output_path: str,
    derivation_kind: DerivationKind,
    certainty: CertaintyLevel,
) -> ResolutionTraceEntry:
    return ResolutionTraceEntry(
        component=component,
        sources=(
            source_reference(
                component,
                field_name,
                value
            ),
        ),
        operation=operation,
        output_path=output_path,
        derivation_kind=derivation_kind,
        certainty=certainty,
    )


def finding_for(
    code: str,
    category: str,
    severity: FindingSeverity,
    message: str,
    evidence: VisualIntelligenceEvidence,
    affected_paths: tuple[str, ...],
    status: str = "open"
) -> VisualIntelligenceFinding:
    return VisualIntelligenceFinding(
        code=code,
        category=category,
        severity=severity,
        message=message,
        evidences=(
            evidence,
        ),
        affected_paths=affected_paths,
        status=status,
    )


def specialized_trace(
    resolution_type: str,
    entries: tuple[ResolutionTraceEntry, ...],
    evidences: tuple[VisualIntelligenceEvidence, ...]
) -> SpecializedTrace:
    return SpecializedTrace(
        resolution_type=resolution_type,
        entries=entries,
        evidences=evidences,
    )


def _stable_value(
    value
) -> str:
    if isinstance(
        value,
        tuple
    ):
        return " | ".join(
            clean(
                item
            )
            for item in value
            if clean(
                item
            )
        )
    return clean(
        value
    )
