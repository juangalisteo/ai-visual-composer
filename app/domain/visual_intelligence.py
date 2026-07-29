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


PayloadT = TypeVar(
    "PayloadT"
)


@dataclass(frozen=True)
class VisualIntelligenceResolutionResult(Generic[PayloadT]):
    result: PayloadT
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
