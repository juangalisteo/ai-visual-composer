"""STUDIO context for execution errors that reach the CLI boundary."""

from app.shared.operational_error import OperationalError, create_operational_error


SRT_INPUT_ACTION = (
    "Pon en esa carpeta un SRT en UTF-8, con bloques de número, tiempos y "
    "texto, y vuelve a intentarlo."
)


def to_studio_operational_error(
    error,
    mode,
    resource=None,
    recommended_action="Revisa los recursos de STUDIO y vuelve a intentarlo.",
):
    """Contextualize a STUDIO execution error once at its CLI boundary."""
    if isinstance(error, OperationalError):
        return error
    return create_operational_error(
        family="STUDIO",
        user_message=str(error),
        recommended_action=recommended_action,
        operation=f"STUDIO/{mode or 'ejecución'}",
        resource=str(resource) if resource is not None else None,
        technical_metadata={"exception_type": type(error).__name__},
    )
