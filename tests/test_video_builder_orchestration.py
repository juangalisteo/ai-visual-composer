from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from app.modules.video.video_build_context import (
    VideoBuildArtifacts,
    VideoBuildComponents,
    VideoBuildContext
)
from app.modules.video.video_builder import VideoBuilder


class VideoBuilderOrchestrationTest(
    unittest.TestCase
):

    def make_context(
        self,
        output_path="out.mp4"
    ):
        return VideoBuildContext(
            config=SimpleNamespace(),
            media=SimpleNamespace(
                output_path=Path(output_path),
                image_paths=(),
                media_types=(),
                media_durations=(),
            ),
            timeline=SimpleNamespace()
        )

    def make_components(
        self
    ):
        return VideoBuildComponents(
            motion_builder=object(),
            transition_builder=object(),
            overlay_builder=object(),
            visual_effect_builder=object()
        )

    def make_filter_context(
        self
    ):
        return SimpleNamespace(
            cleanup_temporary_subtitle=Mock()
        )

    def test_build_keeps_public_api_and_returns_output_path(
        self
    ):
        order = []
        context = self.make_context(
            "final.mp4"
        )
        components = self.make_components()
        filter_context = self.make_filter_context()
        artifacts = VideoBuildArtifacts(
            filter_complex="[vout]",
            command=[
                "ffmpeg"
            ]
        )

        with patch(
            "app.modules.video.video_builder"
            ".VideoBuildContextFactory"
        ) as context_factory_class, patch(
            "app.modules.video.video_builder"
            ".VideoComponentFactory"
        ) as component_factory_class, patch(
            "app.modules.video.video_builder"
            ".VideoFilterContextFactory"
        ) as filter_context_factory_class, patch(
            "app.modules.video.video_builder"
            ".VideoRenderService"
        ) as render_service_class, patch(
            "app.modules.video.video_builder"
            ".FFmpegDiagnostics"
        ) as diagnostics_class:
            context_factory = (
                context_factory_class.return_value
            )
            component_factory = (
                component_factory_class.return_value
            )
            filter_context_factory = (
                filter_context_factory_class.return_value
            )
            render_service = (
                render_service_class.return_value
            )

            def build_context(
                **kwargs
            ):
                order.append(
                    "context"
                )
                return context

            def create_components(
                video_config
            ):
                order.append(
                    "components"
                )
                self.assertIs(
                    video_config,
                    context.config
                )
                return components

            def build_filter_context(
                build_context,
                components
            ):
                order.append(
                    "filter_context"
                )
                self.assertIs(
                    build_context,
                    context
                )
                return filter_context

            def build_artifacts(
                build_context,
                filter_context,
                components
            ):
                order.append(
                    "artifacts"
                )
                return artifacts

            def render_final(
                build_context,
                artifacts,
                diagnostics,
            ):
                order.append("render_final")
                self.assertIs(
                    build_context,
                    context
                )

            context_factory.build.side_effect = (
                build_context
            )
            component_factory.create.side_effect = (
                create_components
            )
            filter_context_factory.build.side_effect = (
                build_filter_context
            )
            render_service.build_artifacts.side_effect = (
                build_artifacts
            )
            render_service.render_final.side_effect = (
                render_final
            )

            output = VideoBuilder().build(
                audio_path="audio.mp3",
                subtitle_path="subtitles.srt",
                images_manifest_path="images.json",
                output_path="final.mp4"
            )

        self.assertEqual(
            output,
            Path("final.mp4")
        )
        self.assertEqual(
            order,
            [
                "context",
                "components",
                "filter_context",
                "artifacts",
                "render_final"
            ]
        )
        context_factory.build.assert_called_once_with(
            audio_path="audio.mp3",
            subtitle_path="subtitles.srt",
            images_manifest_path="images.json",
            video_clips_manifest_path=None,
            output_path="final.mp4"
        )
        filter_context.cleanup_temporary_subtitle.assert_called_once_with()

    def test_build_accepts_video_clips_manifest_without_changing_api(
        self
    ):
        context = self.make_context(
            "final.mp4"
        )
        components = self.make_components()
        artifacts = VideoBuildArtifacts(
            filter_complex="[vout]",
            command=[
                "ffmpeg"
            ]
        )
        filter_context = self.make_filter_context()

        with patch(
            "app.modules.video.video_builder"
            ".VideoBuildContextFactory"
        ) as context_factory_class, patch(
            "app.modules.video.video_builder"
            ".VideoComponentFactory"
        ) as component_factory_class, patch(
            "app.modules.video.video_builder"
            ".VideoFilterContextFactory"
        ) as filter_context_factory_class, patch(
            "app.modules.video.video_builder"
            ".VideoRenderService"
        ) as render_service_class, patch(
            "app.modules.video.video_builder"
            ".FFmpegDiagnostics"
        ) as diagnostics_class:
            context_factory_class.return_value.build.return_value = (
                context
            )
            component_factory_class.return_value.create.return_value = (
                components
            )
            filter_context_factory_class.return_value.build.return_value = (
                filter_context
            )
            render_service_class.return_value.build_artifacts.return_value = (
                artifacts
            )

            output = VideoBuilder().build(
                audio_path="audio.mp3",
                subtitle_path="subtitles.srt",
                video_clips_manifest_path="video_clips.json",
                output_path="final.mp4"
            )

        self.assertEqual(
            Path(
                "final.mp4"
            ),
            output
        )
        context_factory_class.return_value.build.assert_called_once_with(
            audio_path="audio.mp3",
            subtitle_path="subtitles.srt",
            images_manifest_path=None,
            video_clips_manifest_path="video_clips.json",
            output_path="final.mp4"
        )
        filter_context.cleanup_temporary_subtitle.assert_called_once_with()

    def test_build_transports_explicit_disabled_subtitle_rendering(self):
        context = self.make_context("final.mp4")
        components = self.make_components()

        with patch(
            "app.modules.video.video_builder.VideoBuildContextFactory"
        ) as context_factory_class, patch(
            "app.modules.video.video_builder.VideoComponentFactory"
        ) as component_factory_class, patch(
            "app.modules.video.video_builder.VideoFilterContextFactory"
        ), patch(
            "app.modules.video.video_builder.VideoRenderService"
        ) as render_service_class, patch(
            "app.modules.video.video_builder.FFmpegDiagnostics"
        ):
            context_factory_class.return_value.build.return_value = context
            component_factory_class.return_value.create.return_value = components
            render_service_class.return_value.build_artifacts.return_value = (
                VideoBuildArtifacts(filter_complex="[vout]", command=["ffmpeg"])
            )

            VideoBuilder(render_subtitles=False).build(
                audio_path="audio.mp3",
                subtitle_path="subtitles.srt",
                images_manifest_path="images.json",
                output_path="final.mp4",
            )

        context_factory_class.return_value.build.assert_called_once_with(
            audio_path="audio.mp3",
            subtitle_path="subtitles.srt",
            images_manifest_path="images.json",
            video_clips_manifest_path=None,
            output_path="final.mp4",
            render_subtitles=False,
        )

    def test_build_passes_intro_outro_only_to_render_service(self):
        context = self.make_context("final.mp4")
        selection = object()

        with patch(
            "app.modules.video.video_builder.VideoBuildContextFactory"
        ) as context_factory_class, patch(
            "app.modules.video.video_builder.VideoComponentFactory"
        ) as component_factory_class, patch(
            "app.modules.video.video_builder.VideoFilterContextFactory"
        ), patch(
            "app.modules.video.video_builder.VideoRenderService"
        ) as render_service_class, patch(
            "app.modules.video.video_builder.FFmpegDiagnostics"
        ):
            context_factory_class.return_value.build.return_value = context
            component_factory_class.return_value.create.return_value = (
                self.make_components()
            )
            render_service_class.return_value.build_artifacts.return_value = (
                VideoBuildArtifacts(
                    filter_complex="[vout]",
                    command=["ffmpeg"],
                )
            )

            VideoBuilder(
                intro_outro_selection=selection
            ).build()

        render_service_class.assert_called_once_with(
            intro_outro_selection=selection
        )

    def test_exception_from_context_preparation_propagates(
        self
    ):
        with patch(
            "app.modules.video.video_builder"
            ".VideoBuildContextFactory"
        ) as context_factory_class:
            context_factory_class.return_value.build.side_effect = (
                RuntimeError(
                    "boom"
                )
            )

            with self.assertRaisesRegex(
                RuntimeError,
                "boom"
            ):
                VideoBuilder().build()

    def test_same_video_builder_instance_does_not_share_state(
        self
    ):
        contexts = [
            self.make_context(
                "first.mp4"
            ),
            self.make_context(
                "second.mp4"
            )
        ]
        components = [
            self.make_components(),
            self.make_components()
        ]
        filter_contexts = [
            self.make_filter_context(),
            self.make_filter_context(),
        ]
        artifacts = [
            VideoBuildArtifacts(
                filter_complex="[first]",
                command=[
                    "first"
                ]
            ),
            VideoBuildArtifacts(
                filter_complex="[second]",
                command=[
                    "second"
                ]
            )
        ]
        seen_commands = []

        with patch(
            "app.modules.video.video_builder"
            ".VideoBuildContextFactory"
        ) as context_factory_class, patch(
            "app.modules.video.video_builder"
            ".VideoComponentFactory"
        ) as component_factory_class, patch(
            "app.modules.video.video_builder"
            ".VideoFilterContextFactory"
        ) as filter_context_factory_class, patch(
            "app.modules.video.video_builder"
            ".VideoRenderService"
        ) as render_service_class, patch(
            "app.modules.video.video_builder"
            ".FFmpegDiagnostics"
        ) as diagnostics_class:
            context_factory_class.return_value.build.side_effect = (
                contexts
            )
            component_factory_class.return_value.create.side_effect = (
                components
            )
            filter_context_factory_class.return_value.build.side_effect = (
                filter_contexts
            )
            render_service_class.return_value.build_artifacts.side_effect = (
                artifacts
            )
            render_service_class.return_value.render_final.side_effect = (
                lambda build_context, artifacts, diagnostics:
                seen_commands.append(list(artifacts.command))
            )

            builder = VideoBuilder()

            first_output = builder.build()
            second_output = builder.build()

        self.assertEqual(
            first_output,
            Path("first.mp4")
        )
        self.assertEqual(
            second_output,
            Path("second.mp4")
        )
        self.assertEqual(
            seen_commands,
            [
                [
                    "first"
                ],
                [
                    "second"
                ]
            ]
        )
        self.assertIsNot(
            components[0].overlay_builder,
            components[1].overlay_builder
        )
        self.assertIsNot(
            components[0].visual_effect_builder,
            components[1].visual_effect_builder
        )
        for filter_context in filter_contexts:
            filter_context.cleanup_temporary_subtitle.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
