import json
import os
import time
from pathlib import Path

from app.managers.pipeline_summary import PipelineSummary
from app.managers.project_manager import ProjectManager

from app.modules.audio.audio_mixer import AudioMixer
from app.modules.audio.music_selector import MusicSelector
from app.modules.audio.voice_builder import VoiceBuilder
from app.modules.images.image_builder import ImageBuilder
from app.modules.script import (
    ScriptOperation,
    ScriptPreparationService,
)
from app.modules.storyboard.storyboard_builder import StoryboardBuilder
from app.modules.subtitles.srt_optimizer import SrtOptimizer
from app.modules.subtitles.subtitle_builder import SubtitleBuilder
from app.modules.video.video_builder import VideoBuilder

from app.shared.config_manager import ConfigManager
from app.shared.media_probe import MediaProbe


def iniciar():
    pipeline_start = time.perf_counter()

    config = ConfigManager()
    project = ProjectManager()

    pipeline_mode = os.environ.get(
        "MC_PIPELINE_MODE",
        "full"
    ).strip().lower()

    if pipeline_mode != "script":
        project.setup()

    ai_config = config.get_ai_config()
    profile = config.get_profile_config()

    builders = profile.get(
        "builders",
        {}
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

    summary = PipelineSummary(
        project.project_name
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

    if builders.get(
        "subtitles",
        False
    ):
        subtitles_start = (
            time.perf_counter()
        )

        subtitle_path = (
            SubtitleBuilder().build()
        )

        optimized_subtitle_path = (
            SrtOptimizer().optimize()
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

    if builders.get(
        "video",
        False
    ):
        video_path, video_elapsed = (
            _measure_stage(
                VideoBuilder().build
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


def _complete_summary(
    summary,
    stage_times,
    project,
    pipeline_start
):
    scene_count = _count_json_items(
        project.storyboard_path()
    )

    image_count = _count_json_items(
        project.images_manifest_path()
    )

    media_duration = _resolve_media_duration(
        project
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


def _count_json_items(
    json_path
):
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
    ):
        return 0

    if not isinstance(
        data,
        list
    ):
        return 0

    return len(
        data
    )


def _resolve_media_duration(
    project
):
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
            ):
                return None

    return None
