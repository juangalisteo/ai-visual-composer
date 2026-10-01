"""Structured, non-fatal warnings associated with one operation."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from app.shared.error_context import (
    freeze_technical_metadata,
    normalize_optional_text,
    normalize_required_text,
)


@dataclass(frozen=True)
class OperationWarning:
    """A degradative notice that never prints or raises by itself."""

    family: str
    user_message: str
    operation: str | None = None
    recommended_action: str | None = None
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
            "user_message",
            normalize_required_text(self.user_message, "user_message"),
        )
        for field_name in (
            "operation",
            "recommended_action",
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


class OperationWarnings:
    """Per-operation warning collection with no shared default state."""

    def __init__(self, warnings: Iterable[OperationWarning] = ()):
        self._warnings = []
        self._keys = set()
        for warning in warnings:
            self.add(warning)

    def add(self, warning: OperationWarning):
        if not isinstance(warning, OperationWarning):
            raise TypeError("OperationWarnings solo admite OperationWarning.")
        key = self._key_for(warning)
        if key in self._keys:
            return False
        self._keys.add(key)
        self._warnings.append(warning)
        return True

    def snapshot(self) -> tuple[OperationWarning, ...]:
        return tuple(self._warnings)

    def __len__(self):
        return len(self._warnings)

    def __iter__(self):
        return iter(self.snapshot())

    @staticmethod
    def _key_for(warning: OperationWarning):
        """Identify one visible degradation within one operation."""
        return (
            warning.family,
            warning.user_message,
            warning.operation,
            warning.resource,
        )
