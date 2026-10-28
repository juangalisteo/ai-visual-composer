"""STUDIO context for execution errors that reach the CLI boundary."""

from app.shared.operational_error import OperationalError, create_operational_error


def to_studio_operational_error(error, mode, resource=None):
    """Contextualize a STUDIO execution error once at its CLI boundary."""
    if isinstance(error, OperationalError):
        return error
    return create_operational_error(
        family="STUDIO",
        user_message=str(error),
        recommended_action="Revisa los recursos de STUDIO y vuelve a intentarlo.",
        operation=f"STUDIO/{mode or 'ejecución'}",
        resource=str(resource) if resource is not None else None,
        technical_metadata={"exception_type": type(error).__name__},
    )
