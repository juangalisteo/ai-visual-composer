from app.modules.video.ffmpeg.command_builder import CommandBuilder
from app.modules.video.ffmpeg.filter_builder import FilterBuilder
from app.modules.video.ffmpeg.runner import Runner
from app.modules.video.video_build_context import VideoBuildArtifacts
from app.modules.video.video_validator import VideoValidator
from app.modules.video.intro_outro import IntroOutroComposer
from pathlib import Path
import time


class VideoRenderService:

    def __init__(
        self,
        intro_outro_selection=None,
        intro_outro_composer=None,
    ):
        self.intro_outro_selection = (
            intro_outro_selection
        )
        self.intro_outro_composer = (
            intro_outro_composer
            or IntroOutroComposer()
        )

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
            self.validate(
                build_context=build_context,
                output_path=artifacts.render_output_path,
            )
            promoted_path = Path(
                artifacts.render_output_path
            )
            final_command = artifacts.command
            final_stderr = getattr(
                result,
                "stderr",
                "",
            )

            if self.intro_outro_selection is not None:
                composition = (
                    self.intro_outro_composer.compose(
                        main_path=artifacts.render_output_path,
                        final_path=build_context.media.output_path,
                        selection=self.intro_outro_selection,
                        config=build_context.config,
                        expected_main_duration=(
                            build_context.timeline.audio_duration
                        ),
                    )
                )
                promoted_path = composition.output_path
                final_command = list(composition.command)
                final_stderr = composition.stderr

            promoted_path.replace(
                build_context.media.output_path
            )
            if (
                self.intro_outro_selection is not None
                and Path(artifacts.render_output_path).exists()
            ):
                Path(artifacts.render_output_path).unlink()
            elapsed = time.perf_counter() - start
        except Exception as error:
            diagnostics.record_final_assembly(
                command=(
                    getattr(error, "cmd", None)
                    or artifacts.command
                ),
                elapsed=time.perf_counter() - start,
                stderr=str(
                    getattr(error, "stderr", "")
                    or ""
                ),
                status="FAILED",
            )
            raise

        diagnostics.record_final_assembly(
            command=final_command,
            elapsed=elapsed,
            stderr=final_stderr,
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
