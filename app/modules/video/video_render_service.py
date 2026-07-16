from app.modules.video.ffmpeg.command_builder import CommandBuilder
from app.modules.video.ffmpeg.filter_builder import FilterBuilder
from app.modules.video.ffmpeg.runner import Runner
from app.modules.video.video_build_context import VideoBuildArtifacts
from app.modules.video.video_validator import VideoValidator


class VideoRenderService:

    def build_artifacts(
        self,
        build_context,
        filter_context,
        components
    ):
        filter_complex = FilterBuilder().build(
            context=filter_context,
            motion_builder=(
                components.motion_builder
            ),
            transition_builder=(
                components.transition_builder
            ),
            overlay_builder=(
                components.overlay_builder
            ),
            visual_effect_builder=(
                components.visual_effect_builder
            )
        )

        command = CommandBuilder().build(
            images=build_context.media.image_paths,
            audio_path=build_context.media.audio_path,
            output_path=build_context.media.output_path,
            filter_complex=filter_complex,
            codec=build_context.config.codec,
            preset=build_context.config.preset,
            crf=build_context.config.crf,
            fps=build_context.config.fps,
            pixel_format=(
                build_context.config.pixel_format
            ),
            audio_codec=(
                build_context.config.audio_codec
            ),
            audio_bitrate=(
                build_context.config.audio_bitrate
            ),
            movflags=build_context.config.movflags,
            audio_duration=(
                build_context.timeline.audio_duration
            ),
            transition_duration=(
                build_context.config.transitions.duration
            ),
            overlay_inputs=(
                components.overlay_builder.inputs
            ),
            visual_effect_inputs=(
                components.visual_effect_builder.inputs
            ),
            overlay_loop_file=(
                build_context.config.overlays.loop_file
            ),
            visual_effect_loop_file=(
                build_context.config.visual_effects.loop_file
            )
        )

        return VideoBuildArtifacts(
            filter_complex=filter_complex,
            command=command
        )

    def run(
        self,
        command
    ):
        Runner().run(
            command
        )

    def validate(
        self,
        build_context
    ):
        return VideoValidator().validate(
            output_path=(
                build_context.media.output_path
            ),
            expected_duration=(
                build_context.timeline.audio_duration
            ),
            max_duration_difference=(
                build_context
                .config
                .validation
                .max_duration_difference
            )
        )
