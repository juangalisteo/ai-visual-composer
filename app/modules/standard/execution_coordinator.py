"""Coordination for the standard GUION, IMAGEN and VIDEO execution route."""

import time
from pathlib import Path

from app.core.pipeline_telemetry import (
    PipelineTelemetry,
    PipelineTelemetryArtifacts,
)
from app.core.script_length import script_duration_margin
from app.managers.pipeline_summary import PipelineSummary
from app.modules.audio.audio_mixer import AudioMixer
from app.modules.audio.music_selector import MusicSelector
from app.modules.audio.tts_contracts import TtsVoiceConfigurationError
from app.modules.audio.voice_builder import VoiceBuilder
from app.modules.images.image_builder import ImageBuilder
from app.modules.script import (
    ScriptAdjustment,
    ScriptOperation,
)
from app.modules.standard.script_duration_fit import ScriptDurationFit
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
from app.shared.media_probe import MediaProbe
from app.shared.operational_error import (
    create_missing_asset_error,
    create_operational_error,
)
from app.shared.profile_identity import (
    OperationalProfileKey,
    ProfileComponent,
)
from app.shared.subtitle_profile_identity import require_subtitle_profile_key


# Stages of the standard route, in execution order.
_STAGES = (
    "script",
    "voice_and_audio",
    "subtitles",
    "storyboard",
    "images",
    "video",
)

# Last stage each pipeline mode runs; the stages after it are not attempted.
_LAST_STAGE_BY_PIPELINE_MODE = {
    "audio": "voice_and_audio",
    "subtitles": "subtitles",
    "storyboard": "storyboard",
    "full": "video",
    "full_without_subtitles": "video",
}


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
        """Run one typed standard route up to the last stage of its mode."""
        pipeline_mode = route.pipeline_mode
        visual_pipeline = route.visual_pipeline
        script_source = route.script_source
        music_category = route.music_category
        voice_config_id = route.voice_config_id
        overlays_mode = route.overlays_mode
        intro_outro_selection = route.intro_outro_plan
        stages = _stages_for(
            pipeline_mode
        )

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
            include_media_duration=builders.get(
                "voice",
                False
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

        voice_pacing = (
            _generated_script_pacing(config_manager)
            if script_source == "generated" and builders["script"]
            else None
        )
        script_options = {
            "builders": builders,
            "ai_config": ai_config,
            "profile": profile,
            "input_script_path": input_script_path,
            "input_topic_path": input_topic_path,
            "output_script_path": output_script_path,
            "source_mode": script_source,
            "voice_pacing": voice_pacing,
        }
        prepared_script, script_elapsed = self._pipeline_telemetry.measure_stage(
            ScriptOperation().execute,
            **script_options,
        )

        stage_times["Script"] = (
            script_elapsed
        )
        script_text = prepared_script.text

        final_result = (
            output_script_path
        )
        voice_pauses = ()
        whisper_subtitle_path = None

        if (
            "voice_and_audio" in stages
            and builders.get(
                "voice",
                False
            )
        ):
            if voice_config_id is None:
                raise ValueError(
                    "Generar la voz requiere voice_config_id."
                )
            voice_builder = VoiceBuilder(config_manager=config_manager)
            voice_path, voice_elapsed = self._pipeline_telemetry.measure_stage(
                voice_builder.build,
                script_text,
                output_path=project.audio_path(),
            )

            stage_times["Voces"] = (
                voice_elapsed
            )
            voice_pauses = _voice_pauses(
                voice_builder
            )

            if voice_pacing is not None:
                fit = self._fit_script_duration(
                    voice_builder=voice_builder,
                    script_options=script_options,
                    script_text=script_text,
                    target_seconds=require_int(
                        profile,
                        "duration",
                        "duration"
                    ),
                    voice_path=voice_path,
                    voice_pauses=voice_pauses,
                    stage_times=stage_times,
                    warnings=summary.warnings,
                    adjustment_allowed=not _length_already_corrected(
                        prepared_script
                    ),
                )
                script_text = fit.script_text
                voice_pauses = fit.voice_pauses

            final_result = voice_path

            audio_start = time.perf_counter()

            if music_category:
                try:
                    music_path = MusicSelector().select(
                        music_category
                    )
                except (FileNotFoundError, NotADirectoryError) as error:
                    raise create_missing_asset_error(
                        error, operation="Seleccionar música"
                    ) from error
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

        if (
            "subtitles" in stages
            and render_subtitles
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
                voice_pauses=voice_pauses,
            )
            whisper_subtitle_path = subtitle_path

            optimizer_options = {
                "subtitle_profile": subtitle_profile,
                "render_fps": _required_render_fps(profile),
                "project": project,
            }
            optimized_subtitle_path = (
                SrtOptimizer(**optimizer_options).optimize(
                    canonical_content=script_text,
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

        if (
            "storyboard" in stages
            and builders.get(
                "storyboard",
                False
            )
        ):
            storyboard_builder = StoryboardBuilder(
                config_manager=config_manager,
                project=project,
            )
            storyboard_path, storyboard_elapsed = (
                self._pipeline_telemetry.measure_stage(
                    storyboard_builder.build,
                    subtitle_path=whisper_subtitle_path,
                    voice_pauses=voice_pauses,
                )
            )

            stage_times["Storyboard"] = (
                storyboard_elapsed
            )

            final_result = storyboard_path

        if (
            "images" in stages
            and builders.get(
                "images",
                False
            )
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

        if "video" in stages:
            video_builder_options = {
                "subtitle_profile": subtitle_profile,
                "overlays_mode": overlays_mode,
            }
            if not render_subtitles:
                video_builder_options["render_subtitles"] = False
            if intro_outro_selection is not None:
                video_builder_options[
                    "intro_outro_selection"
                ] = intro_outro_selection

            if visual_pipeline == "video":
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

    def _fit_script_duration(
        self,
        *,
        voice_builder,
        script_options,
        script_text,
        target_seconds,
        voice_path,
        voice_pauses,
        stage_times,
        warnings,
        adjustment_allowed,
    ):
        """Measure a topic script's voice and ask once for an adjusted script."""

        def adjust_script(*, previous_script, measured_seconds, output_path):
            adjusted, elapsed = self._pipeline_telemetry.measure_stage(
                ScriptOperation().execute,
                **{
                    **script_options,
                    "output_script_path": output_path,
                    "adjustment": ScriptAdjustment(
                        previous_script=previous_script,
                        measured_seconds=measured_seconds,
                    ),
                },
            )
            stage_times["Script"] += elapsed
            return adjusted.text

        def synthesize_voice(text, output_path):
            path, elapsed = self._pipeline_telemetry.measure_stage(
                voice_builder.build,
                text,
                output_path=output_path,
            )
            stage_times["Voces"] += elapsed
            return path, _voice_pauses(voice_builder)

        return ScriptDurationFit(
            measure_seconds=MediaProbe.get_duration,
            adjust_script=adjust_script,
            synthesize_voice=synthesize_voice,
            margin=script_duration_margin(script_options["ai_config"]),
            warnings=warnings,
        ).fit(
            script_text=script_text,
            target_seconds=target_seconds,
            script_path=script_options["output_script_path"],
            voice_path=voice_path,
            voice_pauses=voice_pauses,
            adjustment_allowed=adjustment_allowed,
        )


def _length_already_corrected(prepared_script):
    """True when Ollama already fixed the script's length before the voice."""
    metadata = getattr(prepared_script, "metadata", None)
    return bool(getattr(metadata, "length_corrected", False))


def _voice_pauses(voice_builder):
    """Silences the backend wrote into the last voice, as (start, end) seconds."""
    return tuple(
        (pause.start_seconds, pause.end_seconds)
        for pause in getattr(voice_builder, "last_pauses", ())
    )


def _stages_for(pipeline_mode):
    """Return the stages one pipeline mode runs, in execution order."""
    last_stage = _LAST_STAGE_BY_PIPELINE_MODE[pipeline_mode]
    return _STAGES[:_STAGES.index(last_stage) + 1]


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


def _generated_script_pacing(config_manager):
    """Reading rate of the selected voice, required to size a topic script."""
    try:
        configuration = config_manager.get_tts_voice_configuration()
    except TtsVoiceConfigurationError as error:
        raise create_operational_error(
            family="CONFIG",
            user_message=f"La configuración de la voz no es válida: {error}",
            recommended_action=(
                "Corrige el documento de la voz en config/voice_configs/."
            ),
            operation="Preparar el guion",
        ) from error
    if configuration.pacing is None:
        raise create_operational_error(
            family="CONFIG",
            user_message=(
                f"La voz «{configuration.display_name}» no declara su ritmo "
                "(«pacing»), que hace falta para calcular la extensión de un "
                "guion generado por tema."
            ),
            recommended_action=(
                "Añade a su documento en config/voice_configs/ el bloque "
                "«pacing» con «letters_per_second» y «words_per_second» "
                "medidos con esa voz."
            ),
            operation="Preparar el guion",
            technical_metadata={
                "voice_id": configuration.voice.voice_id,
            },
        )
    return configuration.pacing


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
