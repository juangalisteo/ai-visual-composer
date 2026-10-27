import time
from pathlib import Path

from app.core.pipeline_telemetry import (
    PipelineTelemetry,
    PipelineTelemetryArtifacts,
)
from app.core.execution_request import (
    ApplicationExecutionRequest,
    DesignExecutionRequest,
    StandardExecutionRequest,
    StudioExecutionRequest,
)
from app.managers.pipeline_summary import PipelineSummary
from app.managers.project_manager import ProjectManager

from app.modules.audio.audio_mixer import AudioMixer
from app.modules.audio.music_selector import MusicSelector
from app.modules.audio.voice_builder import VoiceBuilder
from app.modules.images.image_builder import ImageBuilder
from app.modules.design import DesignExecutionCoordinator
from app.modules.script import (
    ScriptOperation,
    ScriptPreparationService,
)
from app.modules.storyboard.storyboard_builder import StoryboardBuilder
from app.modules.subtitles.io.subtitle_builder import SubtitleBuilder
from app.modules.subtitles.io.external_media_subtitles import (
    ExternalMediaSubtitlePreparationService,
)
from app.modules.subtitles.pipeline.srt_optimizer import SrtOptimizer
from app.modules.video.video_builder import VideoBuilder
from app.modules.video_component.clip_batch import (
    build_public_video,
    generate_video_clips,
)
from app.modules.studio import (
    StudioInputMode,
)
from app.modules.studio.execution_coordinator import (
    StudioExecutionCoordinator,
)

from app.shared.config_contract import (
    require_bool,
    require_int,
    require_mapping,
)
from app.shared.config_manager import ConfigManager
from app.shared.media_probe import MediaProbe
from app.shared.profile_identity import (
    OperationalProfileKey,
    ProfileComponent,
)
from app.shared.subtitle_profile_identity import SubtitleProfileKey


_PIPELINE_TELEMETRY = PipelineTelemetry()
_STUDIO_EXECUTION_COORDINATOR = StudioExecutionCoordinator()
_DESIGN_EXECUTION_COORDINATOR = DesignExecutionCoordinator(
    pipeline_telemetry=_PIPELINE_TELEMETRY,
)


def iniciar(request):
    pipeline_start = time.perf_counter()

    if not isinstance(request, ApplicationExecutionRequest):
        raise TypeError(
            "request debe ser ApplicationExecutionRequest."
        )
    route = request.route
    if isinstance(route, StudioExecutionRequest):
        return _iniciar_studio_request(
            route=route,
            subtitle_profile_key=request.subtitle_profile_key,
            operational_profile_key=request.operational_profile_key,
            project_name=request.project_name,
        )

    project = ProjectManager(project_name=request.project_name)
    if isinstance(route, DesignExecutionRequest):
        design_config = _config_manager_for_operational_key(
            request.operational_profile_key
        )
        if route.mode == "design_image":
            return ejecutar_diseno_imagen(
                pipeline_start=pipeline_start,
                project=project,
                profile=design_config.get_profile_config(),
                ai_config=design_config.get_ai_config(),
            )
        return ejecutar_diseno_video(
            pipeline_start=pipeline_start,
            project=project,
            profile_key=request.operational_profile_key,
            config_manager=design_config,
        )

    if not isinstance(route, StandardExecutionRequest):
        raise TypeError("request contiene una ruta de ejecución no soportada.")
    pipeline_mode = route.pipeline_mode
    visual_pipeline = route.visual_pipeline
    script_source = route.script_source
    music_category = route.music_category
    voice_config_id = route.voice_config_id
    overlays_mode = route.overlays_mode
    intro_outro_selection = route.intro_outro_plan
    subtitle_profile_key = request.subtitle_profile_key
    operational_profile_key = request.operational_profile_key

    config = _config_manager_for_operational_key(
        operational_profile_key,
        voice_config_id=voice_config_id,
    )

    if pipeline_mode != "script":
        project.setup()

    ai_config = config.get_ai_config()
    profile = config.get_profile_config()

    builders = _required_builders(
        profile
    )
    render_subtitles = pipeline_mode != "full_without_subtitles"
    subtitle_profile = None

    if (
        render_subtitles
        and
        pipeline_mode in {
            "full",
            "subtitles",
            "storyboard",
        }
        and builders.get(
            "subtitles",
            False
        )
    ):
            subtitle_profile = config.get_subtitle_profile_by_key(
                _normalise_subtitle_profile_key(
                    subtitle_profile_key=subtitle_profile_key,
                )
            )

    input_script_path = Path(
        "input/guion.txt"
    )

    input_topic_path = Path(
        "input/tema.txt"
    )

    output_script_path = (
        project.script_path()
    )
    storyboard_path = None
    images_manifest_path = None

    summary = PipelineSummary(
        project.project_name,
        include_visual_metrics=(
            pipeline_mode in {
                "storyboard",
                "full",
                "full_without_subtitles",
            }
            and builders.get(
                "storyboard",
                False
            )
        ),
        include_media_duration=(
            pipeline_mode != "script"
            and builders.get(
                "voice",
                False
            )
        ),
    )
    telemetry_artifacts = _pipeline_telemetry_artifacts(
        project
    )
    if not render_subtitles:
        summary.add_detail(
            "Modo",
            "Proyecto completo sin subtítulos",
        )

    stage_times = {}

    script_options = {
        "builders": builders,
        "ai_config": ai_config,
        "profile": profile,
        "input_script_path": input_script_path,
        "input_topic_path": input_topic_path,
        "output_script_path": output_script_path,
        "script_source": script_source,
    }
    prepared_script, script_elapsed = _PIPELINE_TELEMETRY.measure_stage(
        ejecutar_guion,
        **script_options,
    )

    stage_times["Script"] = (
        script_elapsed
    )

    final_result = (
        output_script_path
    )

    if pipeline_mode == "script":
        _PIPELINE_TELEMETRY.complete(
            summary=summary,
            stage_times=stage_times,
            pipeline_start=pipeline_start,
            artifacts=telemetry_artifacts,
        )

        return final_result

    if builders.get(
        "voice",
        False
    ):
        if voice_config_id is None:
            raise ValueError(
                "La ruta moderna requiere voice_config_id para generar voz."
            )
        voice_builder = VoiceBuilder(config_manager=config)
        voice_path, voice_elapsed = _PIPELINE_TELEMETRY.measure_stage(
            voice_builder.build,
            prepared_script.text,
            output_path=project.audio_path(),
        )

        stage_times["Voces"] = (
            voice_elapsed
        )

        final_result = voice_path

        audio_start = time.perf_counter()

        if music_category:
            music_path = (
                MusicSelector().select(
                    music_category
                )
            )
        else:
            music_path = None

        final_audio_path = AudioMixer().build(
            voice_path=voice_path,
            music_path=music_path,
            output_path=project.final_audio_path(),
            project=project,
        )

        stage_times["Audio"] = (
            time.perf_counter()
            - audio_start
        )

        final_result = final_audio_path

    if pipeline_mode == "audio":
        _PIPELINE_TELEMETRY.complete(
            summary=summary,
            stage_times=stage_times,
            pipeline_start=pipeline_start,
            artifacts=telemetry_artifacts,
        )

        return final_result

    if (
        render_subtitles
        and builders.get(
        "subtitles",
        False
        )
    ):
        subtitles_start = (
            time.perf_counter()
        )

        subtitle_path = SubtitleBuilder().build(
            audio_path=project.audio_path(),
            output_path=project.subtitle_path(),
        )

        optimizer_options = {
            "subtitle_profile": subtitle_profile,
            "render_fps": _required_render_fps(profile),
            "project": project,
        }
        optimized_subtitle_path = (
            SrtOptimizer(**optimizer_options).optimize(
                canonical_content=prepared_script.text,
            )
        )

        stage_times["Subtítulos"] = (
            time.perf_counter()
            - subtitles_start
        )

        final_result = (
            optimized_subtitle_path
            or subtitle_path
        )

    if pipeline_mode == "subtitles":
        _PIPELINE_TELEMETRY.complete(
            summary=summary,
            stage_times=stage_times,
            pipeline_start=pipeline_start,
            artifacts=telemetry_artifacts,
        )

        return final_result

    if builders.get(
        "storyboard",
        False
    ):
        storyboard_builder = StoryboardBuilder(
            config_manager=config,
            project=project,
        )
        storyboard_path, storyboard_elapsed = (
            _PIPELINE_TELEMETRY.measure_stage(
                storyboard_builder.build
            )
        )

        stage_times["Storyboard"] = (
            storyboard_elapsed
        )

        final_result = storyboard_path

    if pipeline_mode == "storyboard":
        _PIPELINE_TELEMETRY.complete(
            summary=summary,
            stage_times=stage_times,
            pipeline_start=pipeline_start,
            artifacts=telemetry_artifacts,
        )

        return final_result

    if builders.get(
        "images",
        False
    ):
        image_builder = ImageBuilder(
            profile=profile,
            project=project,
        )
        images_manifest_path, images_elapsed = (
            _PIPELINE_TELEMETRY.measure_stage(
                image_builder.build
            )
        )

        stage_times["Imágenes"] = (
            images_elapsed
        )

        final_result = (
            images_manifest_path
        )

    video_builder_options = {
        "subtitle_profile": subtitle_profile,
        "warnings": summary.warnings,
        "overlays_mode": overlays_mode,
    }
    if not render_subtitles:
        video_builder_options["render_subtitles"] = False
    if intro_outro_selection is not None:
        video_builder_options[
            "intro_outro_selection"
        ] = intro_outro_selection

    if (
        visual_pipeline == "video"
        and pipeline_mode in {
            "full",
            "full_without_subtitles",
        }
    ):
        profile_key = operational_profile_key
        if (
            isinstance(
                profile_key,
                OperationalProfileKey
            )
            and profile_key.component is ProfileComponent.GUION
        ):
            profile_key = _resolve_single_video_operational_key(
                config.profile_resolver,
                profile_key.format,
            )
        video_clips_manifest_path, video_i2v_elapsed = (
            _PIPELINE_TELEMETRY.measure_stage(
                generate_video_clips,
                storyboard_path=(
                    storyboard_path
                    or project.storyboard_path()
                ),
                images_manifest_path=(
                    images_manifest_path
                    or project.images_manifest_path()
                ),
                project=project,
                profile_key=profile_key
            )
        )

        stage_times["Video I2V"] = (
            video_i2v_elapsed
        )

        final_result = (
            video_clips_manifest_path
        )

        video_path, video_elapsed = (
            _PIPELINE_TELEMETRY.measure_stage(
                build_public_video,
                video_builder=VideoBuilder(
                    **video_builder_options,
                    config_manager=config,
                    project=project,
                ),
                video_clips_manifest_path=(
                    video_clips_manifest_path
                )
            )
        )

        stage_times["Vídeo"] = (
            video_elapsed
        )

        final_result = video_path

    if (
        visual_pipeline != "video"
        and builders.get(
            "video",
            False
        )
    ):
        video_path, video_elapsed = (
            _PIPELINE_TELEMETRY.measure_stage(
                VideoBuilder(
                    **video_builder_options,
                    config_manager=config,
                    project=project,
                ).build
            )
        )

        stage_times["Vídeo"] = (
            video_elapsed
        )

        final_result = video_path

    _PIPELINE_TELEMETRY.complete(
        summary=summary,
        stage_times=stage_times,
        pipeline_start=pipeline_start,
        artifacts=telemetry_artifacts,
    )

    return final_result


def _iniciar_studio_request(
    *,
    route,
    subtitle_profile_key,
    operational_profile_key,
    project_name,
):
    """Dispatch a typed STUDIO route without reconstructing its plan."""
    config_manager = _config_manager_for_operational_key(
        operational_profile_key
    )
    project = ProjectManager(project_name=project_name)
    if route.input_mode is StudioInputMode.VIDEO_AUDIO_SRT:
        video_audio_options = _typed_subtitle_options(
            subtitle_profile_key,
        )
        return ejecutar_studio_video_audio_srt(
            route.plan,
            config_manager=config_manager,
            project=project,
            **video_audio_options,
        )
    if route.input_mode is StudioInputMode.INTRO_OUTRO:
        return ejecutar_studio_intro_outro(
            route.plan,
            config_manager=config_manager,
            project=project,
        )
    if route.input_mode is StudioInputMode.EXPORTAR_SRT:
        export_options = _typed_subtitle_options(
            subtitle_profile_key,
        )
        return ejecutar_studio_exportar_srt(
            route.plan,
            config_manager=config_manager,
            project=project,
            **export_options,
        )
    if route.input_mode is StudioInputMode.MONTAJE_VIDEOS:
        montage_options = {}
        if route.music_path is not None:
            montage_options["music_path"] = route.music_path
        if route.intro_outro_plan is not None:
            montage_options["intro_outro_selection"] = route.intro_outro_plan
        montage_options["project"] = project
        return ejecutar_studio_montaje(route.plan, **montage_options)

    studio_options = {
        "music_path": route.music_path,
        "input_mode": route.input_mode.value,
    }
    studio_options.update(
        _typed_subtitle_options(
            subtitle_profile_key,
        )
    )
    if route.subtitle_original:
        studio_options["subtitle_original"] = True
    if route.intro_outro_plan is not None:
        studio_options["intro_outro_selection"] = route.intro_outro_plan
    if route.video_path is not None:
        studio_options["video_path"] = route.video_path
    if route.subtitle_path is not None:
        studio_options["subtitle_path"] = route.subtitle_path
    studio_options["config_manager"] = config_manager
    project.setup()
    studio_options["project"] = project
    return ejecutar_studio(**studio_options)


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


def _typed_subtitle_options(subtitle_profile_key):
    if subtitle_profile_key is not None:
        return {"subtitle_profile_key": subtitle_profile_key}
    return {}


def _normalise_subtitle_profile_key(
    subtitle_profile_key=None,
):
    """Validate and return the full subtitle identity."""
    if subtitle_profile_key is None:
        raise ValueError("La ruta de subtítulos requiere una SubtitleProfileKey.")
    if not isinstance(subtitle_profile_key, SubtitleProfileKey):
        raise TypeError(
            "La ruta moderna requiere una SubtitleProfileKey completa."
        )
    return subtitle_profile_key


def _resolve_single_video_operational_key(profile_resolver, profile_format):
    """Resolve the only applicable VIDEO operational identity for I2V."""
    candidates = []
    candidates.extend(
        descriptor.key
        for descriptor in profile_resolver.discover_operational_profiles(
            ProfileComponent.VIDEO,
            profile_format,
        )
    )
    if not candidates:
        raise FileNotFoundError(
            "No existe un perfil operacional VIDEO para el formato: "
            f"{profile_format}."
        )
    if len(candidates) > 1:
        raise ValueError(
            "La identidad operacional VIDEO es ambigua para el formato: "
            f"{profile_format}."
        )
    return candidates[0]


def preparar_studio(
    input_mode=None,
    subtitle_profile_key=None,
    config_manager=None,
    profile_loader=None,
    input_preparation_service=None,
    media_probe=None,
    video_path=None,
    subtitle_path=None,
    subtitle_original=False,
):
    """Validate and transport Studio inputs without creating a project."""
    return _STUDIO_EXECUTION_COORDINATOR.prepare_standard(
        input_mode=input_mode,
        subtitle_profile_key=subtitle_profile_key,
        config_manager=config_manager,
        profile_loader=profile_loader,
        input_preparation_service=input_preparation_service,
        media_probe=media_probe,
        video_path=video_path,
        subtitle_path=subtitle_path,
        subtitle_original=subtitle_original,
        subtitle_profile_key_normalizer=_normalise_subtitle_profile_key,
    )


def ejecutar_studio_video_audio_srt(
    plan,
    subtitle_profile_key=None,
    project=None,
    config_manager=None,
    profile_loader=None,
    output_path_resolver=None,
    service=None,
):
    return _STUDIO_EXECUTION_COORDINATOR.run_video_audio_srt(
        plan=plan,
        subtitle_profile_key=subtitle_profile_key,
        project=project,
        config_manager=config_manager,
        profile_loader=profile_loader,
        output_path_resolver=output_path_resolver,
        service=service,
        subtitle_profile_key_normalizer=_normalise_subtitle_profile_key,
        persist_subtitle_base=_persist_studio_subtitle_base,
        persist_render_subtitle=_persist_studio_render_subtitle,
    )

def ejecutar_studio_intro_outro(
    intro_outro_plan,
    project=None,
    config_manager=None,
    profile_loader=None,
    output_path_resolver=None,
    render_service=None,
):
    return _STUDIO_EXECUTION_COORDINATOR.run_intro_outro(
        intro_outro_plan=intro_outro_plan,
        project=project,
        config_manager=config_manager,
        profile_loader=profile_loader,
        output_path_resolver=output_path_resolver,
        render_service=render_service,
    )

def ejecutar_studio_exportar_srt(
    export_plan,
    subtitle_profile_key=None,
    project=None,
    config_manager=None,
    profile_loader=None,
    export_service=None,
):
    return _STUDIO_EXECUTION_COORDINATOR.run_subtitle_export(
        export_plan=export_plan,
        subtitle_profile_key=subtitle_profile_key,
        project=project,
        config_manager=config_manager,
        profile_loader=profile_loader,
        export_service=export_service,
        subtitle_profile_key_normalizer=_normalise_subtitle_profile_key,
    )


def ejecutar_studio_montaje(
    montage_plan,
    music_path=None,
    intro_outro_selection=None,
    project=None,
    profile_resolver=None,
    profile_loader=None,
    output_path_resolver=None,
    montage_service=None,
    render_service=None,
):
    return _STUDIO_EXECUTION_COORDINATOR.run_montage(
        montage_plan=montage_plan,
        music_path=music_path,
        intro_outro_selection=intro_outro_selection,
        project=project,
        profile_resolver=profile_resolver,
        profile_loader=profile_loader,
        output_path_resolver=output_path_resolver,
        montage_service=montage_service,
        render_service=render_service,
    )


def ejecutar_studio(
    input_mode=None,
    subtitle_profile_key=None,
    music_path=None,
    intro_outro_selection=None,
    preparation_service=None,
    render_service=None,
    output_path_resolver=None,
    external_subtitle_preparation_service=None,
    project=None,
    video_path=None,
    subtitle_path=None,
    subtitle_original=False,
    config_manager=None,
):
    if preparation_service is None and config_manager is not None:
        def preparation_service(**options):
            return preparar_studio(
                config_manager=config_manager,
                **options,
            )

    return _STUDIO_EXECUTION_COORDINATOR.run_standard(
        input_mode=input_mode,
        subtitle_profile_key=subtitle_profile_key,
        music_path=music_path,
        intro_outro_selection=intro_outro_selection,
        preparation_service=(
            preparation_service
            or preparar_studio
        ),
        render_service=render_service,
        output_path_resolver=output_path_resolver,
        external_subtitle_preparation_service=external_subtitle_preparation_service,
        project=project,
        video_path=video_path,
        subtitle_path=subtitle_path,
        subtitle_original=subtitle_original,
        config_manager=config_manager,
        subtitle_profile_key_normalizer=_normalise_subtitle_profile_key,
        persist_subtitle_base=_persist_studio_subtitle_base,
        persist_render_subtitle=_persist_studio_render_subtitle,
        with_subtitle_artifacts=_with_studio_subtitle_artifacts,
    )


def _persist_studio_subtitle_base(subtitle_path, output_path):
    return _STUDIO_EXECUTION_COORDINATOR.persist_subtitle_base(
        subtitle_path,
        output_path,
    )


def _persist_studio_render_subtitle(
    base_subtitle_path,
    output_path,
    subtitle_profile,
    render_fps,
    timing=None,
    original=False,
):
    return _STUDIO_EXECUTION_COORDINATOR.persist_render_subtitle(
        base_subtitle_path=base_subtitle_path,
        output_path=output_path,
        subtitle_profile=subtitle_profile,
        render_fps=render_fps,
        timing=timing,
        original=original,
    )


def _with_studio_subtitle_artifacts(
    rendered,
    base_subtitle_path,
    render_subtitle_path,
    subtitle_preparation_duration=None,
):
    return _STUDIO_EXECUTION_COORDINATOR.with_subtitle_artifacts(
        rendered,
        base_subtitle_path=base_subtitle_path,
        render_subtitle_path=render_subtitle_path,
        subtitle_preparation_duration=subtitle_preparation_duration,
    )


def ejecutar_guion(
    builders,
    ai_config,
    profile,
    input_script_path,
    input_topic_path,
    output_script_path,
    script_source,
):
    return ScriptOperation().execute(
        builders=builders,
        ai_config=ai_config,
        profile=profile,
        input_script_path=input_script_path,
        input_topic_path=input_topic_path,
        output_script_path=output_script_path,
        source_mode=script_source
    )


def ejecutar_diseno_imagen(
    pipeline_start=None,
    project=None,
    input_design_path=None,
    preparation_service=None,
    visual_truth_adapter=None,
    image_builder=None,
    profile=None,
    ai_config=None,
):
    return _DESIGN_EXECUTION_COORDINATOR.run_image(
        pipeline_start=pipeline_start,
        project=project,
        input_design_path=input_design_path,
        preparation_service=preparation_service,
        visual_truth_adapter=visual_truth_adapter,
        image_builder=image_builder,
        profile=profile,
        ai_config=ai_config,
    )


def ejecutar_diseno_video(
    pipeline_start=None,
    project=None,
    input_design_path=None,
    preparation_service=None,
    visual_truth_adapter=None,
    image_builder=None,
    video_builder=None,
    profile=None,
    profile_key=None,
    config_manager=None,
    ai_config=None,
):
    return _DESIGN_EXECUTION_COORDINATOR.run_video(
        pipeline_start=pipeline_start,
        project=project,
        input_design_path=input_design_path,
        preparation_service=preparation_service,
        visual_truth_adapter=visual_truth_adapter,
        image_builder=image_builder,
        video_builder=video_builder,
        profile=profile,
        profile_key=profile_key,
        config_manager=config_manager,
        ai_config=ai_config,
    )


def _required_builders(profile):
    builders = require_mapping(
        profile,
        "builders",
        "builders"
    )
    required_names = (
        "script",
        "voice",
        "subtitles",
        "storyboard",
        "images",
        "video",
    )
    return {
        name: require_bool(
            builders,
            name,
            f"builders.{name}"
        )
        for name in required_names
    }


def _required_render_fps(profile):
    video_style = require_mapping(
        profile,
        "video_style",
        "video_style"
    )
    fps = require_int(
        video_style,
        "fps",
        "video_style.fps"
    )
    if fps <= 0:
        raise ValueError(
            "La configuración video_style.fps debe ser "
            "superior a cero."
        )
    return fps


def _pipeline_telemetry_artifacts(
    project,
):
    return PipelineTelemetryArtifacts(
        storyboard_path=project.storyboard_path(),
        images_manifest_path=project.images_manifest_path(),
        final_audio_path=project.final_audio_path(),
        audio_path=project.audio_path(),
    )
