"""Coordination for the standard GUION, IMAGEN and VIDEO execution route."""

import time
from pathlib import Path

from app.core.pipeline_telemetry import (
    PipelineTelemetry,
    PipelineTelemetryArtifacts,
)
from app.managers.pipeline_summary import PipelineSummary
from app.modules.audio.audio_mixer import AudioMixer
from app.modules.audio.music_selector import MusicSelector
from app.modules.audio.voice_builder import VoiceBuilder
from app.modules.images.image_builder import ImageBuilder
from app.modules.script import (
    ScriptOperation,
)
from app.modules.storyboard.storyboard_builder import StoryboardBuilder
from app.modules.subtitles.io.subtitle_builder import SubtitleBuilder
from app.modules.subtitles.pipeline.srt_optimizer import SrtOptimizer
from app.modules.video.video_builder import VideoBuilder
from app.modules.video_component.clip_batch import (
    build_public_video,
    generate_video_clips,
)
from app.shared.config_contract import (
    require_bool,
    require_int,
    require_mapping,
)
from app.shared.profile_identity import (
    OperationalProfileKey,
    ProfileComponent,
)
from app.shared.subtitle_profile_identity import require_subtitle_profile_key


class StandardExecutionCoordinator:
    """Coordinate the standard route through existing capabilities."""

    def __init__(
        self,
        pipeline_telemetry=None,
    ):
        self._pipeline_telemetry = (
            pipeline_telemetry
            or PipelineTelemetry()
        )

    def run(
        self,
        route,
        subtitle_profile_key,
        operational_profile_key,
        config_manager,
        project,
        pipeline_start,
    ):
        """Run one typed standard route in its established stage order."""
        pipeline_mode = route.pipeline_mode
        visual_pipeline = route.visual_pipeline
        script_source = route.script_source
        music_category = route.music_category
        voice_config_id = route.voice_config_id
        overlays_mode = route.overlays_mode
        intro_outro_selection = route.intro_outro_plan

        if pipeline_mode != "script":
            project.setup()

        ai_config = config_manager.get_ai_config()
        profile = config_manager.get_profile_config()

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
                subtitle_profile = config_manager.get_subtitle_profile_by_key(
                    require_subtitle_profile_key(
                        subtitle_profile_key
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
            "source_mode": script_source,
        }
        prepared_script, script_elapsed = self._pipeline_telemetry.measure_stage(
            ScriptOperation().execute,
            **script_options,
        )

        stage_times["Script"] = (
            script_elapsed
        )

        final_result = (
            output_script_path
        )

        if pipeline_mode == "script":
            self._pipeline_telemetry.complete(
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
            voice_builder = VoiceBuilder(config_manager=config_manager)
            voice_path, voice_elapsed = self._pipeline_telemetry.measure_stage(
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
            self._pipeline_telemetry.complete(
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
            self._pipeline_telemetry.complete(
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
                config_manager=config_manager,
                project=project,
            )
            storyboard_path, storyboard_elapsed = (
                self._pipeline_telemetry.measure_stage(
                    storyboard_builder.build
                )
            )

            stage_times["Storyboard"] = (
                storyboard_elapsed
            )

            final_result = storyboard_path

        if pipeline_mode == "storyboard":
            self._pipeline_telemetry.complete(
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
                self._pipeline_telemetry.measure_stage(
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
                    config_manager.profile_resolver,
                    profile_key.format,
                )
            video_clips_manifest_path, video_i2v_elapsed = (
                self._pipeline_telemetry.measure_stage(
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
                self._pipeline_telemetry.measure_stage(
                    build_public_video,
                    video_builder=VideoBuilder(
                        **video_builder_options,
                        config_manager=config_manager,
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
                self._pipeline_telemetry.measure_stage(
                    VideoBuilder(
                        **video_builder_options,
                        config_manager=config_manager,
                        project=project,
                    ).build
                )
            )

            stage_times["Vídeo"] = (
                video_elapsed
            )

            final_result = video_path

        self._pipeline_telemetry.complete(
            summary=summary,
            stage_times=stage_times,
            pipeline_start=pipeline_start,
            artifacts=telemetry_artifacts,
        )

        return final_result


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
