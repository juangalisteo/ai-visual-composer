import json
import os
import time
from pathlib import Path

from app.core.prompt_engine import PromptEngine

from app.managers.pipeline_summary import PipelineSummary
from app.managers.project_manager import ProjectManager

from app.modules.audio.audio_mixer import AudioMixer
from app.modules.audio.music_selector import MusicSelector
from app.modules.audio.voice_builder import VoiceBuilder
from app.modules.images.image_builder import ImageBuilder
from app.modules.script.script_builder import ScriptBuilder
from app.modules.storyboard.storyboard_builder import StoryboardBuilder
from app.modules.subtitles.srt_optimizer import SrtOptimizer
from app.modules.subtitles.subtitle_builder import SubtitleBuilder
from app.modules.video.video_builder import VideoBuilder

from app.shared.config_manager import ConfigManager
from app.shared.media_probe import MediaProbe
from app.shared.progress_logger import ProgressLogger


def iniciar():
    pipeline_start = time.perf_counter()

    config = ConfigManager()
    project = ProjectManager()
    project.setup()

    pipeline_mode = os.environ.get(
        "MC_PIPELINE_MODE",
        "full"
    ).strip().lower()

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

    script, script_elapsed = _measure_stage(
        cargar_o_generar_guion,
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

    if builders.get(
        "voice",
        False
    ):
        voice_path, voice_elapsed = _measure_stage(
            VoiceBuilder().build,
            script
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
    output_script_path
):
    if builders.get(
        "script",
        True
    ):
        manual_script = (
            input_script_path.exists()
            and input_script_path.read_text(
                encoding="utf-8"
            ).strip()
        )

        if manual_script:
            ProgressLogger.info(
                "Usando guion manual."
            )

            script = str(
                manual_script
            ).strip()

        else:
            if not input_topic_path.exists():
                raise FileNotFoundError(
                    "No existe input/tema.txt."
                )

            topic = input_topic_path.read_text(
                encoding="utf-8"
            ).strip()

            if not topic:
                raise ValueError(
                    "El archivo input/tema.txt "
                    "está vacío."
                )

            prompt = (
                PromptEngine()
                .build_script_prompt(
                    topic,
                    profile
                )
            )

            script = (
                ScriptBuilder(
                    ai_config
                )
                .build(
                    prompt
                )
                .strip()
            )

        output_script_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        output_script_path.write_text(
            script,
            encoding="utf-8"
        )

        return script

    if not output_script_path.exists():
        raise FileNotFoundError(
            "ScriptBuilder está desactivado "
            "y no existe el guion esperado: "
            f"{output_script_path}"
        )

    script = output_script_path.read_text(
        encoding="utf-8"
    ).strip()

    if not script:
        raise ValueError(
            "ScriptBuilder está desactivado "
            "y el guion existente está vacío: "
            f"{output_script_path}"
        )

    ProgressLogger.info(
        "Usando guion existente."
    )

    return script


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