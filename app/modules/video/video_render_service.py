from app.modules.video.ffmpeg.command_builder import CommandBuilder
from app.modules.video.ffmpeg.filter_builder import FilterBuilder
from app.modules.video.ffmpeg.runner import Runner
from app.modules.video.video_build_context import VideoBuildArtifacts
from app.modules.video.video_validator import VideoValidator
from pathlib import Path
import time


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

        render_output_path = self._render_output_path(
            build_context.media.output_path
        )

        command = CommandBuilder().build(
            images=build_context.media.image_paths,
            audio_path=build_context.media.audio_path,
            output_path=render_output_path,
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
            media_types=(
                getattr(
                    build_context.media,
                    "media_types",
                    ()
                )
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
            command=command,
            render_output_path=render_output_path,
        )

    def run(
        self,
        command
    ):
        return Runner().run(command)

    def render_final(
        self,
        build_context,
        artifacts,
        diagnostics,
    ):
        start = time.perf_counter()

        try:
            result = self.run(
                artifacts.command
            )
            elapsed = time.perf_counter() - start
            self.validate(
                build_context=build_context,
                output_path=artifacts.render_output_path,
            )
            Path(artifacts.render_output_path).replace(
                build_context.media.output_path
            )
        except Exception as error:
            diagnostics.record_final_assembly(
                command=artifacts.command,
                elapsed=time.perf_counter() - start,
                stderr=str(
                    getattr(error, "stderr", "")
                    or ""
                ),
                status="FAILED",
            )
            raise

        diagnostics.record_final_assembly(
            command=artifacts.command,
            elapsed=elapsed,
            stderr=getattr(result, "stderr", ""),
        )

    def validate(
        self,
        build_context,
        output_path=None,
    ):
        return VideoValidator().validate(
            output_path=(
                output_path
                or build_context.media.output_path
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

    def _render_output_path(
        self,
        output_path,
    ):
        output_path = Path(output_path)
        return output_path.with_name(
            f"{output_path.stem}.rendering"
            f"{output_path.suffix}"
        )
