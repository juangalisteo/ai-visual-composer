from app.domain import (
    CertaintyLevel,
    DerivationKind,
    FindingSeverity,
    ResolutionTraceEntry,
    SourceReference,
    SpecializedTrace,
    VisualAnalysisResult,
    VisualIntelligenceEvidence,
    VisualIntelligenceFinding,
)
from app.visual_intelligence.analysis.rules import clean, dedupe


def ensure_analysis(
    analysis: VisualAnalysisResult,
    component: str
) -> None:
    if not isinstance(
        analysis,
        VisualAnalysisResult
    ):
        raise TypeError(
            f"{component} expects a VisualAnalysisResult."
        )


def source_reference(
    component: str,
    path: str,
    value,
    analysis: VisualAnalysisResult
) -> SourceReference:
    field = path.split(
        "."
    )[-1]
    return SourceReference(
        component=component,
        field=field,
        path=path,
        value=stable_value(
            value
        ),
        source_fingerprint=analysis.fingerprint,
    )


def evidence_for(
    component: str,
    path: str,
    value,
    analysis: VisualAnalysisResult,
    derivation_kind: DerivationKind,
    certainty: CertaintyLevel,
    explanation_code: str,
    details: tuple[str, ...] = ()
) -> VisualIntelligenceEvidence:
    return VisualIntelligenceEvidence(
        source=source_reference(
            component,
            path,
            value,
            analysis
        ),
        derivation_kind=derivation_kind,
        certainty=certainty,
        explanation_code=explanation_code,
        responsible_component=component,
        details=details,
    )


def trace_entry(
    component: str,
    path: str,
    value,
    analysis: VisualAnalysisResult,
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
                path,
                value,
                analysis
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


def trace_values_for_field(
    analysis: VisualAnalysisResult,
    field_name: str
) -> tuple[str, ...]:
    values = []
    if analysis.trace:
        for evidence in analysis.trace.evidences:
            if evidence.source.field == field_name:
                values.extend(
                    split_stable_value(
                        evidence.source.value
                    )
                )
        for entry in analysis.trace.entries:
            for source in entry.sources:
                if source.field == field_name:
                    values.extend(
                        split_stable_value(
                            source.value
                        )
                    )
    return dedupe(
        values
    )


def stable_value(
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


def split_stable_value(
    value: str
) -> tuple[str, ...]:
    return tuple(
        item
        for item in (
            clean(
                part
            )
            for part in value.split(
                "|"
            )
        )
        if item
    )


def merge_findings(
    *groups: tuple[VisualIntelligenceFinding, ...]
) -> tuple[VisualIntelligenceFinding, ...]:
    result = []
    seen = set()
    for group in groups:
        for finding in group:
            if finding.fingerprint not in seen:
                seen.add(
                    finding.fingerprint
                )
                result.append(
                    finding
                )
    return tuple(
        result
    )
