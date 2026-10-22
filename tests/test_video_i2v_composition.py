import json
import os
from pathlib import Path
from types import SimpleNamespace
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from app.modules.video.ffmpeg.diagnostics import FFmpegDiagnostics
from app.modules.video.ffmpeg.i2v_normalizer import I2VClipTransform
from app.modules.video.video_build_context import (
    VideoBuildArtifacts,
)
from app.modules.video.video_render_service import VideoRenderService
from app.modules.video.video_validator import VideoValidator
from app.shared.config_manager import ConfigManager
from app.shared.profile_identity import (
    OperationalProfileKey,
    ProfileComponent,
)
from app.shared.profile_resolver import ProfileResolver
from app.shared.operational_error import OperationalError


class I2VCompositionTest(unittest.TestCase):

    def make_config(
        self,
        width=1080,
        height=1920,
    ):
        return SimpleNamespace(
            width=width,
            height=height,
            fps=30,
            pixel_format="yuv420p",
            codec="libx264",
            preset="medium",
            crf=18,
            movflags="+faststart",
            transitions=SimpleNamespace(
                enabled=True,
                duration=0.4,
            ),
            validation=SimpleNamespace(
                max_duration_difference=0.2,
            ),
        )

    def test_diagnostics_uses_structured_profile_identity(self):
        profile_key = OperationalProfileKey(
            ProfileComponent.VIDEO,
            "instagram",
            "video_instagram",
        )
        environment = {
            "MC_PROFILE_PATH": "C:/arbitrary/profile.json",
        }

        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,
            environment,
            clear=True
        ):
            output_path = Path(directory) / "video" / "final.mp4"
            diagnostics = FFmpegDiagnostics(
                output_path=output_path,
                scene_count=2,
                config_manager=ConfigManager(
                    operational_profile_key=profile_key
                ),
            )
            persisted = json.loads(
                diagnostics.path.read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(
            {
                "component": "video",
                "platform": "instagram",
                "profile_id": "video_instagram",
                "path": str(
                    ProfileResolver().resolve_operational(profile_key)
                ),
            },
            persisted["profile"]
        )

    def test_pingpong_happens_before_delivery_scale_and_fps(self):
        graph = I2VClipTransform().build_filter(
            source_frame_count=48,
            duration=4.4,
            width=1080,
            height=1920,
            fps=30,
            pixel_format="yuv420p",
            input_stream="[0:v]",
            output_stream="[vout]",
            label_prefix="i2v_0",
        )

        self.assertIn(
            "reverse,trim=start_frame=1:end_frame=47",
            graph,
        )
        self.assertIn(
            "loop=loop=-1:size=94:start=0",
            graph,
        )
        self.assertLess(
            graph.index("reverse"),
            graph.index("scale=1080:1920"),
        )
        self.assertLess(
            graph.index("reverse"),
            graph.index("fps=30"),
        )
        self.assertIn(
            "trim=duration=4.400000",
            graph,
        )

    def test_transform_preserves_instagram_contract(self):
        graph = I2VClipTransform().build_filter(
            source_frame_count=48,
            duration=4.4,
            width=1080,
            height=1920,
            fps=30,
            pixel_format="yuv420p",
            input_stream="[0:v]",
            output_stream="[v0]",
            label_prefix="i2v_0",
        )

        self.assertIn("scale=1080:1920", graph)
        self.assertIn("fps=30", graph)
        self.assertIn("format=yuv420p", graph)
        self.assertTrue(graph.endswith("[v0]"))

    def test_transform_preserves_youtube_contract(self):
        graph = I2VClipTransform().build_filter(
            source_frame_count=48,
            duration=4.4,
            width=1920,
            height=1080,
            fps=30,
            pixel_format="yuv420p",
            input_stream="[0:v]",
            output_stream="[v0]",
            label_prefix="i2v_0",
        )

        self.assertIn("scale=1920:1080", graph)
        self.assertIn("fps=30", graph)
        self.assertIn("format=yuv420p", graph)

    def test_transform_is_pure_and_does_not_encode_an_intermediate_mp4(self):
        graph = I2VClipTransform().build_filter(
            source_frame_count=48,
            duration=4.4,
            width=1080,
            height=1920,
            fps=30,
            pixel_format="yuv420p",
            input_stream="[0:v]",
            output_stream="[v0]",
            label_prefix="i2v_0",
        )

        self.assertIn("[0:v]trim=start_frame=0:end_frame=48", graph)
        self.assertNotIn(".mp4", graph)

    def test_final_command_consumes_raw_i2v_input_without_normalized_path(self):
        raw_path = Path("wan_raw.mp4")
        context = SimpleNamespace(
            media=SimpleNamespace(
                image_paths=(raw_path,),
                audio_path=Path("audio.mp3"),
                output_path=Path("final.mp4"),
                media_types=("video",),
            ),
            timeline=SimpleNamespace(audio_duration=4.0),
            config=SimpleNamespace(
                codec="libx264",
                preset="slow",
                crf=16,
                fps=30,
                pixel_format="yuv420p",
                audio_codec="aac",
                audio_bitrate="192k",
                movflags="+faststart",
                transitions=SimpleNamespace(duration=0.4),
                overlays=SimpleNamespace(loop_file=True),
                visual_effects=SimpleNamespace(loop_file=True),
            ),
        )
        filter_context = SimpleNamespace(render_subtitles=False)
        components = SimpleNamespace(
            motion_builder=object(),
            transition_builder=object(),
            overlay_builder=SimpleNamespace(inputs=()),
            visual_effect_builder=SimpleNamespace(inputs=()),
        )

        with patch(
            "app.modules.video.video_render_service.FilterBuilder"
        ) as filter_builder_class:
            filter_builder_class.return_value.build.return_value = (
                "[0:v]trim=start_frame=0:end_frame=49[vout]"
            )
            artifacts = VideoRenderService().build_artifacts(
                build_context=context,
                filter_context=filter_context,
                components=components,
            )

        self.assertIn(str(raw_path), artifacts.command)
        self.assertNotIn("i2v_normalized", " ".join(artifacts.command))
        self.assertEqual(1, artifacts.command.count("-c:v"))

    def test_failed_render_keeps_final_path_unpublished(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            final_path = root / "final.mp4"
            render_path = root / "final.rendering.mp4"
            render_path.write_bytes(b"partial")
            context = SimpleNamespace(
                media=SimpleNamespace(output_path=final_path),
                timeline=SimpleNamespace(audio_duration=4.0),
                config=SimpleNamespace(
                    validation=SimpleNamespace(
                        max_duration_difference=0.2,
                    ),
                ),
            )
            artifacts = VideoBuildArtifacts(
                filter_complex="[vout]",
                command=["ffmpeg"],
                render_output_path=render_path,
            )
            diagnostics = FFmpegDiagnostics(
                output_path=final_path,
                scene_count=1,
            )

            with patch(
                "app.modules.video.video_render_service.Runner"
            ) as runner_class:
                runner_class.return_value.run.side_effect = (
                    subprocess.CalledProcessError(
                        12,
                        ["ffmpeg"],
                        stderr="allocation failed",
                    )
                )

                with self.assertRaises(OperationalError) as caught:
                    VideoRenderService().render_final(
                        build_context=context,
                        artifacts=artifacts,
                        diagnostics=diagnostics,
                    )

            self.assertEqual("FFMPEG", caught.exception.context.family)
            self.assertEqual(str(diagnostics.path), caught.exception.context.diagnostic_reference)
            self.assertIsInstance(caught.exception.__cause__, subprocess.CalledProcessError)

            self.assertFalse(final_path.exists())
            self.assertTrue(render_path.exists())
            self.assertIn(
                '"status": "FAILED"',
                diagnostics.path.read_text(encoding="utf-8"),
            )

    def test_successful_render_promotes_validated_temporary_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            final_path = root / "final.mp4"
            render_path = root / "final.rendering.mp4"
            context = SimpleNamespace(
                media=SimpleNamespace(output_path=final_path),
                timeline=SimpleNamespace(audio_duration=4.0),
                config=SimpleNamespace(
                    validation=SimpleNamespace(
                        max_duration_difference=0.2,
                    ),
                ),
            )
            artifacts = VideoBuildArtifacts(
                filter_complex="[vout]",
                command=["ffmpeg"],
                render_output_path=render_path,
            )
            diagnostics = FFmpegDiagnostics(
                output_path=final_path,
                scene_count=1,
            )

            def render_file(command):
                render_path.write_bytes(b"valid")
                return SimpleNamespace(stderr="")

            with patch.object(
                VideoRenderService,
                "run",
                side_effect=render_file,
            ), patch.object(
                VideoRenderService,
                "validate",
            ) as validate:
                VideoRenderService().render_final(
                    build_context=context,
                    artifacts=artifacts,
                    diagnostics=diagnostics,
                )

            validate.assert_called_once_with(
                build_context=context,
                output_path=render_path,
            )
            self.assertTrue(final_path.exists())
            self.assertFalse(render_path.exists())

    def test_failed_duration_validation_keeps_final_path_unpublished(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            final_path = root / "final.mp4"
            render_path = root / "final.rendering.mp4"
            context = SimpleNamespace(
                media=SimpleNamespace(output_path=final_path),
                timeline=SimpleNamespace(audio_duration=4.0),
                config=SimpleNamespace(
                    validation=SimpleNamespace(
                        max_duration_difference=0.2,
                    ),
                ),
            )
            artifacts = VideoBuildArtifacts(
                filter_complex="[vout]",
                command=["ffmpeg"],
                render_output_path=render_path,
            )
            diagnostics = FFmpegDiagnostics(
                output_path=final_path,
                scene_count=1,
            )

            def render_file(command):
                render_path.write_bytes(b"wrong-duration")
                return SimpleNamespace(stderr="")

            with patch.object(
                VideoRenderService,
                "run",
                side_effect=render_file,
            ), patch.object(
                VideoRenderService,
                "validate",
                side_effect=RuntimeError("wrong duration"),
            ), self.assertRaisesRegex(RuntimeError, "wrong duration"):
                VideoRenderService().render_final(
                    build_context=context,
                    artifacts=artifacts,
                    diagnostics=diagnostics,
                )

            self.assertFalse(final_path.exists())
            self.assertTrue(render_path.exists())

    def test_duration_outside_tolerance_is_not_valid(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "video.mp4"
            output_path.write_bytes(b"video")

            with patch(
                "app.modules.video.video_validator.MediaProbe.get_duration",
                return_value=3.0,
            ), self.assertRaises(OperationalError) as caught:
                VideoValidator().validate(
                    output_path=output_path,
                    expected_duration=4.0,
                    max_duration_difference=0.2,
                )

        self.assertEqual("VALIDATION", caught.exception.context.family)
        self.assertIsInstance(caught.exception.__cause__, RuntimeError)


if __name__ == "__main__":
    unittest.main()
