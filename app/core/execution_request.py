"""Pure typed transport contracts for application execution decisions.

``RunController`` builds an ``ApplicationExecutionRequest`` from the menu
choices and ``run_application`` dispatches it. The contracts only validate
their own fields: they do not read or write process environment, load
configuration, or invoke pipelines.
"""

from dataclasses import dataclass
from pathlib import Path
import re
from typing import TypeAlias

from app.modules.studio import (
    StudioInputMode,
    StudioIntroOutroPlan,
    StudioMontagePlan,
    StudioSubtitleExportMode,
    StudioSubtitleExportPlan,
    StudioVideoAudioSrtPlan,
    coerce_studio_input_mode,
)
from app.modules.video.intro_outro import IntroOutroPlan
from app.shared.profile_identity import (
    OperationalProfileKey,
    ProfileComponent,
)
from app.shared.subtitle_profile_identity import SubtitleProfileKey


_TECHNICAL_ID_PATTERN = re.compile(r"[a-z0-9]+(?:_[a-z0-9]+)*")
# The pipeline modes the menu offers for the standard route.
STANDARD_PIPELINE_MODES = (
    "full",
    "audio",
    "subtitles",
    "storyboard",
    "full_without_subtitles",
)
_STUDIO_PLAN_TYPES = (
    StudioVideoAudioSrtPlan,
    StudioIntroOutroPlan,
    StudioMontagePlan,
    StudioSubtitleExportPlan,
)

StudioExecutionPlan: TypeAlias = (
    StudioVideoAudioSrtPlan
    | StudioIntroOutroPlan
    | StudioMontagePlan
    | StudioSubtitleExportPlan
)


@dataclass(frozen=True)
class StandardExecutionRequest:
    """Already-resolved technical decisions for the standard pipeline."""

    pipeline_mode: str
    visual_pipeline: str
    script_source: str
    voice_config_id: str | None = None
    music_category: str | None = None
    overlays_mode: str | None = None
    intro_outro_plan: IntroOutroPlan | None = None

    def __post_init__(self):
        pipeline_mode = _require_non_empty_text(self.pipeline_mode, "pipeline_mode")
        if pipeline_mode not in STANDARD_PIPELINE_MODES:
            raise ValueError(
                f"La ruta estándar no admite el modo {pipeline_mode}. "
                f"Modos admitidos: {', '.join(STANDARD_PIPELINE_MODES)}."
            )
        object.__setattr__(self, "pipeline_mode", pipeline_mode)
        object.__setattr__(
            self,
            "visual_pipeline",
            _require_non_empty_text(self.visual_pipeline, "visual_pipeline"),
        )
        object.__setattr__(
            self,
            "script_source",
            _require_non_empty_text(self.script_source, "script_source"),
        )
        object.__setattr__(
            self,
            "voice_config_id",
            _coerce_technical_id(self.voice_config_id, "voice_config_id"),
        )
        object.__setattr__(
            self,
            "music_category",
            _coerce_optional_text(self.music_category, "music_category"),
        )
        object.__setattr__(
            self,
            "overlays_mode",
            _coerce_optional_text(self.overlays_mode, "overlays_mode"),
        )
        if (
            self.intro_outro_plan is not None
            and not isinstance(self.intro_outro_plan, IntroOutroPlan)
        ):
            raise TypeError("intro_outro_plan debe ser IntroOutroPlan o None.")


@dataclass(frozen=True)
class StudioExecutionRequest:
    """One STUDIO route with an existing typed plan kept intact."""

    input_mode: StudioInputMode
    plan: StudioExecutionPlan | None = None
    video_path: Path | None = None
    subtitle_path: Path | None = None
    music_path: Path | None = None
    subtitle_original: bool = False
    intro_outro_plan: IntroOutroPlan | None = None

    def __post_init__(self):
        input_mode = coerce_studio_input_mode(self.input_mode)
        if self.plan is not None and not isinstance(
            self.plan,
            _STUDIO_PLAN_TYPES,
        ):
            raise TypeError("plan debe ser un plan STUDIO tipado o None.")
        _validate_studio_plan_for_input_mode(input_mode, self.plan)
        _require_optional_path(self.video_path, "video_path")
        _require_optional_path(self.subtitle_path, "subtitle_path")
        _require_optional_path(self.music_path, "music_path")
        if not isinstance(self.subtitle_original, bool):
            raise TypeError("subtitle_original debe ser booleano.")
        if (
            self.intro_outro_plan is not None
            and not isinstance(self.intro_outro_plan, IntroOutroPlan)
        ):
            raise TypeError("intro_outro_plan debe ser IntroOutroPlan o None.")
        object.__setattr__(self, "input_mode", input_mode)


@dataclass(frozen=True)
class DesignExecutionRequest:
    """One already-selected DESIGN route without presentation metadata."""

    mode: str

    def __post_init__(self):
        mode = _require_non_empty_text(self.mode, "mode")
        if mode not in {"design_image", "design_video"}:
            raise ValueError("mode debe ser design_image o design_video.")
        object.__setattr__(self, "mode", mode)


ExecutionRoute: TypeAlias = (
    StandardExecutionRequest
    | StudioExecutionRequest
    | DesignExecutionRequest
)


@dataclass(frozen=True)
class ApplicationExecutionRequest:
    """Immutable application request carrying identities and a single route."""

    project_name: str
    overwrite_project: bool
    operational_profile_key: OperationalProfileKey | None
    subtitle_profile_key: SubtitleProfileKey | None
    route: ExecutionRoute

    def __post_init__(self):
        object.__setattr__(
            self,
            "project_name",
            _require_non_empty_text(self.project_name, "project_name"),
        )
        if not isinstance(self.overwrite_project, bool):
            raise TypeError("overwrite_project debe ser booleano.")
        if (
            self.operational_profile_key is not None
            and not isinstance(self.operational_profile_key, OperationalProfileKey)
        ):
            raise TypeError(
                "operational_profile_key debe ser OperationalProfileKey o None."
            )
        if (
            self.subtitle_profile_key is not None
            and not isinstance(self.subtitle_profile_key, SubtitleProfileKey)
        ):
            raise TypeError(
                "subtitle_profile_key debe ser SubtitleProfileKey o None."
            )
        if not isinstance(
            self.route,
            (
                StandardExecutionRequest,
                StudioExecutionRequest,
                DesignExecutionRequest,
            ),
        ):
            raise TypeError("route debe ser un payload de ejecución tipado.")
        _validate_route_identity(
            route=self.route,
            operational_profile_key=self.operational_profile_key,
        )


def _validate_studio_plan_for_input_mode(
    input_mode: StudioInputMode,
    plan: StudioExecutionPlan | None,
) -> None:
    expected_plan_type = {
        StudioInputMode.VIDEO_AUDIO_SRT: StudioVideoAudioSrtPlan,
        StudioInputMode.INTRO_OUTRO: StudioIntroOutroPlan,
        StudioInputMode.MONTAJE_VIDEOS: StudioMontagePlan,
        StudioInputMode.EXPORTAR_SRT: StudioSubtitleExportPlan,
    }.get(input_mode)
    if expected_plan_type is None:
        if plan is not None:
            raise ValueError("La ruta STUDIO estándar no admite un plan tipado.")
        return
    if not isinstance(plan, expected_plan_type):
        raise ValueError(
            "El plan STUDIO no corresponde al modo de entrada seleccionado."
        )


def _validate_route_identity(
    *,
    route: ExecutionRoute,
    operational_profile_key: OperationalProfileKey | None,
) -> None:
    if isinstance(route, DesignExecutionRequest):
        if operational_profile_key is None:
            raise ValueError("DESIGN requiere identidad operacional.")
        expected_component = (
            ProfileComponent.IMAGEN
            if route.mode == "design_image"
            else ProfileComponent.VIDEO
        )
        if operational_profile_key.component is not expected_component:
            raise ValueError(
                "La identidad operacional no corresponde a la ruta DESIGN."
            )
        return
    if isinstance(route, StudioExecutionRequest):
        if _studio_route_requires_identity(route) and operational_profile_key is None:
            raise ValueError("La ruta STUDIO requiere identidad operacional.")
        if (
            operational_profile_key is not None
            and operational_profile_key.component is not ProfileComponent.STUDIO
        ):
            raise ValueError("La ruta STUDIO requiere component=studio.")
        if (
            isinstance(route.plan, StudioMontagePlan)
            and operational_profile_key != route.plan.profile_key
        ):
            raise ValueError(
                "El plan de montaje y la identidad operacional no coinciden."
            )


def _studio_route_requires_identity(route: StudioExecutionRequest) -> bool:
    if route.input_mode is not StudioInputMode.EXPORTAR_SRT:
        return True
    if not isinstance(route.plan, StudioSubtitleExportPlan):
        return True
    return route.plan.mode is StudioSubtitleExportMode.CONVERTIR


def _require_non_empty_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} debe ser texto no vacío.")
    return value.strip()


def _coerce_optional_text(value: object, name: str) -> str | None:
    if value is None:
        return None
    return _require_non_empty_text(value, name)


def _coerce_technical_id(value: object, name: str) -> str | None:
    if value is None:
        return None
    technical_id = _require_non_empty_text(value, name).lower()
    if not _TECHNICAL_ID_PATTERN.fullmatch(technical_id):
        raise ValueError(f"{name} debe ser una identidad técnica opaca válida.")
    return technical_id


def _require_optional_path(value: object, name: str) -> None:
    if value is not None and not isinstance(value, Path):
        raise TypeError(f"{name} debe ser Path o None.")
