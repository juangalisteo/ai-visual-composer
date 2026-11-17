import time

from app.core.pipeline_telemetry import PipelineTelemetry
from app.core.execution_request import (
    ApplicationExecutionRequest,
    DesignExecutionRequest,
    StandardExecutionRequest,
    StudioExecutionRequest,
)
from app.managers.project_manager import ProjectManager

from app.modules.design import DesignExecutionCoordinator
from app.modules.standard import StandardExecutionCoordinator
from app.modules.studio.execution_coordinator import (
    StudioExecutionCoordinator,
)

from app.shared.config_manager import ConfigManager


_PIPELINE_TELEMETRY = PipelineTelemetry()
_STUDIO_EXECUTION_COORDINATOR = StudioExecutionCoordinator()
_DESIGN_EXECUTION_COORDINATOR = DesignExecutionCoordinator(
    pipeline_telemetry=_PIPELINE_TELEMETRY,
)
_STANDARD_EXECUTION_COORDINATOR = StandardExecutionCoordinator(
    pipeline_telemetry=_PIPELINE_TELEMETRY,
)


def run_application(request):
    pipeline_start = time.perf_counter()

    if not isinstance(request, ApplicationExecutionRequest):
        raise TypeError(
            "request debe ser ApplicationExecutionRequest."
        )
    route = request.route
    if isinstance(route, StudioExecutionRequest):
        config_manager = _config_manager_for_operational_key(
            request.operational_profile_key
        )
        project = ProjectManager(project_name=request.project_name)
        return _STUDIO_EXECUTION_COORDINATOR.run_route(
            route=route,
            subtitle_profile_key=request.subtitle_profile_key,
            config_manager=config_manager,
            project=project,
        )

    project = ProjectManager(project_name=request.project_name)
    if isinstance(route, DesignExecutionRequest):
        design_config = _config_manager_for_operational_key(
            request.operational_profile_key
        )
        if route.mode == "design_image":
            return _DESIGN_EXECUTION_COORDINATOR.run_image(
                pipeline_start=pipeline_start,
                project=project,
                profile=design_config.get_profile_config(),
                ai_config=design_config.get_ai_config(),
            )
        return _DESIGN_EXECUTION_COORDINATOR.run_video(
            pipeline_start=pipeline_start,
            project=project,
            profile_key=request.operational_profile_key,
            config_manager=design_config,
        )

    if not isinstance(route, StandardExecutionRequest):
        raise TypeError("request contiene una ruta de ejecución no soportada.")
    config = _config_manager_for_operational_key(
        request.operational_profile_key,
        voice_config_id=route.voice_config_id,
    )
    return _STANDARD_EXECUTION_COORDINATOR.run(
        route=route,
        subtitle_profile_key=request.subtitle_profile_key,
        operational_profile_key=request.operational_profile_key,
        config_manager=config,
        project=project,
        pipeline_start=pipeline_start,
    )


def _config_manager_for_operational_key(
    operational_profile_key,
    *,
    voice_config_id=None,
):
    options = {}
    if operational_profile_key is not None:
        options["operational_profile_key"] = operational_profile_key
    if voice_config_id is not None:
        options["voice_config_id"] = voice_config_id
    return ConfigManager(**options)
