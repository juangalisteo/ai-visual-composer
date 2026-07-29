from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any, Generic, TypeVar


SCHEMA_VERSION = "1.0.0"


class DerivationKind(Enum):
    COPIED = "copied"
    NORMALIZED = "normalized"
    INFERRED = "inferred"
    CLASSIFIED = "classified"
    PRIORITIZED = "prioritized"
    AGGREGATED = "aggregated"


class CertaintyLevel(Enum):
    EXPLICIT = "explicit"
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    UNKNOWN = "unknown"


class FindingSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    BLOCKING = "blocking"


class ResolutionStatus(Enum):
    READY = "ready"
    WARNING = "warning"
    ERROR = "error"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class SourceReference:
    component: str
    field: str = ""
    path: str = ""
    value: str = ""
    source_fingerprint: str = ""
    fingerprint: str = ""

    def __post_init__(self) -> None:
        _require_text(
            self.component,
            "component"
        )
        _set_fingerprint(
            self,
            "SourceReference",
            (
                "component",
                "field",
                "path",
                "value",
                "source_fingerprint",
            )
        )


@dataclass(frozen=True)
class VisualIntelligenceEvidence:
    source: SourceReference
    derivation_kind: DerivationKind
    certainty: CertaintyLevel
    explanation_code: str
    responsible_component: str
    details: tuple[str, ...] = field(default_factory=tuple)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        _require_type(
            self.source,
            SourceReference,
            "source"
        )
        _require_enum(
            self.derivation_kind,
            DerivationKind,
            "derivation_kind"
        )
        _require_enum(
            self.certainty,
            CertaintyLevel,
            "certainty"
        )
        _require_text(
            self.explanation_code,
            "explanation_code"
        )
        _require_text(
            self.responsible_component,
            "responsible_component"
        )
        _set_fingerprint(
            self,
            "VisualIntelligenceEvidence",
            (
                "source",
                "derivation_kind",
                "certainty",
                "explanation_code",
                "responsible_component",
                "details",
            )
        )


@dataclass(frozen=True)
class VisualIntelligenceFinding:
    code: str
    category: str
    severity: FindingSeverity
    message: str
    evidences: tuple[VisualIntelligenceEvidence, ...] = field(default_factory=tuple)
    affected_paths: tuple[str, ...] = field(default_factory=tuple)
    status: str = "open"
    fingerprint: str = ""

    def __post_init__(self) -> None:
        _require_text(
            self.code,
            "code"
        )
        _require_text(
            self.category,
            "category"
        )
        _require_enum(
            self.severity,
            FindingSeverity,
            "severity"
        )
        _require_text(
            self.message,
            "message"
        )
        _require_sequence_of(
            self.evidences,
            VisualIntelligenceEvidence,
            "evidences"
        )
        _set_fingerprint(
            self,
            "VisualIntelligenceFinding",
            (
                "code",
                "category",
                "severity",
                "message",
                "evidences",
                "affected_paths",
                "status",
            )
        )


@dataclass(frozen=True)
class ResolutionTraceEntry:
    component: str
    sources: tuple[SourceReference, ...]
    operation: str
    output_path: str
    derivation_kind: DerivationKind
    certainty: CertaintyLevel
    fingerprint: str = ""

    def __post_init__(self) -> None:
        _require_text(
            self.component,
            "component"
        )
        _require_sequence_of(
            self.sources,
            SourceReference,
            "sources"
        )
        _require_text(
            self.operation,
            "operation"
        )
        _require_text(
            self.output_path,
            "output_path"
        )
        _require_enum(
            self.derivation_kind,
            DerivationKind,
            "derivation_kind"
        )
        _require_enum(
            self.certainty,
            CertaintyLevel,
            "certainty"
        )
        _set_fingerprint(
            self,
            "ResolutionTraceEntry",
            (
                "component",
                "sources",
                "operation",
                "output_path",
                "derivation_kind",
                "certainty",
            )
        )


ResultT = TypeVar(
    "ResultT"
)


@dataclass(frozen=True)
class VisualIntelligenceResolutionResult(Generic[ResultT]):
    result: ResultT
    findings: tuple[VisualIntelligenceFinding, ...] = field(default_factory=tuple)
    trace: tuple[ResolutionTraceEntry, ...] = field(default_factory=tuple)
    status: ResolutionStatus = ResolutionStatus.READY
    schema_version: str = SCHEMA_VERSION
    version: str = SCHEMA_VERSION
    fingerprint: str = ""

    def __post_init__(self) -> None:
        _require_sequence_of(
            self.findings,
            VisualIntelligenceFinding,
            "findings"
        )
        _require_sequence_of(
            self.trace,
            ResolutionTraceEntry,
            "trace"
        )
        _require_enum(
            self.status,
            ResolutionStatus,
            "status"
        )
        _require_text(
            self.schema_version,
            "schema_version"
        )
        _require_text(
            self.version,
            "version"
        )
        _set_fingerprint(
            self,
            "VisualIntelligenceResolutionResult",
            (
                "result",
                "findings",
                "trace",
                "status",
                "schema_version",
                "version",
            )
        )


@dataclass(frozen=True)
class SpecializedTrace:
    resolution_type: str
    entries: tuple[ResolutionTraceEntry, ...] = field(default_factory=tuple)
    evidences: tuple[VisualIntelligenceEvidence, ...] = field(default_factory=tuple)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        _require_text(
            self.resolution_type,
            "resolution_type"
        )
        _require_sequence_of(
            self.entries,
            ResolutionTraceEntry,
            "entries"
        )
        _require_sequence_of(
            self.evidences,
            VisualIntelligenceEvidence,
            "evidences"
        )
        _set_fingerprint(
            self,
            "SpecializedTrace",
            (
                "resolution_type",
                "entries",
                "evidences",
            )
        )


@dataclass(frozen=True)
class VisualInspectionResult:
    completeness: str
    consistency: str
    visual_density: str = ""
    specificity: str = ""
    missing_fields: tuple[str, ...] = field(default_factory=tuple)
    ambiguous_fields: tuple[str, ...] = field(default_factory=tuple)
    findings: tuple[VisualIntelligenceFinding, ...] = field(default_factory=tuple)
    trace: SpecializedTrace | None = None
    fingerprint: str = ""

    def __post_init__(self) -> None:
        _require_text(
            self.completeness,
            "completeness"
        )
        _require_text(
            self.consistency,
            "consistency"
        )
        _require_sequence_of(
            self.findings,
            VisualIntelligenceFinding,
            "findings"
        )
        _require_optional_type(
            self.trace,
            SpecializedTrace,
            "trace"
        )
        _set_fingerprint(
            self,
            "VisualInspectionResult",
            (
                "completeness",
                "consistency",
                "visual_density",
                "specificity",
                "missing_fields",
                "ambiguous_fields",
                "findings",
                "trace",
            )
        )


@dataclass(frozen=True)
class VisualSemantics:
    primary_subject: str
    secondary_subjects: tuple[str, ...] = field(default_factory=tuple)
    narrative_objects: tuple[str, ...] = field(default_factory=tuple)
    active_environment: str = ""
    contextual_environment: str = ""
    observable_action: str = ""
    visual_state: str = ""
    spatial_relationships: tuple[str, ...] = field(default_factory=tuple)
    ambiguity_level: CertaintyLevel = CertaintyLevel.UNKNOWN
    evidences: tuple[VisualIntelligenceEvidence, ...] = field(default_factory=tuple)
    trace: SpecializedTrace | None = None
    fingerprint: str = ""

    def __post_init__(self) -> None:
        _require_text(
            self.primary_subject,
            "primary_subject"
        )
        _require_enum(
            self.ambiguity_level,
            CertaintyLevel,
            "ambiguity_level"
        )
        _require_sequence_of(
            self.evidences,
            VisualIntelligenceEvidence,
            "evidences"
        )
        _require_optional_type(
            self.trace,
            SpecializedTrace,
            "trace"
        )
        _set_fingerprint(
            self,
            "VisualSemantics",
            (
                "primary_subject",
                "secondary_subjects",
                "narrative_objects",
                "active_environment",
                "contextual_environment",
                "observable_action",
                "visual_state",
                "spatial_relationships",
                "ambiguity_level",
                "evidences",
                "trace",
            )
        )


@dataclass(frozen=True)
class VisualPriority:
    primary_priority: str
    secondary_priorities: tuple[str, ...] = field(default_factory=tuple)
    attention_focus: str = ""
    supporting_elements: tuple[str, ...] = field(default_factory=tuple)
    visual_hierarchy: tuple[str, ...] = field(default_factory=tuple)
    evidences: tuple[VisualIntelligenceEvidence, ...] = field(default_factory=tuple)
    trace: SpecializedTrace | None = None
    fingerprint: str = ""

    def __post_init__(self) -> None:
        _require_text(
            self.primary_priority,
            "primary_priority"
        )
        _require_sequence_of(
            self.evidences,
            VisualIntelligenceEvidence,
            "evidences"
        )
        _require_optional_type(
            self.trace,
            SpecializedTrace,
            "trace"
        )
        _set_fingerprint(
            self,
            "VisualPriority",
            (
                "primary_priority",
                "secondary_priorities",
                "attention_focus",
                "supporting_elements",
                "visual_hierarchy",
                "evidences",
                "trace",
            )
        )


@dataclass(frozen=True)
class VisualSceneIntent:
    emotional_function: str
    narrative_tension: str = ""
    visual_subtext: str = ""
    uncertainty: CertaintyLevel = CertaintyLevel.UNKNOWN
    evidences: tuple[VisualIntelligenceEvidence, ...] = field(default_factory=tuple)
    trace: SpecializedTrace | None = None
    fingerprint: str = ""

    def __post_init__(self) -> None:
        _require_text(
            self.emotional_function,
            "emotional_function"
        )
        _require_enum(
            self.uncertainty,
            CertaintyLevel,
            "uncertainty"
        )
        _require_sequence_of(
            self.evidences,
            VisualIntelligenceEvidence,
            "evidences"
        )
        _require_optional_type(
            self.trace,
            SpecializedTrace,
            "trace"
        )
        _set_fingerprint(
            self,
            "VisualSceneIntent",
            (
                "emotional_function",
                "narrative_tension",
                "visual_subtext",
                "uncertainty",
                "evidences",
                "trace",
            )
        )


@dataclass(frozen=True)
class VisualIntelligenceStrategy:
    representation_approach: str
    realism_level: str = ""
    symbolism_degree: str = ""
    visual_limits: tuple[str, ...] = field(default_factory=tuple)
    resources_to_avoid: tuple[str, ...] = field(default_factory=tuple)
    declared_conflicts: tuple[VisualIntelligenceFinding, ...] = field(default_factory=tuple)
    evidences: tuple[VisualIntelligenceEvidence, ...] = field(default_factory=tuple)
    trace: SpecializedTrace | None = None
    fingerprint: str = ""

    def __post_init__(self) -> None:
        _require_text(
            self.representation_approach,
            "representation_approach"
        )
        _require_sequence_of(
            self.declared_conflicts,
            VisualIntelligenceFinding,
            "declared_conflicts"
        )
        _require_sequence_of(
            self.evidences,
            VisualIntelligenceEvidence,
            "evidences"
        )
        _require_optional_type(
            self.trace,
            SpecializedTrace,
            "trace"
        )
        _set_fingerprint(
            self,
            "VisualIntelligenceStrategy",
            (
                "representation_approach",
                "realism_level",
                "symbolism_degree",
                "visual_limits",
                "resources_to_avoid",
                "declared_conflicts",
                "evidences",
                "trace",
            )
        )


@dataclass(frozen=True)
class SequenceContinuity:
    character_continuity: tuple[str, ...] = field(default_factory=tuple)
    object_continuity: tuple[str, ...] = field(default_factory=tuple)
    location_continuity: tuple[str, ...] = field(default_factory=tuple)
    visual_continuity: tuple[str, ...] = field(default_factory=tuple)
    scene_relationships: tuple[str, ...] = field(default_factory=tuple)
    detected_risks: tuple[VisualIntelligenceFinding, ...] = field(default_factory=tuple)
    evidences: tuple[VisualIntelligenceEvidence, ...] = field(default_factory=tuple)
    trace: SpecializedTrace | None = None
    fingerprint: str = ""

    def __post_init__(self) -> None:
        _require_sequence_of(
            self.detected_risks,
            VisualIntelligenceFinding,
            "detected_risks"
        )
        _require_sequence_of(
            self.evidences,
            VisualIntelligenceEvidence,
            "evidences"
        )
        _require_optional_type(
            self.trace,
            SpecializedTrace,
            "trace"
        )
        _set_fingerprint(
            self,
            "SequenceContinuity",
            (
                "character_continuity",
                "object_continuity",
                "location_continuity",
                "visual_continuity",
                "scene_relationships",
                "detected_risks",
                "evidences",
                "trace",
            )
        )


@dataclass(frozen=True)
class VisualConflict:
    conflict: str
    category: str
    severity: FindingSeverity
    origin: SourceReference
    involved_components: tuple[str, ...] = field(default_factory=tuple)
    passive_recommendation: str = ""
    evidences: tuple[VisualIntelligenceEvidence, ...] = field(default_factory=tuple)
    trace: SpecializedTrace | None = None
    fingerprint: str = ""

    def __post_init__(self) -> None:
        _require_text(
            self.conflict,
            "conflict"
        )
        _require_text(
            self.category,
            "category"
        )
        _require_enum(
            self.severity,
            FindingSeverity,
            "severity"
        )
        _require_type(
            self.origin,
            SourceReference,
            "origin"
        )
        _require_sequence_of(
            self.evidences,
            VisualIntelligenceEvidence,
            "evidences"
        )
        _require_optional_type(
            self.trace,
            SpecializedTrace,
            "trace"
        )
        _set_fingerprint(
            self,
            "VisualConflict",
            (
                "conflict",
                "category",
                "severity",
                "origin",
                "involved_components",
                "passive_recommendation",
                "evidences",
                "trace",
            )
        )


def deterministic_fingerprint(
    label: str,
    value: Any
) -> str:
    canonical = {
        label: _canonical_mapping(
            value
        )
    }
    return hashlib.sha256(
        json.dumps(
            canonical,
            sort_keys=True,
            separators=(
                ",",
                ":"
            )
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def _set_fingerprint(
    instance: Any,
    label: str,
    fields: tuple[str, ...]
) -> None:
    canonical = {
        field_name: getattr(
            instance,
            field_name
        )
        for field_name in fields
    }
    object.__setattr__(
        instance,
        "fingerprint",
        deterministic_fingerprint(
            label,
            canonical
        )
    )


def _canonical_mapping(
    value: Any
) -> Any:
    if isinstance(
        value,
        Enum
    ):
        return value.value
    if is_dataclass(
        value
    ):
        return {
            key: _canonical_mapping(
                item
            )
            for key, item in asdict(
                value
            ).items()
            if key != "fingerprint"
        }
    if isinstance(
        value,
        dict
    ):
        return {
            key: _canonical_mapping(
                item
            )
            for key, item in sorted(
                value.items()
            )
        }
    if isinstance(
        value,
        (
            tuple,
            list,
        )
    ):
        return [
            _canonical_mapping(
                item
            )
            for item in value
        ]
    return value


def _require_text(
    value: str,
    field_name: str
) -> None:
    if not isinstance(
        value,
        str
    ) or not value.strip():
        raise ValueError(
            f"{field_name} must be a non-empty string."
        )


def _require_enum(
    value: Any,
    enum_type: type[Enum],
    field_name: str
) -> None:
    if not isinstance(
        value,
        enum_type
    ):
        raise ValueError(
            f"{field_name} must be a {enum_type.__name__} value."
        )


def _require_type(
    value: Any,
    expected_type: type,
    field_name: str
) -> None:
    if not isinstance(
        value,
        expected_type
    ):
        raise ValueError(
            f"{field_name} must be a {expected_type.__name__}."
        )


def _require_optional_type(
    value: Any,
    expected_type: type,
    field_name: str
) -> None:
    if value is None:
        return
    _require_type(
        value,
        expected_type,
        field_name
    )


def _require_sequence_of(
    values: tuple[Any, ...],
    expected_type: type,
    field_name: str
) -> None:
    if not isinstance(
        values,
        tuple
    ):
        raise ValueError(
            f"{field_name} must be a tuple."
        )
    for value in values:
        _require_type(
            value,
            expected_type,
            field_name
        )
