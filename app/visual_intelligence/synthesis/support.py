from app.domain import (
    CertaintyLevel,
    DerivationKind,
    ResolutionTraceEntry,
    SourceReference,
    SpecializedTrace,
    VisualAnalysisResult,
    VisualIntelligenceEvidence,
    VisualIntelligenceFinding,
    VisualReasoningResult,
)
from app.visual_intelligence.analysis.rules import clean, dedupe


def ensure_inputs(
    analysis: VisualAnalysisResult,
    reasoning: VisualReasoningResult,
    component: str
) -> None:
    if not isinstance(
        analysis,
        VisualAnalysisResult
    ):
        raise TypeError(
            f"{component} expects a VisualAnalysisResult."
        )
    if not isinstance(
        reasoning,
        VisualReasoningResult
    ):
        raise TypeError(
            f"{component} expects a VisualReasoningResult."
        )


def source_reference(
    component: str,
    path: str,
    value,
    source_fingerprint: str
) -> SourceReference:
    return SourceReference(
        component=component,
        field=path.split(
            "."
        )[-1],
        path=path,
        value=stable_value(
            value
        ),
        source_fingerprint=source_fingerprint,
    )


def evidence_for(
    component: str,
    path: str,
    value,
    source_fingerprint: str,
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
            source_fingerprint
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
    source_fingerprint: str,
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
                source_fingerprint
            ),
        ),
        operation=operation,
        output_path=output_path,
        derivation_kind=derivation_kind,
        certainty=certainty,
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


def merge_evidences(
    *groups: tuple[VisualIntelligenceEvidence, ...]
) -> tuple[VisualIntelligenceEvidence, ...]:
    result = []
    seen = set()
    for group in groups:
        for evidence in group:
            if evidence.fingerprint not in seen:
                seen.add(
                    evidence.fingerprint
                )
                result.append(
                    evidence
                )
    return tuple(
        result
    )


def merge_sources(
    *groups: tuple[SourceReference, ...]
) -> tuple[SourceReference, ...]:
    result = []
    seen = set()
    for group in groups:
        for source in group:
            if source.fingerprint not in seen:
                seen.add(
                    source.fingerprint
                )
                result.append(
                    source
                )
    return tuple(
        result
    )


def sources_from_trace(
    trace: SpecializedTrace | None
) -> tuple[SourceReference, ...]:
    if not trace:
        return ()
    sources = []
    for evidence in trace.evidences:
        sources.append(
            evidence.source
        )
    for entry in trace.entries:
        sources.extend(
            entry.sources
        )
    return tuple(
        sources
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


def tuple_without_unknown(
    values
) -> tuple[str, ...]:
    return tuple(
        value
        for value in dedupe(
            values
        )
        if value != "unknown"
    )
