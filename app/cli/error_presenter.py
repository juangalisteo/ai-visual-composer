"""Pure terminal presentation for neutral incident contracts.

This adapter intentionally receives already-classified shared contracts.  It
does not inspect domain exceptions, write diagnostics, or print by itself.
"""

from dataclasses import dataclass

from app.shared.error_context import ErrorContext, ErrorSeverity, ExitKind
from app.shared.operational_error import OperationalError
from app.shared.operation_warnings import OperationWarning


@dataclass(frozen=True)
class CliPresentation:
    """Deterministic, caller-renderable terminal content for one incident."""

    heading: str
    user_lines: tuple[str, ...]
    diagnostic_lines: tuple[str, ...] = ()

    @property
    def lines(self) -> tuple[str, ...]:
        """Return the complete visible output in stable display order."""
        return (self.heading, *self.user_lines, *self.diagnostic_lines)

    @property
    def text(self) -> str:
        """Return a plain-text rendering without writing to the terminal."""
        return "\n".join(self.lines)


class ErrorPresenter:
    """Translate shared incident contracts into safe terminal content."""

    def present(
        self,
        incident: ErrorContext | OperationalError | OperationWarning,
    ) -> CliPresentation:
        """Present one supported shared incident contract."""
        if isinstance(incident, OperationalError):
            return self.present_operational_error(incident)
        if isinstance(incident, ErrorContext):
            return self.present_context(incident)
        if isinstance(incident, OperationWarning):
            return self.present_warning(incident)
        raise TypeError("El presentador requiere un contrato de incidencia shared.")

    def present_operational_error(
        self,
        error: OperationalError,
    ) -> CliPresentation:
        """Present an operational wrapper without exposing its cause."""
        if not isinstance(error, OperationalError):
            raise TypeError("Se requiere un OperationalError.")
        return self.present_context(error.context)

    def present_context(self, context: ErrorContext) -> CliPresentation:
        """Present a resolved error, cancellation, or recoverable context."""
        if not isinstance(context, ErrorContext):
            raise TypeError("Se requiere un ErrorContext.")
        return self._presentation(
            heading=self._heading_for(context),
            user_message=context.user_message,
            operation=context.operation,
            resource=context.resource,
            recommended_action=context.recommended_action,
            diagnostic_reference=context.diagnostic_reference,
        )

    def present_warning(self, warning: OperationWarning) -> CliPresentation:
        """Present a non-fatal warning without turning it into an error."""
        if not isinstance(warning, OperationWarning):
            raise TypeError("Se requiere un OperationWarning.")
        return self._presentation(
            heading="AVISO",
            user_message=warning.user_message,
            operation=warning.operation,
            resource=warning.resource,
            recommended_action=warning.recommended_action,
            diagnostic_reference=warning.diagnostic_reference,
        )

    @staticmethod
    def _heading_for(context: ErrorContext) -> str:
        if context.exit_kind is ExitKind.CANCELLATION:
            return "CANCELADO"
        if (
            context.severity is ErrorSeverity.FATAL_INTERNAL
            or context.exit_kind is ExitKind.INTERNAL_ERROR
        ):
            return "ERROR INTERNO"
        if context.severity is ErrorSeverity.FATAL_OPERATIONAL:
            return "ERROR"
        if context.severity is ErrorSeverity.WARNING:
            return "AVISO"
        return "CORREGIR"

    @staticmethod
    def _presentation(
        *,
        heading: str,
        user_message: str,
        operation: str | None,
        resource: str | None,
        recommended_action: str | None,
        diagnostic_reference: str | None,
    ) -> CliPresentation:
        user_lines = [user_message]
        if operation:
            user_lines.append(f"Operación: {operation}")
        if resource:
            user_lines.append(f"Recurso: {resource}")
        if recommended_action:
            user_lines.append(f"Acción recomendada: {recommended_action}")

        diagnostic_lines = ()
        if diagnostic_reference:
            diagnostic_lines = (f"Diagnóstico técnico: {diagnostic_reference}",)
        return CliPresentation(
            heading=heading,
            user_lines=tuple(user_lines),
            diagnostic_lines=diagnostic_lines,
        )
