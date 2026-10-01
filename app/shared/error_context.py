"""Neutral contracts for operational incidents.

These types intentionally know nothing about a CLI, pipeline, provider, or
product profile. Domain edges may attach their own context later.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Any


class ErrorSeverity(str, Enum):
    RECOVERABLE = "recoverable"
    FATAL_OPERATIONAL = "fatal_operational"
    FATAL_INTERNAL = "fatal_internal"
    WARNING = "warning"


class ExitKind(str, Enum):
    SUCCESS = "success"
    CANCELLATION = "cancellation"
    OPERATIONAL_ERROR = "operational_error"
    INTERNAL_ERROR = "internal_error"


def normalize_required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} debe ser texto.")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} no puede estar vacío.")
    return normalized


def normalize_optional_text(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return normalize_required_text(value, field_name)


def freeze_technical_metadata(metadata: Mapping[str, Any] | None):
    """Return a deterministic, recursively immutable metadata mapping.

    Metadata is deliberately restricted to JSON-like scalar values, mappings
    and ordered sequences. This prevents shared mutable state from crossing an
    error boundary and keeps later diagnostic serialization predictable.
    """
    if metadata is None:
        return MappingProxyType({})
    if not isinstance(metadata, Mapping):
        raise TypeError("technical_metadata debe ser un mapping.")

    frozen = {}
    for key in sorted(metadata):
        if not isinstance(key, str) or not key.strip():
            raise ValueError(
                "technical_metadata requiere claves de texto no vacías."
            )
        frozen[key] = _freeze_metadata_value(metadata[key])
    return MappingProxyType(frozen)


def _freeze_metadata_value(value: Any):
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError(
                "technical_metadata no admite floats no finitos."
            )
        return value
    if isinstance(value, Mapping):
        return freeze_technical_metadata(value)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_metadata_value(item) for item in value)
    raise TypeError(
        "technical_metadata solo admite valores JSON-like inmutables."
    )


def coerce_error_severity(value: ErrorSeverity | str) -> ErrorSeverity:
    if isinstance(value, ErrorSeverity):
        return value
    try:
        return ErrorSeverity(normalize_required_text(value, "severity").lower())
    except ValueError as error:
        raise ValueError(f"severity no soportada: {value}.") from error


def coerce_exit_kind(value: ExitKind | str) -> ExitKind:
    if isinstance(value, ExitKind):
        return value
    try:
        return ExitKind(normalize_required_text(value, "exit_kind").lower())
    except ValueError as error:
        raise ValueError(f"exit_kind no soportado: {value}.") from error


@dataclass(frozen=True)
class ErrorContext:
    """Transportable, neutral context for one user-presentable incident."""

    family: str
    severity: ErrorSeverity | str
    user_message: str
    exit_kind: ExitKind | str
    recommended_action: str | None = None
    operation: str | None = None
    resource: str | None = None
    diagnostic_reference: str | None = None
    technical_metadata: Mapping[str, Any] | None = field(default=None)

    def __post_init__(self):
        object.__setattr__(
            self,
            "family",
            normalize_required_text(self.family, "family").upper(),
        )
        object.__setattr__(
            self,
            "severity",
            coerce_error_severity(self.severity),
        )
        object.__setattr__(
            self,
            "user_message",
            normalize_required_text(self.user_message, "user_message"),
        )
        object.__setattr__(
            self,
            "exit_kind",
            coerce_exit_kind(self.exit_kind),
        )
        for field_name in (
            "recommended_action",
            "operation",
            "resource",
            "diagnostic_reference",
        ):
            object.__setattr__(
                self,
                field_name,
                normalize_optional_text(getattr(self, field_name), field_name),
            )
        object.__setattr__(
            self,
            "technical_metadata",
            freeze_technical_metadata(self.technical_metadata),
        )
