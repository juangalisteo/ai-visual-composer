"""Pure typed transport contracts for application execution decisions.

This module deliberately has no runtime integration yet.  It adapts the
current controller dictionary without reading or writing process environment,
loading configuration, or invoking pipelines.
"""

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Mapping, TypeAlias

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
        object.__setattr__(
            self,
            "pipeline_mode",
            _require_non_empty_text(self.pipeline_mode, "pipeline_mode"),
        )
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
    clear_output: bool
    operational_profile_key: OperationalProfileKey | None
    subtitle_profile_key: SubtitleProfileKey | None
    route: ExecutionRoute

    def __post_init__(self):
        object.__setattr__(
            self,
            "project_name",
            _require_non_empty_text(self.project_name, "project_name"),
        )
        if not isinstance(self.clear_output, bool):
            raise TypeError("clear_output debe ser booleano.")
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


def adapt_legacy_run_options(
    options: Mapping[str, object],
) -> ApplicationExecutionRequest:
    """Adapt the current controller mapping without consulting runtime state."""
    if not isinstance(options, Mapping):
        raise TypeError("options debe ser un mapping de opciones de ejecución.")

    pipeline_mode = _require_non_empty_text(
        options.get("pipeline_mode"),
        "pipeline_mode",
    )
    operational_profile_key = _adapt_operational_profile_key(options)
    subtitle_profile_key = _require_subtitle_profile_key(
        options.get("subtitle_profile_key"),
    )
    route = _adapt_route(
        options=options,
        pipeline_mode=pipeline_mode,
    )
    return ApplicationExecutionRequest(
        project_name=_require_non_empty_text(
            options.get("project_name"),
            "project_name",
        ),
        clear_output=_require_bool(options.get("clear_output"), "clear_output"),
        operational_profile_key=operational_profile_key,
        subtitle_profile_key=subtitle_profile_key,
        route=route,
    )


def _adapt_route(
    *,
    options: Mapping[str, object],
    pipeline_mode: str,
) -> ExecutionRoute:
    if pipeline_mode == "studio":
        return StudioExecutionRequest(
            input_mode=options.get("studio_input_mode"),
            plan=_adapt_studio_plan(options),
            video_path=_adapt_optional_path(options.get("studio_video_path")),
            subtitle_path=_adapt_optional_path(
                options.get("studio_subtitle_path"),
            ),
            music_path=_adapt_optional_path(options.get("studio_music_path")),
            subtitle_original=_coerce_bool_default(
                options.get("studio_subtitle_original"),
                default=False,
                name="studio_subtitle_original",
            ),
            intro_outro_plan=_require_intro_outro_plan(
                options.get("intro_outro_selection"),
            ),
        )
    if pipeline_mode in {"design_image", "design_video"}:
        return DesignExecutionRequest(mode=pipeline_mode)
    return StandardExecutionRequest(
        pipeline_mode=pipeline_mode,
        visual_pipeline=options.get("visual_pipeline"),
        script_source=options.get("script_source"),
        voice_config_id=_blank_to_none(options.get("voice_config")),
        music_category=_blank_to_none(options.get("music_category")),
        overlays_mode=_blank_to_none(options.get("overlays_mode")),
        intro_outro_plan=_require_intro_outro_plan(
            options.get("intro_outro_selection"),
        ),
    )


def _adapt_operational_profile_key(
    options: Mapping[str, object],
) -> OperationalProfileKey | None:
    existing_key = options.get("operational_profile_key")
    if existing_key is not None:
        if not isinstance(existing_key, OperationalProfileKey):
            raise TypeError(
                "operational_profile_key debe ser OperationalProfileKey."
            )
        return existing_key

    values = tuple(
        _blank_to_none(options.get(name))
        for name in (
            "profile_component",
            "profile_platform",
            "profile_id",
        )
    )
    if not any(values):
        return None
    if not all(values):
        raise ValueError("La identidad operacional legacy está incompleta.")
    return OperationalProfileKey(*values)


def _adapt_studio_plan(options: Mapping[str, object]) -> StudioExecutionPlan | None:
    plans = tuple(
        value
        for value in (
            options.get("studio_video_audio_srt_plan"),
            options.get("studio_intro_outro_plan"),
            options.get("studio_montage_plan"),
            options.get("studio_subtitle_export_plan"),
        )
        if value is not None
    )
    if len(plans) > 1:
        raise ValueError("Una ruta STUDIO no puede transportar varios planes.")
    return plans[0] if plans else None


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
    if isinstance(route, StandardExecutionRequest):
        if route.pipeline_mode in {"studio", "design_image", "design_video"}:
            raise ValueError(
                "La ruta estándar no admite modos STUDIO ni DESIGN."
            )
        return
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


def _require_bool(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{name} debe ser booleano.")
    return value


def _coerce_bool_default(value: object, *, default: bool, name: str) -> bool:
    if value is None:
        return default
    return _require_bool(value, name)


def _require_subtitle_profile_key(value: object) -> SubtitleProfileKey | None:
    if value is None:
        return None
    if not isinstance(value, SubtitleProfileKey):
        raise TypeError("subtitle_profile_key debe ser SubtitleProfileKey o None.")
    return value


def _require_intro_outro_plan(value: object) -> IntroOutroPlan | None:
    if value is None:
        return None
    if not isinstance(value, IntroOutroPlan):
        raise TypeError("intro_outro_selection debe ser IntroOutroPlan o None.")
    return value


def _require_optional_path(value: object, name: str) -> None:
    if value is not None and not isinstance(value, Path):
        raise TypeError(f"{name} debe ser Path o None.")


def _adapt_optional_path(value: object) -> Path | None:
    if value is None or value == "":
        return None
    if isinstance(value, Path):
        return value
    if isinstance(value, str):
        return Path(value)
    raise TypeError("Las rutas legacy deben ser texto, Path o None.")


def _blank_to_none(value: object) -> object | None:
    if isinstance(value, str) and not value.strip():
        return None
    return value
