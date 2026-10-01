import json
import os
import secrets
import shutil
import time
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from app.managers.pipeline_summary import PipelineSummary
from app.managers.project_manager import ProjectManager

from app.modules.audio.audio_mixer import AudioMixer
from app.modules.audio.music_selector import MusicSelector
from app.modules.audio.voice_builder import VoiceBuilder
from app.modules.images.image_builder import ImageBuilder
from app.modules.images import (
    ImageDesignPreparationService,
    ImageDesignVisualTruthAdapter,
)
from app.modules.script import (
    ScriptOperation,
    ScriptPreparationService,
)
from app.modules.storyboard.storyboard_builder import StoryboardBuilder
from app.modules.subtitles.io.subtitle_builder import SubtitleBuilder
from app.modules.subtitles.io.external_media_subtitles import (
    ExternalMediaSubtitlePreparationService,
)
from app.modules.subtitles.modes.registry import CueModelRegistry
from app.modules.subtitles.pipeline.cue_transformer import SubtitleCueTransformer
from app.modules.subtitles.pipeline.srt_optimizer import SrtOptimizer
from app.modules.subtitles.policies.text_case import TextCasePolicy
from app.modules.video.video_builder import VideoBuilder
from app.modules.video_component import (
    VideoComponentBuilder,
    VideoDesignPreparationService,
    VideoDesignVisualTruthAdapter,
)
from app.modules.studio import (
    StudioInputPreparationService,
    StudioInputMode,
    StudioSubtitleExportMode,
    StudioSubtitleExportPlan,
    StudioSubtitleExportService,
    StudioMontagePlan,
    StudioMontageRenderResult,
    StudioMontageService,
    StudioOutputPathResolver,
    StudioPreparation,
    StudioProfileLoader,
    StudioRenderResult,
    StudioRenderService,
    StudioIntroOutroPlan,
    StudioVideoAudioSrtPlan,
    StudioVideoAudioSrtService,
)

from app.domain.adapters import StoryboardSceneAdapter
from app.shared.config_contract import (
    require_bool,
    require_int,
    require_mapping,
)
from app.shared.config_manager import ConfigManager
from app.shared.media_probe import MediaProbe
from app.shared.operation_warnings import OperationWarning, OperationWarnings
from app.shared.progress_logger import ProgressLogger
from app.shared.profile_identity import (
    ProfileComponent,
    ProfileKey,
)
from app.shared.profile_resolver import ProfileResolver
from app.shared.subtitle_profile_identity import SubtitleProfileKey


def iniciar(
    subtitle_style=None,
    subtitle_profile_key=None,
    intro_outro_selection=None,
    studio_music_path=None,
    studio_input_mode=None,
    studio_video_path=None,
    studio_subtitle_path=None,
    studio_subtitle_export_plan=None,
    studio_montage_plan=None,
    studio_intro_outro_plan=None,
    studio_video_audio_srt_plan=None,
    studio_subtitle_original=False,
):
    pipeline_start = time.perf_counter()

    pipeline_mode = os.environ.get(
        "MC_PIPELINE_MODE",
        "full"
    ).strip().lower()

    if pipeline_mode == "studio":
        if studio_video_audio_srt_plan is not None:
            video_audio_options = {}
            if subtitle_profile_key is not None:
                video_audio_options["subtitle_profile_key"] = (
                    subtitle_profile_key
                )
            elif subtitle_style is not None:
                video_audio_options["subtitle_style"] = subtitle_style
            return ejecutar_studio_video_audio_srt(
                studio_video_audio_srt_plan,
                **video_audio_options,
            )
        if studio_intro_outro_plan is not None:
            return ejecutar_studio_intro_outro(studio_intro_outro_plan)
        if studio_subtitle_export_plan is not None:
            export_options = {}
            if subtitle_profile_key is not None:
                export_options["subtitle_profile_key"] = (
                    subtitle_profile_key
                )
            elif subtitle_style is not None:
                export_options["subtitle_style"] = subtitle_style
            return ejecutar_studio_exportar_srt(
                studio_subtitle_export_plan,
                **export_options,
            )
        if studio_montage_plan is not None:
            montage_options = {}
            if studio_music_path is not None:
                montage_options["music_path"] = studio_music_path
            if intro_outro_selection is not None:
                montage_options["intro_outro_selection"] = (
                    intro_outro_selection
                )
            return ejecutar_studio_montaje(
                studio_montage_plan,
                **montage_options,
            )
        studio_options = {
            "music_path": studio_music_path,
            "input_mode": studio_input_mode,
        }
        if subtitle_profile_key is not None:
            studio_options["subtitle_profile_key"] = (
                subtitle_profile_key
            )
        elif subtitle_style is not None:
            studio_options["subtitle_style"] = subtitle_style
        if studio_subtitle_original:
            studio_options["subtitle_original"] = True
        if intro_outro_selection is not None:
            studio_options["intro_outro_selection"] = intro_outro_selection
        if studio_video_path is not None:
            studio_options["video_path"] = studio_video_path
        if studio_subtitle_path is not None:
            studio_options["subtitle_path"] = studio_subtitle_path
        return ejecutar_studio(
            **studio_options
        )

    project = ProjectManager()

    visual_pipeline = os.environ.get(
        "MC_VISUAL_PIPELINE",
        "image"
    ).strip().lower()

    if pipeline_mode == "design_image":
        return ejecutar_diseno_imagen(
            pipeline_start=pipeline_start,
            project=project
        )

    if pipeline_mode == "design_video":
        return ejecutar_diseno_video(
            pipeline_start=pipeline_start,
            project=project
        )

    config = ConfigManager()

    if pipeline_mode != "script":
        project.setup()

    ai_config = config.get_ai_config()
    profile = config.get_profile_config()

    if pipeline_mode == "video_i2v":
        return ejecutar_video_i2v(
            pipeline_start=pipeline_start,
            project=project,
            profile_key=config.get_profile_key()
        )

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
                    config,
                    subtitle_profile_key=subtitle_profile_key,
                    subtitle_style=subtitle_style,
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
        project.project_name
    )
    if not render_subtitles:
        summary.add_detail(
            "Modo",
            "Proyecto completo sin subtítulos",
        )

    stage_times = {}

    prepared_script, script_elapsed = _measure_stage(
        ejecutar_guion,
        builders=builders,
        ai_config=ai_config,
        profile=profile,
        input_script_path=input_script_path,
        input_topic_path=input_topic_path,
        output_script_path=output_script_path
    )

    stage_times["Script"] = (
        script_elapsed
    )

    final_result = (
        output_script_path
    )

    if pipeline_mode == "script":
        _complete_summary(
            summary=summary,
            stage_times=stage_times,
            project=project,
            pipeline_start=pipeline_start
        )

        return final_result

    if builders.get(
        "voice",
        False
    ):
        voice_path, voice_elapsed = _measure_stage(
            VoiceBuilder().build,
            prepared_script.text
        )

        stage_times["Voces"] = (
            voice_elapsed
        )

        final_result = voice_path

        music_category = os.environ.get(
            "MC_MUSIC_CATEGORY",
            ""
        ).strip()

        audio_start = time.perf_counter()

        if music_category:
            music_path = (
                MusicSelector().select(
                    music_category
                )
            )
        else:
            music_path = None

        final_audio_path = (
            AudioMixer().build(
                music_path=music_path
            )
        )

        stage_times["Audio"] = (
            time.perf_counter()
            - audio_start
        )

        final_result = final_audio_path

    if pipeline_mode == "audio":
        _complete_summary(
            summary=summary,
            stage_times=stage_times,
            project=project,
            pipeline_start=pipeline_start
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

        subtitle_path = (
            SubtitleBuilder().build()
        )

        optimized_subtitle_path = (
            SrtOptimizer(
                subtitle_profile=subtitle_profile,
                render_fps=_required_render_fps(
                    profile
                )
            ).optimize(
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
        _complete_summary(
            summary=summary,
            stage_times=stage_times,
            project=project,
            pipeline_start=pipeline_start
        )

        return final_result

    if builders.get(
        "storyboard",
        False
    ):
        storyboard_path, storyboard_elapsed = (
            _measure_stage(
                StoryboardBuilder().build
            )
        )

        stage_times["Storyboard"] = (
            storyboard_elapsed
        )

        final_result = storyboard_path

    if pipeline_mode == "storyboard":
        _complete_summary(
            summary=summary,
            stage_times=stage_times,
            project=project,
            pipeline_start=pipeline_start
        )

        return final_result

    if builders.get(
        "images",
        False
    ):
        images_manifest_path, images_elapsed = (
            _measure_stage(
                ImageBuilder().build
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
        profile_key = config.get_profile_key()
        if (
            isinstance(
                profile_key,
                ProfileKey
            )
            and profile_key.component is ProfileComponent.GUION
        ):
            profile_key = _resolve_single_video_operational_key(
                config.profile_resolver,
                profile_key.platform,
            )
        video_clips_manifest_path, video_i2v_elapsed = (
            _measure_stage(
                generar_video_clips_i2v,
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
            _measure_stage(
                VideoBuilder(
                    **video_builder_options
                ).build,
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
            _measure_stage(
                VideoBuilder(
                    **video_builder_options
                ).build
            )
        )

        stage_times["Vídeo"] = (
            video_elapsed
        )

        final_result = video_path

    _complete_summary(
        summary=summary,
        stage_times=stage_times,
        project=project,
        pipeline_start=pipeline_start
    )

    return final_result


def _normalise_subtitle_profile_key(
    config,
    subtitle_profile_key=None,
    subtitle_style=None,
):
    """Keep legacy strings at one input boundary and return a full key."""
    if subtitle_profile_key is not None:
        if not isinstance(subtitle_profile_key, SubtitleProfileKey):
            raise TypeError(
                "La ruta moderna requiere una SubtitleProfileKey completa."
            )
        return subtitle_profile_key
    if subtitle_style is None:
        raise ValueError("La ruta de subtitulos requiere una SubtitleProfileKey.")
    return config.adapt_legacy_subtitle_selection(subtitle_style)


def _resolve_single_video_operational_key(profile_resolver, platform):
    """Resolve the only applicable VIDEO operational identity for I2V."""
    candidates = []
    for family in profile_resolver.discover_families(
        ProfileComponent.VIDEO,
        platform,
    ):
        candidates.extend(
            descriptor[0]
            for descriptor in profile_resolver.discover(
                ProfileComponent.VIDEO,
                platform,
                family,
            )
        )
    if not candidates:
        raise FileNotFoundError(
            "No existe un perfil operacional VIDEO para la plataforma: "
            f"{platform}."
        )
    if len(candidates) > 1:
        raise ValueError(
            "La identidad operacional VIDEO es ambigua para la plataforma: "
            f"{platform}."
        )
    return candidates[0]


def preparar_studio(
    subtitle_style=None,
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
    config = config_manager or ConfigManager()
    profile_key = config.get_profile_key()
    if profile_key is None:
        raise ValueError(
            "STUDIO requiere una identidad de perfil estructurada."
        )
    if profile_key.component is not ProfileComponent.STUDIO:
        raise ValueError(
            "La ejecucion STUDIO requiere component=studio."
        )

    profile = (profile_loader or StudioProfileLoader()).load(
        config.get_profile_config(),
        profile_key,
    )
    subtitle_profile_key = _normalise_subtitle_profile_key(
        config,
        subtitle_profile_key=subtitle_profile_key,
        subtitle_style=subtitle_style,
    )
    subtitle_profile = config.get_subtitle_profile_by_key(subtitle_profile_key)
    preparation_options = {}
    if video_path is not None:
        preparation_options["video_path"] = video_path
    if subtitle_path is not None:
        preparation_options["subtitle_path"] = subtitle_path
    prepared_input = (
        input_preparation_service
        or StudioInputPreparationService()
    ).prepare(
        profile,
        input_mode,
        **preparation_options,
    )

    if prepared_input.mode is StudioInputMode.VIDEO:
        media_info = (
            media_probe
            or MediaProbe()
        ).inspect(prepared_input.video_path)
        if not media_info.has_audio:
            raise ValueError(
                "El video seleccionado no contiene una pista de audio. "
                "SOLO VIDEO necesita audio para generar los subtitulos."
            )

    return StudioPreparation(
        profile_key=profile_key,
        profile=profile,
        subtitle_profile=subtitle_profile,
        video_path=prepared_input.video_path,
        subtitle_path=prepared_input.subtitle_path,
        input_mode=prepared_input.mode.value,
        subtitle_original=bool(subtitle_original),
    )


def preparar_studio_montaje(montage_plan):
    """Validate the structured STUDIO montage boundary."""
    if not isinstance(montage_plan, StudioMontagePlan):
        raise TypeError(
            "MONTAJE DE VÍDEOS requiere un plan STUDIO estructurado."
        )
    return montage_plan


def ejecutar_studio_video_audio_srt(
    plan,
    subtitle_style=None,
    subtitle_profile_key=None,
    project=None,
    config_manager=None,
    profile_loader=None,
    output_path_resolver=None,
    service=None,
):
    if not isinstance(plan, StudioVideoAudioSrtPlan):
        raise TypeError("VIDEO + AUDIO SRT requiere un plan STUDIO estructurado.")
    if (
        plan.subtitle_path is None
        and (subtitle_style is not None or subtitle_profile_key is not None)
    ):
        raise ValueError(
            "VIDEO + AUDIO SRT sin SRT no admite estilo de subtitulos."
        )
    if (
        plan.subtitle_path is not None
        and not (subtitle_style or subtitle_profile_key)
    ):
        raise ValueError(
            "VIDEO + AUDIO SRT con SRT requiere un estilo de subtitulos."
        )
    project = project or ProjectManager()
    project.setup()
    config = config_manager or ConfigManager()
    profile_key = config.get_profile_key()
    if profile_key is None or profile_key.component is not ProfileComponent.STUDIO:
        raise ValueError("VIDEO + AUDIO SRT requiere identidad STUDIO estructurada.")
    profile = (profile_loader or StudioProfileLoader()).load(
        config.get_profile_config(),
        profile_key,
    )
    output_path = (output_path_resolver or StudioOutputPathResolver()).resolve(
        profile_key=profile_key,
        project=project,
    )
    subtitle_profile = None
    base_subtitle_path = None
    render_subtitle_path = None
    render_plan = plan
    if plan.subtitle_path is not None:
        subtitle_profile_key = _normalise_subtitle_profile_key(
            config,
            subtitle_profile_key=subtitle_profile_key,
            subtitle_style=subtitle_style,
        )
        subtitle_profile = config.get_subtitle_profile_by_key(
            subtitle_profile_key,
        )
        base_subtitle_path = _persist_studio_subtitle_base(
            plan.subtitle_path,
            output_path,
        )
        render_subtitle_path = _persist_studio_render_subtitle(
            base_subtitle_path=base_subtitle_path,
            output_path=output_path,
            subtitle_profile=subtitle_profile,
            render_fps=profile.fps,
            original=True,
        )
        render_plan = replace(plan, subtitle_path=render_subtitle_path)
    output_path, duration, command = (
        service or StudioVideoAudioSrtService()
    ).render(
        render_plan,
        output_path,
        profile,
        subtitle_profile=subtitle_profile,
    )
    return type(
        "StudioVideoAudioSrtResult",
        (),
        {
            "output_path": output_path,
            "generated_duration": duration,
            "command": command,
            "base_subtitle_path": base_subtitle_path,
            "generated_subtitle_path": render_subtitle_path,
        },
    )()

def ejecutar_studio_intro_outro(
    intro_outro_plan,
    project=None,
    config_manager=None,
    profile_loader=None,
    output_path_resolver=None,
    render_service=None,
):
    if not isinstance(intro_outro_plan, StudioIntroOutroPlan):
        raise TypeError("INTRO / OUTRO requiere un plan STUDIO estructurado.")
    project = project or ProjectManager()
    project.setup()
    config = config_manager or ConfigManager()
    profile_key = config.get_profile_key()
    if profile_key is None or profile_key.component is not ProfileComponent.STUDIO:
        raise ValueError("INTRO / OUTRO requiere identidad STUDIO estructurada.")
    profile = (profile_loader or StudioProfileLoader()).load(
        config.get_profile_config(), profile_key,
    )
    output_path = (output_path_resolver or StudioOutputPathResolver()).resolve(
        profile_key=profile_key, project=project,
    )
    return (render_service or StudioRenderService()).render(
        video_path=intro_outro_plan.source_path,
        subtitle_path=None,
        profile_key=profile_key,
        profile=profile,
        output_path=output_path,
        intro_outro_selection=intro_outro_plan.intro_outro_plan,
    )

def ejecutar_studio_exportar_srt(
    export_plan,
    subtitle_style=None,
    subtitle_profile_key=None,
    project=None,
    config_manager=None,
    profile_loader=None,
    export_service=None,
):
    if not isinstance(export_plan, StudioSubtitleExportPlan):
        raise TypeError(
            "EXPORTAR SRT requiere un plan STUDIO estructurado."
        )
    project = project or ProjectManager()
    project.setup()
    service = export_service or StudioSubtitleExportService()
    if export_plan.mode is StudioSubtitleExportMode.TRANSCRIBIR:
        if subtitle_style is not None or subtitle_profile_key is not None:
            raise ValueError("TRANSCRIBIR no admite formato de subtitulos.")
        return service.export(
            plan=export_plan,
            project=project,
        )
    if subtitle_profile_key is None and subtitle_style is None:
        raise ValueError("CONVERTIR requiere una SubtitleProfileKey.")
    config = config_manager or ConfigManager()
    profile_key = config.get_profile_key()
    if profile_key is None or profile_key.component is not ProfileComponent.STUDIO:
        raise ValueError(
            "CONVERTIR requiere una identidad STUDIO estructurada."
        )
    profile = (profile_loader or StudioProfileLoader()).load(
        config.get_profile_config(),
        profile_key,
    )
    subtitle_profile_key = _normalise_subtitle_profile_key(
        config,
        subtitle_profile_key=subtitle_profile_key,
        subtitle_style=subtitle_style,
    )
    subtitle_profile = config.get_subtitle_profile_by_key(
        subtitle_profile_key,
    )
    return service.export(
        plan=export_plan,
        project=project,
        profile=profile,
        subtitle_profile=subtitle_profile,
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
    montage_plan = preparar_studio_montaje(montage_plan)
    project = project or ProjectManager()
    project.setup()
    profile_resolver = profile_resolver or ProfileResolver()
    profile_loader = profile_loader or StudioProfileLoader()
    profile = profile_loader.load(
        profile_resolver.load(montage_plan.profile_key),
        montage_plan.profile_key,
    )
    output_path = (
        output_path_resolver
        or StudioOutputPathResolver()
    ).resolve(
        profile_key=montage_plan.profile_key,
        project=project,
    )
    montage_service = montage_service or StudioMontageService()
    with TemporaryDirectory(
        prefix="ai_visual_composer_studio_montage_"
    ) as directory:
        principal_path = Path(directory) / "montage-principal.mp4"
        montage_result = montage_service.compose(
            plan=montage_plan,
            output_path=principal_path,
            profile=profile,
        )
        preparation = StudioPreparation(
            profile_key=montage_plan.profile_key,
            profile=profile,
            subtitle_profile=None,
            video_path=montage_result.output_path,
            subtitle_path=None,
            input_mode=StudioInputMode.VIDEO.value,
            subtitles_enabled=False,
        )
        render_result = _render_prepared_studio(
            preparation=preparation,
            project=project,
            music_path=music_path,
            intro_outro_selection=intro_outro_selection,
            output_path=output_path,
            render_service=render_service,
        )
    return StudioMontageRenderResult(
        montage_result=montage_result,
        render_result=render_result,
    )


def ejecutar_studio(
    subtitle_style=None,
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
):
    if (
        subtitle_original
        and input_mode != StudioInputMode.SRT_VIDEO.value
    ):
        raise ValueError(
            "ORIGINAL solo esta disponible para STUDIO SRT + VIDEO."
        )
    preparation_options = {"input_mode": input_mode}
    if subtitle_profile_key is not None:
        preparation_options["subtitle_profile_key"] = (
            subtitle_profile_key
        )
    elif subtitle_style is not None:
        preparation_options["subtitle_style"] = subtitle_style
    if subtitle_original:
        preparation_options["subtitle_original"] = True
    if video_path is not None:
        preparation_options["video_path"] = video_path
    if subtitle_path is not None:
        preparation_options["subtitle_path"] = subtitle_path
    preparation = (
        preparation_service
        or preparar_studio
    )(**preparation_options)
    if project is None:
        project = ProjectManager()
        project.setup()
    return _render_prepared_studio(
        preparation=preparation,
        project=project,
        music_path=music_path,
        intro_outro_selection=intro_outro_selection,
        output_path=(
            output_path_resolver
            or StudioOutputPathResolver()
        ).resolve(
            profile_key=preparation.profile_key,
            project=project,
        ),
        render_service=render_service,
        external_subtitle_preparation_service=(
            external_subtitle_preparation_service
        ),
    )


def _render_prepared_studio(
    preparation,
    project,
    music_path,
    intro_outro_selection,
    output_path,
    render_service=None,
    external_subtitle_preparation_service=None,
):
    subtitles_enabled = getattr(
        preparation,
        "subtitles_enabled",
        True,
    )
    render_options = {
        "video_path": preparation.video_path,
        "profile_key": preparation.profile_key,
        "music_path": music_path,
        "profile": preparation.profile,
    }
    if subtitles_enabled:
        render_options["subtitle_profile"] = preparation.subtitle_profile
    if intro_outro_selection is not None:
        render_options["intro_outro_selection"] = intro_outro_selection
    render_options["output_path"] = output_path
    renderer = render_service or StudioRenderService()
    if not subtitles_enabled:
        return renderer.render(**render_options)
    if preparation.input_mode == StudioInputMode.SRT_VIDEO.value:
        base_subtitle_path = _persist_studio_subtitle_base(
            preparation.subtitle_path,
            output_path,
        )
        render_subtitle_path = _persist_studio_render_subtitle(
            base_subtitle_path=base_subtitle_path,
            output_path=output_path,
            subtitle_profile=preparation.subtitle_profile,
            render_fps=preparation.profile.fps,
            original=getattr(preparation, "subtitle_original", False),
        )
        render_options["subtitle_path"] = render_subtitle_path
        rendered = renderer.render(**render_options)
        return _with_studio_subtitle_artifacts(
            rendered,
            base_subtitle_path=base_subtitle_path,
            render_subtitle_path=render_subtitle_path,
        )

    with TemporaryDirectory(
        prefix="ai_visual_composer_studio_whisper_"
    ) as directory:
        ProgressLogger.start(
            "PREPARANDO SUBTÍTULOS"
        )
        subtitle_preparation_start = time.perf_counter()
        subtitles = (
            external_subtitle_preparation_service
            or ExternalMediaSubtitlePreparationService()
        ).prepare(
            video_path=preparation.video_path,
            working_directory=directory,
        )
        subtitle_preparation_duration = (
            time.perf_counter()
            - subtitle_preparation_start
        )
        ProgressLogger.finish(
            "SUBTÍTULOS PREPARADOS",
            subtitle_preparation_duration,
        )
        base_subtitle_path = _persist_studio_subtitle_base(
            subtitles.subtitle_path,
            output_path,
        )
        render_subtitle_path = _persist_studio_render_subtitle(
            base_subtitle_path=base_subtitle_path,
            output_path=output_path,
            subtitle_profile=preparation.subtitle_profile,
            render_fps=preparation.profile.fps,
            timing=subtitles.timing,
            original=getattr(preparation, "subtitle_original", False),
        )
        render_options["subtitle_path"] = render_subtitle_path
        rendered = renderer.render(**render_options)
        return _with_studio_subtitle_artifacts(
            rendered,
            base_subtitle_path=base_subtitle_path,
            render_subtitle_path=render_subtitle_path,
            subtitle_preparation_duration=subtitle_preparation_duration,
        )


def _persist_studio_subtitle_base(subtitle_path, output_path):
    output_path = Path(output_path)
    target_path = (
        output_path.parent.parent
        / "subtitles"
        / f"{output_path.stem}.srt"
    )
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(subtitle_path, target_path)
    return target_path


def _persist_studio_render_subtitle(
    base_subtitle_path,
    output_path,
    subtitle_profile,
    render_fps,
    timing=None,
    original=False,
):
    if original:
        content = Path(base_subtitle_path).read_text(encoding="utf-8")
        text_case = TextCasePolicy.from_cue_policy(
            subtitle_profile.cue_policy
        )
        rendered = text_case.apply_srt_cues(content)
        if rendered == content:
            return Path(base_subtitle_path)
        target_path = (
            Path(output_path).parent.parent
            / "subtitles"
            / f"{Path(output_path).stem}_original.srt"
        )
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = target_path.with_suffix(".srt.tmp")
        temporary_path.write_text(rendered, encoding="utf-8")
        temporary_path.replace(target_path)
        return target_path

    mode = CueModelRegistry.mode_from(subtitle_profile.cue_policy)
    output_path = Path(output_path)
    target_path = (
        output_path.parent.parent
        / "subtitles"
        / f"{output_path.stem}_{mode}.srt"
    )
    transformed = SubtitleCueTransformer(
        subtitle_profile=subtitle_profile,
        render_fps=render_fps,
    ).transform(
        Path(base_subtitle_path).read_text(encoding="utf-8"),
        timing=timing,
    )
    if not transformed.strip():
        raise ValueError("El SRT de STUDIO no produjo cues renderizables.")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = target_path.with_suffix(".srt.tmp")
    temporary_path.write_text(transformed, encoding="utf-8")
    temporary_path.replace(target_path)
    return target_path


def _with_studio_subtitle_artifacts(
    rendered,
    base_subtitle_path,
    render_subtitle_path,
    subtitle_preparation_duration=None,
):
    if not isinstance(rendered, StudioRenderResult):
        return rendered
    return replace(
        rendered,
        generated_subtitle_path=Path(render_subtitle_path),
        base_subtitle_path=Path(base_subtitle_path),
        subtitle_preparation_duration=subtitle_preparation_duration,
    )


def cargar_o_generar_guion(
    builders,
    ai_config,
    profile,
    input_script_path,
    input_topic_path,
    output_script_path,
    script_builder_factory=None
):
    return preparar_guion(
        builders=builders,
        ai_config=ai_config,
        profile=profile,
        input_script_path=input_script_path,
        input_topic_path=input_topic_path,
        output_script_path=output_script_path,
        script_builder_factory=script_builder_factory
    ).text


def ejecutar_guion(
    builders,
    ai_config,
    profile,
    input_script_path,
    input_topic_path,
    output_script_path
):
    source_mode = os.environ.get(
        "MC_SCRIPT_SOURCE",
        "generated"
    ).strip().lower()

    return ScriptOperation().execute(
        builders=builders,
        ai_config=ai_config,
        profile=profile,
        input_script_path=input_script_path,
        input_topic_path=input_topic_path,
        output_script_path=output_script_path,
        source_mode=source_mode
    )


def ejecutar_diseno_imagen(
    pipeline_start=None,
    project=None,
    input_design_path=None,
    preparation_service=None,
    visual_truth_adapter=None,
    image_builder=None
):
    if pipeline_start is None:
        pipeline_start = time.perf_counter()

    project = (
        project
        or ProjectManager()
    )

    summary = PipelineSummary(
        project.project_name
    )

    preparation_service = (
        preparation_service
        or ImageDesignPreparationService()
    )
    visual_truth_adapter = (
        visual_truth_adapter
        or ImageDesignVisualTruthAdapter()
    )
    image_builder = (
        image_builder
        or ImageBuilder()
    )

    prepared_design = preparation_service.prepare(
        input_path=(
            input_design_path
            or Path("input/guion_imagen.txt")
        )
    )

    scenes = visual_truth_adapter.adapt(
        prepared_design
    )

    _ensure_single_design_scene(
        scenes
    )

    storyboard_path = (
        project.storyboard_path()
    )
    storyboard_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )
    storyboard_path.write_text(
        json.dumps(
            scenes,
            ensure_ascii=False,
            indent=4
        ),
        encoding="utf-8"
    )

    images_manifest_path, images_elapsed = _measure_stage(
        image_builder.build,
        storyboard_path=storyboard_path,
        output_dir=project.images_dir()
    )

    _ensure_single_design_image(
        images_manifest_path
    )

    _complete_summary(
        summary=summary,
        stage_times={
            "Imágenes": images_elapsed
        },
        project=project,
        pipeline_start=pipeline_start
    )

    return images_manifest_path


def ejecutar_diseno_video(
    pipeline_start=None,
    project=None,
    input_design_path=None,
    preparation_service=None,
    visual_truth_adapter=None,
    image_builder=None,
    video_builder=None,
    profile=None,
    profile_key=None
):
    if pipeline_start is None:
        pipeline_start = time.perf_counter()

    project = (
        project
        or ProjectManager()
    )

    summary = PipelineSummary(
        project.project_name
    )

    preparation_service = (
        preparation_service
        or VideoDesignPreparationService()
    )
    visual_truth_adapter = (
        visual_truth_adapter
        or VideoDesignVisualTruthAdapter()
    )
    image_builder = (
        image_builder
        or ImageBuilder()
    )
    video_builder = (
        video_builder
        or VideoComponentBuilder()
    )
    if profile is None:
        config = ConfigManager()
        profile = config.get_profile_config()
        if profile_key is None:
            profile_key = config.get_profile_key()

    prepared_design = preparation_service.prepare(
        input_path=(
            input_design_path
            or Path("input/guion_video.txt")
        )
    )

    scenes = visual_truth_adapter.adapt(
        prepared_design
    )

    _ensure_single_video_design_scene(
        scenes
    )

    storyboard_path = (
        project.storyboard_path()
    )
    storyboard_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )
    storyboard_path.write_text(
        json.dumps(
            scenes,
            ensure_ascii=False,
            indent=4
        ),
        encoding="utf-8"
    )

    images_manifest_path, images_elapsed = _measure_stage(
        image_builder.build,
        storyboard_path=storyboard_path,
        output_dir=project.images_dir()
    )

    _ensure_single_design_image(
        images_manifest_path
    )

    video_clips_manifest_path, video_elapsed = _measure_stage(
        generar_video_clips_i2v,
        storyboard_path=storyboard_path,
        images_manifest_path=images_manifest_path,
        project=project,
        video_builder=video_builder,
        profile_key=profile_key
    )

    output_clip = _ensure_single_video_design_clip(
        video_clips_manifest_path
    )

    _complete_summary(
        summary=summary,
        stage_times={
            "Imágenes": images_elapsed,
            "Video I2V": video_elapsed
        },
        project=project,
        pipeline_start=pipeline_start
    )

    return output_clip


def ejecutar_video_i2v(
    pipeline_start=None,
    project=None,
    profile_key=None,
    source_path=None,
    video_builder=None
):
    if pipeline_start is None:
        pipeline_start = time.perf_counter()

    project = (
        project
        or ProjectManager()
    )

    project.setup()

    video_profile = _load_video_component_profile(
        profile_key
    )

    video_builder = (
        video_builder
        or VideoComponentBuilder()
    )

    output_dir = (
        project.base_path
        / "video_clips"
    )

    result, video_elapsed = _measure_stage(
        video_builder.generate_clip,
        source_path=(
            source_path
            or Path("tests/fixtures/video/source.png")
        ),
        output_dir=output_dir,
        **_video_i2v_overrides(
            video_profile
        )
    )

    summary = PipelineSummary(
        project.project_name
    )
    summary.set_media_duration(
        result.duration_seconds
    )
    summary.add_stage(
        "Video I2V",
        video_elapsed
    )
    summary.set_total_time(
        time.perf_counter()
        - pipeline_start
    )
    summary.print()

    return result.output_clip


def generar_video_clips_i2v(
    storyboard_path,
    images_manifest_path,
    project=None,
    video_builder=None,
    profile_key=None
):
    project = (
        project
        or ProjectManager()
    )

    video_profile = _load_video_component_profile(
        profile_key
    )

    video_builder = (
        video_builder
        or VideoComponentBuilder()
    )

    storyboard_path = Path(
        storyboard_path
    )
    images_manifest_path = Path(
        images_manifest_path
    )

    scenes = _load_storyboard_scenes(
        storyboard_path
    )
    image_entries = _load_image_manifest_entries(
        images_manifest_path
    )

    scenes_by_number = {
        int(
            scene.get(
                "scene"
            )
        ): scene
        for scene in scenes
    }

    output_dir = (
        project.base_path
        / "video_clips"
    )
    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    clip_entries = []

    for entry in image_entries:
        scene_number = _required_manifest_scene_number(
            entry
        )
        scene = scenes_by_number.get(
            scene_number
        )
        if scene is None:
            raise ValueError(
                "No existe una escena de storyboard "
                f"para la imagen {scene_number}."
            )

        source_image = Path(
            entry.get(
                "image",
                ""
            )
        )
        if not source_image.exists():
            raise FileNotFoundError(
                "No existe la imagen base para Video: "
                f"{source_image}"
            )

        storyboard_scene = (
            StoryboardSceneAdapter.from_visual_truth(
                scene=scene,
                default_scene_number=scene_number
            )
        )

        result = video_builder.generate_clip(
            source_path=source_image,
            output_dir=output_dir,
            output_name=f"scene_{scene_number:03d}.mp4",
            storyboard_scene=storyboard_scene,
            **_video_i2v_overrides(
                video_profile
            )
        )

        clip_entries.append(
            _build_video_clip_manifest_entry(
                result=result,
                storyboard_scene=storyboard_scene,
                image_entry=entry
            )
        )

    manifest_path = (
        output_dir
        / "video_clips_manifest.json"
    )
    manifest_path.write_text(
        json.dumps(
            clip_entries,
            ensure_ascii=False,
            indent=4
        ),
        encoding="utf-8"
    )

    return manifest_path


def _load_storyboard_scenes(
    storyboard_path
):
    data = json.loads(
        Path(
            storyboard_path
        ).read_text(
            encoding="utf-8"
        )
    )
    if not isinstance(
        data,
        list
    ):
        raise ValueError(
            "El storyboard de Video debe ser una lista de escenas."
        )
    return data


def _load_image_manifest_entries(
    images_manifest_path
):
    data = json.loads(
        Path(
            images_manifest_path
        ).read_text(
            encoding="utf-8"
        )
    )
    if not isinstance(
        data,
        list
    ):
        raise ValueError(
            "El manifiesto de imágenes debe ser una lista."
        )
    return data


def _required_manifest_scene_number(
    entry
):
    if not isinstance(
        entry,
        dict
    ):
        raise ValueError(
            "Cada entrada del manifiesto de imágenes "
            "debe ser un diccionario."
        )

    try:
        return int(
            entry[
                "scene"
            ]
        )
    except (
        KeyError,
        TypeError,
        ValueError
    ) as error:
        raise ValueError(
            "Cada imagen base de Video debe declarar scene."
        ) from error


def _load_video_component_profile(
    profile_key
):
    if not isinstance(
        profile_key,
        ProfileKey
    ):
        raise TypeError(
            "La configuracion Wan requiere un ProfileKey "
            "VIDEO explicito."
        )

    if profile_key.component is not ProfileComponent.VIDEO:
        raise ValueError(
            "La configuracion Wan requiere identidad del "
            "componente video."
        )

    return ProfileResolver().load_video_component(
        profile_key
    )


def _build_video_clip_manifest_entry(
    result,
    storyboard_scene,
    image_entry
):
    return {
        "scene": storyboard_scene.scene_number,
        "source_image": str(
            result.source_image
        ),
        "image_manifest_entry": image_entry,
        "output_clip": str(
            result.output_clip
        ),
        "positive_prompt": result.positive_prompt,
        "negative_prompt": result.negative_prompt,
        "motion_summary": result.motion_summary,
        "camera_motion": result.camera_motion,
        "motion_intensity": result.motion_intensity,
        "stability": result.stability,
        "temporal_rhythm": result.temporal_rhythm,
        "motion_level": result.motion_level,
        "preservation_constraints": list(
            result.preservation_constraints
        ),
        "avoidance_constraints": list(
            result.avoidance_constraints
        ),
        "source_trace": list(
            result.source_trace
        ),
        "profile": result.profile_name,
        "backend": result.backend,
        "model": result.model,
        "workflow": result.workflow,
        "prompt_id": result.prompt_id,
        "seed": result.seed,
        "frames": result.frames,
        "fps": result.fps,
        "generation_width": result.generation_width,
        "generation_height": result.generation_height,
        "target_width": result.target_width,
        "target_height": result.target_height,
        "steps": result.steps,
        "cfg": result.cfg,
        "sampler": result.sampler,
        "scheduler": result.scheduler,
        "duration_seconds": result.duration_seconds,
        "fingerprint": result.fingerprint,
    }


def preparar_guion(
    builders,
    ai_config,
    profile,
    input_script_path,
    input_topic_path,
    output_script_path,
    script_builder_factory=None
):
    service_kwargs = {}

    if script_builder_factory is not None:
        service_kwargs[
            "script_builder_factory"
        ] = script_builder_factory

    return ScriptPreparationService(
        **service_kwargs
    ).prepare(
        builders=builders,
        ai_config=ai_config,
        profile=profile,
        input_script_path=input_script_path,
        input_topic_path=input_topic_path,
        output_script_path=output_script_path
    )


def _video_i2v_overrides(
    profile
):
    video_component = profile.get(
        "video_component",
        {}
    )

    if not video_component:
        raise ValueError(
            "El perfil de Video debe definir video_component."
        )

    generation = video_component.get(
        "generation",
        {}
    )
    target = video_component.get(
        "target",
        {}
    )
    sampling = video_component.get(
        "sampling",
        {}
    )

    return {
        "profile_name": str(
            video_component.get(
                "profile",
                profile.get(
                    "platform",
                    ""
                )
            )
        ),
        "generation_width": _required_int(
            generation,
            "width",
            "generation.width"
        ),
        "generation_height": _required_int(
            generation,
            "height",
            "generation.height"
        ),
        "target_width": _required_int(
            target,
            "width",
            "target.width"
        ),
        "target_height": _required_int(
            target,
            "height",
            "target.height"
        ),
        "frames": _required_int(
            video_component,
            "frames",
            "frames"
        ),
        "fps": _required_float(
            video_component,
            "fps",
            "fps"
        ),
        "seed": _resolve_video_seed(
            video_component
        ),
        "steps": _required_int(
            sampling,
            "steps",
            "sampling.steps"
        ),
        "cfg": _required_float(
            sampling,
            "cfg",
            "sampling.cfg"
        ),
        "sampler": _required_text(
            sampling,
            "sampler",
            "sampling.sampler"
        ),
        "scheduler": _required_text(
            sampling,
            "scheduler",
            "sampling.scheduler"
        ),
    }


def _resolve_video_seed(
    video_component
):
    seed_mode = str(
        video_component.get(
            "seed_mode",
            ""
        )
    ).strip().lower()

    if seed_mode == "random":
        return _random_video_seed()

    if seed_mode == "fixed":
        return _required_seed(
            video_component
        )

    raise ValueError(
        "Parámetro de vídeo inválido: seed_mode."
    )


def _random_video_seed():
    return secrets.randbelow(
        2 ** 63
    )


def _required_seed(
    video_component
):
    try:
        seed = int(
            video_component[
                "seed"
            ]
        )
    except (
        KeyError,
        TypeError,
        ValueError
    ) as error:
        raise ValueError(
            "Parámetro de vídeo inválido: seed."
        ) from error

    if seed < 0:
        raise ValueError(
            "Parámetro de vídeo inválido: seed."
        )

    return seed


def _required_int(
    data,
    key,
    label
):
    try:
        value = int(
            data[key]
        )
    except (
        KeyError,
        TypeError,
        ValueError
    ) as error:
        raise ValueError(
            f"Parámetro de vídeo inválido: {label}."
        ) from error

    if value <= 0:
        raise ValueError(
            f"Parámetro de vídeo inválido: {label}."
        )

    return value


def _required_float(
    data,
    key,
    label
):
    try:
        value = float(
            data[key]
        )
    except (
        KeyError,
        TypeError,
        ValueError
    ) as error:
        raise ValueError(
            f"Parámetro de vídeo inválido: {label}."
        ) from error

    if value <= 0:
        raise ValueError(
            f"Parámetro de vídeo inválido: {label}."
        )

    return value


def _required_text(
    data,
    key,
    label
):
    value = str(
        data.get(
            key,
            ""
        )
    ).strip()

    if not value:
        raise ValueError(
            f"Parámetro de vídeo inválido: {label}."
        )

    return value


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
            "La configuracion video_style.fps debe ser "
            "superior a cero."
        )
    return fps


def _measure_stage(
    function,
    *args,
    **kwargs
):
    start = time.perf_counter()

    result = function(
        *args,
        **kwargs
    )

    elapsed = (
        time.perf_counter()
        - start
    )

    return result, elapsed


def _ensure_single_design_scene(
    scenes
):
    if not isinstance(
        scenes,
        list
    ):
        raise ValueError(
            "El diseño visual debe producir una lista "
            "de escenas."
        )

    if len(
        scenes
    ) != 1:
        raise ValueError(
            "El diseño visual debe producir exactamente "
            "una escena."
        )


def _ensure_single_design_image(
    images_manifest_path
):
    manifest_path = Path(
        images_manifest_path
    )
    manifest = json.loads(
        manifest_path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(
        manifest,
        list
    ):
        raise ValueError(
            "El manifiesto de diseño debe contener "
            "una lista de imágenes."
        )

    if len(
        manifest
    ) != 1:
        raise ValueError(
            "El diseño visual debe generar exactamente "
            "una imagen."
        )

    image_name = Path(
        str(
            manifest[0].get(
                "image",
                ""
            )
        )
    ).name

    if image_name != "scene_001.png":
        raise ValueError(
            "La imagen de diseño debe corresponder a "
            "scene_001.png."
        )


def _ensure_single_video_design_scene(
    scenes
):
    _ensure_single_design_scene(
        scenes
    )

    scene = scenes[0]
    if not isinstance(
        scene,
        dict
    ):
        raise ValueError(
            "El diseño de vídeo debe producir una escena válida."
        )

    if int(
        scene.get(
            "scene",
            0
        )
    ) != 1:
        raise ValueError(
            "El diseño de vídeo debe producir scene 1."
        )


def _ensure_single_video_design_clip(
    video_clips_manifest_path
):
    manifest_path = Path(
        video_clips_manifest_path
    )
    manifest = json.loads(
        manifest_path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(
        manifest,
        list
    ):
        raise ValueError(
            "El manifiesto de diseño de vídeo debe "
            "contener una lista de clips."
        )

    if len(
        manifest
    ) != 1:
        raise ValueError(
            "El diseño de vídeo debe generar exactamente "
            "un clip."
        )

    try:
        scene_number = int(
            manifest[0][
                "scene"
            ]
        )
    except (
        KeyError,
        TypeError,
        ValueError
    ) as error:
        raise ValueError(
            "El clip de diseño de vídeo debe declarar scene 1."
        ) from error

    if scene_number != 1:
        raise ValueError(
            "El clip de diseño de vídeo debe corresponder "
            "a scene 1."
        )

    output_clip = Path(
        str(
            manifest[0].get(
                "output_clip",
                ""
            )
        )
    )

    if output_clip.name != "scene_001.mp4":
        raise ValueError(
            "El clip de diseño de vídeo debe corresponder "
            "a scene_001.mp4."
        )

    if not output_clip.exists():
        raise FileNotFoundError(
            "No existe el clip de diseño de vídeo: "
            f"{output_clip}"
        )

    return output_clip


def _complete_summary(
    summary,
    stage_times,
    project,
    pipeline_start
):
    scene_count = _count_json_items(
        project.storyboard_path(),
        warnings=summary.warnings,
        metric_name="escenas",
    )

    image_count = _count_json_items(
        project.images_manifest_path(),
        warnings=summary.warnings,
        metric_name="im\u00e1genes",
    )

    media_duration = _resolve_media_duration(
        project,
        warnings=summary.warnings,
    )

    summary.set_scene_count(
        scene_count
    )

    summary.set_image_count(
        image_count
    )

    summary.set_media_duration(
        media_duration
    )

    stage_order = (
        "Script",
        "Storyboard",
        "Imágenes",
        "Video I2V",
        "Voces",
        "Subtítulos",
        "Audio",
        "Vídeo"
    )

    for stage_name in stage_order:
        if stage_name in stage_times:
            summary.add_stage(
                stage_name,
                stage_times[stage_name]
            )

    measured_total = (
        time.perf_counter()
        - pipeline_start
    )

    recorded_total = (
        summary.total_time()
    )

    if measured_total > recorded_total:
        summary.set_total_time(
            measured_total
        )

    summary.print()


def _count_json_items(json_path, warnings=None, metric_name=None):
    json_path = Path(
        json_path
    )

    if not json_path.exists():
        return 0

    try:
        data = json.loads(
            json_path.read_text(
                encoding="utf-8"
            )
        )

    except (
        json.JSONDecodeError,
        OSError
    ) as error:
        _record_summary_degradation(
            warnings=warnings,
            metric_name=metric_name or "elementos",
            resource=json_path,
            error=error,
        )
        return None

    if not isinstance(
        data,
        list
    ):
        _record_summary_degradation(
            warnings=warnings,
            metric_name=metric_name or "elementos",
            resource=json_path,
            error=TypeError("El manifiesto no contiene una lista."),
        )
        return None

    return len(
        data
    )


def _resolve_media_duration(project, warnings=None):
    candidate_paths = (
        project.final_audio_path(),
        project.audio_path()
    )

    for media_path in candidate_paths:
        if media_path.exists():
            try:
                return MediaProbe.get_duration(
                    media_path
                )
            except (
                OSError,
                RuntimeError,
                ValueError
            ) as error:
                _record_summary_degradation(
                    warnings=warnings,
                    metric_name="duraci\u00f3n del medio",
                    resource=media_path,
                    error=error,
                )
                return None

    return None


def _record_summary_degradation(
    warnings,
    metric_name,
    resource,
    error,
):
    """Record unavailable telemetry without changing pipeline continuity."""
    if not isinstance(warnings, OperationWarnings):
        return
    warnings.add(
        OperationWarning(
            family="DEGRADATION",
            user_message=(
                f"No se pudo obtener la m\u00e9trica de {metric_name}; "
                "se muestra como no disponible."
            ),
            recommended_action=(
                "Revisa el recurso generado si necesitas esa m\u00e9trica."
            ),
            operation="Resumen del pipeline",
            resource=str(resource),
            technical_metadata={
                "cause_type": type(error).__name__,
                "metric": str(metric_name),
                "source": "pipeline_summary",
            },
        )
    )
