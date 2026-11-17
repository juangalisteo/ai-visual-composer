import time
import traceback

from app.cli.error_presenter import ErrorPresenter
from app.cli.studio_summary import print_studio_summary
from app.controllers.run_controller import RunController
from app.core.execution_request import StudioExecutionRequest
from app.core.start import run_application
from app.managers.font_manager import FontManager
from app.managers.output_manager import OutputManager
from app.modules.studio import (
    StudioMontageError,
    StudioVideoAudioSrtError,
    to_studio_operational_error,
)
from app.shared.error_context import ErrorContext, ErrorSeverity, ExitKind
from app.shared.format_catalog import FormatCatalog
from app.shared.internal_error_log import write_internal_error_log
from app.shared.operational_error import OperationalError
from app.shared.profile_resolver import ProfileResolver


def main():
    """Run the CLI with one final boundary for shared incident contracts."""
    try:
        return _run_main()
    except KeyboardInterrupt:
        _present_cancellation(
            "La operación fue interrumpida por el usuario.",
            operation="Ejecución principal",
        )
        return 130
    except EOFError:
        _present_cancellation(
            "La entrada de terminal finalizó antes de completar la selección.",
            operation="Selección de opciones",
        )
        return 0
    except OperationalError as error:
        _present_incident(ErrorPresenter().present_operational_error(error))
        if error.context.exit_kind is ExitKind.CANCELLATION:
            return 0
        return 1
    except Exception as error:
        _present_unexpected_error(error)
        return 1


def _run_main():
    # A broken format or font catalog fails here, before the first menu.
    FormatCatalog().validate(ProfileResolver())
    FontManager().validate()

    request = RunController().run()

    studio_route = (
        request.route
        if isinstance(request.route, StudioExecutionRequest)
        else None
    )
    if request.clear_output:
        OutputManager().reset()

    studio_start = time.perf_counter()
    try:
        result = run_application(request=request)
    except (
        StudioMontageError,
        StudioVideoAudioSrtError,
        ValueError,
    ) as error:
        if (
            isinstance(error, ValueError)
            and studio_route is None
        ):
            raise
        raise to_studio_operational_error(
            error,
            mode=(
                studio_route.input_mode.value
                if studio_route is not None
                else None
            ),
        ) from error

    if studio_route is not None:
        print_studio_summary(
            request,
            result,
            time.perf_counter() - studio_start,
        )

    return 0


def _present_unexpected_error(error):
    """Present an INTERNAL incident and keep its evidence in a log file."""
    operation = "Ejecución principal"
    error_traceback = "".join(traceback.format_exception(error))
    context = ErrorContext(
        family="INTERNAL",
        severity=ErrorSeverity.FATAL_INTERNAL,
        user_message="Se produjo un error interno inesperado.",
        exit_kind=ExitKind.INTERNAL_ERROR,
        operation=operation,
        diagnostic_reference=write_internal_error_log(
            error,
            error_traceback,
            operation=operation,
        ),
        technical_metadata={
            "exception_type": type(error).__name__,
            "traceback": error_traceback,
        },
    )
    _present_incident(ErrorPresenter().present_context(context))


def _present_cancellation(user_message, *, operation):
    """Present a terminal cancellation without treating it as INTERNAL."""
    _present_incident(
        ErrorPresenter().present_context(
            ErrorContext(
                family="CANCELLATION",
                severity=ErrorSeverity.RECOVERABLE,
                user_message=user_message,
                exit_kind=ExitKind.CANCELLATION,
                operation=operation,
            )
        )
    )


def _present_incident(presentation):
    """Write already-resolved presentation content at the terminal boundary."""
    print(presentation.text)


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
