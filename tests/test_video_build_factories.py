from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.modules.video.ffmpeg.filter_context import FilterContext
from app.modules.video.video_build_context import (
    VideoBuildComponents,
    VideoBuildContext
)
from app.modules.video.video_build_context_factory import (
    VideoBuildContextFactory
)
from app.modules.video.video_component_factory import (
    VideoComponentFactory
)
from app.modules.video.video_filter_context_factory import (
    VideoFilterContextFactory
)
from app.modules.video.video_render_service import (
    VideoRenderService
)


class VideoBuildFactoriesTest(
    unittest.TestCase
):

    def test_context_factory_loads_profile_media_and_timeline(
        self
    ):
        project = SimpleNamespace(
            subtitle_path=lambda: Path(
                "project.srt"
            ),
            images_manifest_path=lambda: Path(
                "project_images.json"
            ),
            video_path=lambda: Path(
                "project.mp4"
            )
        )
        config = SimpleNamespace(
            subtitle_offset=0.25,
            transitions=SimpleNamespace(
                duration=0.4
            ),
            width=640,
            height=360,
            fps=24
        )
        media = SimpleNamespace(
            audio_path=Path(
                "audio.mp3"
            ),
            subtitle_path=Path(
                "subtitles.srt"
            ),
            output_path=Path(
                "out.mp4"
            ),
            image_paths=(
                Path("one.png"),
                Path("two.png")
            )
        )
        timeline = SimpleNamespace(
            audio_duration=4.0,
            image_duration=2.0
        )

        with patch(
            "app.modules.video.video_build_context_factory"
            ".ProjectManager",
            return_value=project
        ), patch(
            "app.modules.video.video_build_context_factory"
            ".AudioResolver"
        ) as audio_resolver_class, patch(
            "app.modules.video.video_build_context_factory"
            ".VideoConfigLoader"
        ) as config_loader_class, patch(
            "app.modules.video.video_build_context_factory"
            ".MediaLoader"
        ) as media_loader_class, patch(
            "app.modules.video.video_build_context_factory"
            ".TimelineBuilder"
        ) as timeline_builder_class:
            audio_resolver_class.return_value.resolve.return_value = (
                Path("audio.mp3")
            )
            config_loader_class.return_value.load.return_value = (
                config
            )
            media_loader_class.return_value.load.return_value = (
                media
            )
            timeline_builder_class.return_value.build.return_value = (
                timeline
            )

            result = VideoBuildContextFactory().build(
                audio_path="audio.mp3",
                subtitle_path="subtitles.srt",
                images_manifest_path="images.json",
                output_path="out.mp4"
            )

        self.assertIs(
            result.config,
            config
        )
        self.assertIs(
            result.media,
            media
        )
        self.assertIs(
            result.timeline,
            timeline
        )
        audio_resolver_class.return_value.resolve.assert_called_once_with(
            project=project,
            audio_path="audio.mp3"
        )
        config_loader_class.return_value.load.assert_called_once_with()
        media_loader_class.return_value.load.assert_called_once_with(
            audio_path=Path("audio.mp3"),
            subtitle_path=Path("subtitles.srt"),
            images_manifest_path=Path("images.json"),
            output_path=Path("out.mp4")
        )
        timeline_builder_class.return_value.build.assert_called_once_with(
            audio_path=media.audio_path,
            subtitle_path=media.subtitle_path,
            image_count=2,
            subtitle_offset=0.25
        )

    def test_component_factory_creates_fresh_builders_and_resets_layers(
        self
    ):
        calls = []

        class FakeLayerBuilder:

            def __init__(
                self,
                config
            ):
                self.config = config

            def reset(
                self
            ):
                calls.append(
                    (
                        "reset",
                        self.config
                    )
                )

        config = SimpleNamespace(
            motion="motion",
            overlays="overlays",
            visual_effects="visual_effects"
        )

        with patch(
            "app.modules.video.video_component_factory"
            ".MotionBuilder",
            side_effect=lambda motion: (
                "motion_builder",
                motion
            )
        ), patch(
            "app.modules.video.video_component_factory"
            ".TransitionBuilder",
            return_value="transition_builder"
        ), patch(
            "app.modules.video.video_component_factory"
            ".OverlayBuilder",
            side_effect=FakeLayerBuilder
        ), patch(
            "app.modules.video.video_component_factory"
            ".VisualEffectBuilder",
            side_effect=FakeLayerBuilder
        ):
            first = VideoComponentFactory().create(
                config
            )
            second = VideoComponentFactory().create(
                config
            )

        self.assertEqual(
            first.motion_builder,
            (
                "motion_builder",
                "motion"
            )
        )
        self.assertEqual(
            first.transition_builder,
            "transition_builder"
        )
        self.assertEqual(
            calls,
            [
                (
                    "reset",
                    "overlays"
                ),
                (
                    "reset",
                    "visual_effects"
                ),
                (
                    "reset",
                    "overlays"
                ),
                (
                    "reset",
                    "visual_effects"
                )
            ]
        )
        self.assertIsNot(
            first.overlay_builder,
            second.overlay_builder
        )
        self.assertIsNot(
            first.visual_effect_builder,
            second.visual_effect_builder
        )

    def test_filter_context_factory_preserves_indices_and_layer_inputs(
        self
    ):
        media = SimpleNamespace(
            image_paths=(
                Path("a.png"),
                Path("b.png")
            )
        )
        config = SimpleNamespace(
            subtitle_style={
                "font": "Arial"
            }
        )
        context = VideoBuildContext(
            config=config,
            media=media,
            timeline=SimpleNamespace()
        )
        components = VideoBuildComponents(
            motion_builder=object(),
            transition_builder=object(),
            overlay_builder=SimpleNamespace(
                inputs=(
                    Path("overlay.mov"),
                )
            ),
            visual_effect_builder=SimpleNamespace(
                inputs=(
                    Path("effect.mov"),
                )
            )
        )

        with patch(
            "app.modules.video.video_filter_context_factory"
            ".SubtitleStyleBuilder"
        ) as style_builder_class:
            style_builder_class.return_value.build.return_value = (
                "style"
            )

            filter_context = (
                VideoFilterContextFactory().build(
                    build_context=context,
                    components=components
                )
            )

        self.assertIsInstance(
            filter_context,
            FilterContext
        )
        self.assertEqual(
            filter_context.subtitle_style,
            "style"
        )
        self.assertEqual(
            filter_context.first_overlay_input,
            3
        )
        self.assertEqual(
            filter_context.first_visual_effect_input,
            4
        )
        self.assertEqual(
            filter_context.overlay_inputs,
            (
                Path("overlay.mov"),
            )
        )
        self.assertEqual(
            filter_context.visual_effect_inputs,
            (
                Path("effect.mov"),
            )
        )

    def test_render_service_preserves_filter_complex_and_command(
        self
    ):
        build_context = VideoBuildContext(
            config=SimpleNamespace(
                codec="libx264",
                preset="medium",
                crf=18,
                fps=30,
                pixel_format="yuv420p",
                audio_codec="aac",
                audio_bitrate="192k",
                movflags="+faststart",
                transitions=SimpleNamespace(
                    duration=0.4
                ),
                overlays=SimpleNamespace(
                    loop_file=True
                ),
                visual_effects=SimpleNamespace(
                    loop_file=False
                )
            ),
            media=SimpleNamespace(
                image_paths=(
                    Path("a.png"),
                ),
                audio_path=Path("audio.mp3"),
                output_path=Path("out.mp4")
            ),
            timeline=SimpleNamespace(
                audio_duration=4.0
            )
        )
        components = VideoBuildComponents(
            motion_builder="motion",
            transition_builder="transition",
            overlay_builder=SimpleNamespace(
                inputs=(
                    Path("overlay.mov"),
                )
            ),
            visual_effect_builder=SimpleNamespace(
                inputs=(
                    Path("effect.mov"),
                )
            )
        )
        filter_context = object()

        with patch(
            "app.modules.video.video_render_service"
            ".FilterBuilder"
        ) as filter_builder_class, patch(
            "app.modules.video.video_render_service"
            ".CommandBuilder"
        ) as command_builder_class:
            filter_builder_class.return_value.build.return_value = (
                "[filter][vout]"
            )
            command_builder_class.return_value.build.return_value = [
                "ffmpeg",
                "-filter_complex",
                "[filter][vout]"
            ]

            artifacts = (
                VideoRenderService().build_artifacts(
                    build_context=build_context,
                    filter_context=filter_context,
                    components=components
                )
            )

        self.assertEqual(
            artifacts.filter_complex,
            "[filter][vout]"
        )
        self.assertEqual(
            artifacts.command,
            [
                "ffmpeg",
                "-filter_complex",
                "[filter][vout]"
            ]
        )
        filter_builder_class.return_value.build.assert_called_once_with(
            context=filter_context,
            motion_builder="motion",
            transition_builder="transition",
            overlay_builder=components.overlay_builder,
            visual_effect_builder=(
                components.visual_effect_builder
            )
        )
        command_builder_class.return_value.build.assert_called_once_with(
            images=build_context.media.image_paths,
            audio_path=build_context.media.audio_path,
            output_path=build_context.media.output_path,
            filter_complex="[filter][vout]",
            codec="libx264",
            preset="medium",
            crf=18,
            fps=30,
            pixel_format="yuv420p",
            audio_codec="aac",
            audio_bitrate="192k",
            movflags="+faststart",
            audio_duration=4.0,
            transition_duration=0.4,
            overlay_inputs=(
                Path("overlay.mov"),
            ),
            visual_effect_inputs=(
                Path("effect.mov"),
            ),
            overlay_loop_file=True,
            visual_effect_loop_file=False
        )


if __name__ == "__main__":
    unittest.main()
