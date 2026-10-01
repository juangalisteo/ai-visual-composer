"""Generic operational errors carrying neutral incident context."""

from collections.abc import Mapping
from typing import Any

from app.shared.error_context import ErrorContext, ErrorSeverity, ExitKind


def summarize_technical_text(value: object, limit: int = 500) -> str | None:
    """Keep a bounded diagnostic hint without exposing a full process log."""
    text = str(value or "").strip()
    if not text:
        return None
    return text[:limit]


class OperationalError(RuntimeError):
    """A non-presenting error for a domain edge with operational context.

    Callers preserve a library or domain failure with normal Python chaining:
    ``raise OperationalError(context) from error``.
    """

    def __init__(self, context: ErrorContext):
        if not isinstance(context, ErrorContext):
            raise TypeError("OperationalError requiere un ErrorContext.")
        self.context = context
        super().__init__(context.user_message)


def create_operational_error(
    *,
    family: str,
    user_message: str,
    recommended_action: str,
    operation: str,
    resource: str | None = None,
    diagnostic_reference: str | None = None,
    technical_metadata: Mapping[str, Any] | None = None,
) -> OperationalError:
    """Build one fatal operational error without presenting it.

    Domain boundaries provide the contextual values and preserve the original
    cause themselves with ``raise ... from error``.
    """
    return OperationalError(
        ErrorContext(
            family=family,
            severity=ErrorSeverity.FATAL_OPERATIONAL,
            user_message=user_message,
            recommended_action=recommended_action,
            operation=operation,
            resource=resource,
            diagnostic_reference=diagnostic_reference,
            technical_metadata=technical_metadata,
            exit_kind=ExitKind.OPERATIONAL_ERROR,
        )
    )
