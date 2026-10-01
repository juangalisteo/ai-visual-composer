"""STUDIO context adapter for legacy execution errors."""

from app.shared.operational_error import OperationalError, create_operational_error


def adapt_legacy_studio_error(error, mode, resource=None):
    """Contextualize a legacy STUDIO execution error once at its CLI boundary."""
    if isinstance(error, OperationalError):
        return error
    return create_operational_error(
        family="STUDIO",
        user_message=str(error),
        recommended_action="Revisa los recursos de STUDIO y vuelve a intentarlo.",
        operation=f"STUDIO/{mode or 'ejecucion'}",
        resource=str(resource) if resource is not None else None,
        technical_metadata={"legacy_exception_type": type(error).__name__},
    )
