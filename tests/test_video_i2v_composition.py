import json
import os
from pathlib import Path
from types import SimpleNamespace
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from app.modules.video.ffmpeg.diagnostics import FFmpegDiagnostics
from app.modules.video.ffmpeg.i2v_normalizer import I2VClipNormalizer
from app.modules.video.media.media_loader import VideoMedia
from app.modules.video.video_build_context import (
    VideoBuildArtifacts,
    VideoBuildContext,
)
from app.modules.video.video_render_service import VideoRenderService
from app.modules.video.video_validator import VideoValidator
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
            "MC_PROFILE_COMPONENT": profile_key.component.value,
            "MC_PROFILE_PLATFORM": profile_key.platform,
            "MC_PROFILE_ID": profile_key.profile_id,
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
                scene_count=2
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
        graph = I2VClipNormalizer().build_filter(
            source_frame_count=48,
            duration=4.4,
            width=1080,
            height=1920,
            fps=30,
            pixel_format="yuv420p",
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

    def test_normalizer_command_preserves_instagram_contract(self):
        command = I2VClipNormalizer().build_command(
            source_path=Path("wan.mp4"),
            output_path=Path("scene_001.mp4"),
            source_frame_count=48,
            duration=4.4,
            config=self.make_config(),
        )

        graph = command[command.index("-filter_complex") + 1]
        self.assertIn("scale=1080:1920", graph)
        self.assertIn("fps=30", graph)
        self.assertIn("format=yuv420p", graph)
        self.assertEqual(command[-1], "scene_001.mp4")

    def test_normalizer_command_preserves_youtube_contract(self):
        command = I2VClipNormalizer().build_command(
            source_path=Path("wan.mp4"),
            output_path=Path("scene_001.mp4"),
            source_frame_count=48,
            duration=4.4,
            config=self.make_config(
                width=1920,
                height=1080,
            ),
        )

        graph = command[command.index("-filter_complex") + 1]
        self.assertIn("scale=1920:1080", graph)
        self.assertIn("fps=30", graph)
        self.assertIn("format=yuv420p", graph)

    def test_normalizer_processes_each_i2v_scene_into_project_temporaries(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            first_source = root / "wan_001.mp4"
            second_source = root / "wan_002.mp4"
            first_source.write_bytes(b"source")
            second_source.write_bytes(b"source")
            final_path = root / "video" / "final.mp4"
            context = VideoBuildContext(
                config=self.make_config(),
                media=VideoMedia(
                    audio_path=root / "audio.mp3",
                    subtitle_path=root / "subtitles.srt",
                    images_manifest_path=root / "clips.json",
                    output_path=final_path,
                    image_paths=(first_source, second_source),
                    media_types=("video", "video"),
                    media_durations=(4.0, 4.0),
                ),
                timeline=SimpleNamespace(
                    image_duration=4.0,
                ),
            )
            diagnostics = FFmpegDiagnostics(
                output_path=final_path,
                scene_count=2,
            )

            def render_clip(command):
                Path(command[-1]).write_bytes(b"normalized")
                return SimpleNamespace(stderr="")

            with patch(
                "app.modules.video.ffmpeg.i2v_normalizer"
                ".MediaProbe.get_video_frame_count",
                return_value=48,
            ), patch(
                "app.modules.video.ffmpeg.i2v_normalizer.Runner"
            ) as runner_class, patch(
                "app.modules.video.ffmpeg.i2v_normalizer.VideoValidator"
            ) as validator_class:
                runner_class.return_value.run.side_effect = render_clip
                normalized = I2VClipNormalizer().normalize(
                    build_context=context,
                    diagnostics=diagnostics,
                )

            self.assertEqual(
                normalized.media.image_paths,
                (
                    root / "video" / "i2v_normalized" / "scene_001.mp4",
                    root / "video" / "i2v_normalized" / "scene_002.mp4",
                ),
            )
            self.assertEqual(
                normalized.media.media_durations,
                (4.4, 4.0),
            )
            self.assertEqual(
                runner_class.return_value.run.call_count,
                2,
            )
            self.assertEqual(
                validator_class.return_value.validate.call_count,
                2,
            )

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

    def test_failed_i2v_normalization_keeps_diagnostic_reference(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source_path = root / "wan.mp4"
            source_path.write_bytes(b"source")
            final_path = root / "video" / "final.mp4"
            context = VideoBuildContext(
                config=self.make_config(),
                media=VideoMedia(
                    audio_path=root / "audio.mp3",
                    subtitle_path=root / "subtitles.srt",
                    images_manifest_path=root / "clips.json",
                    output_path=final_path,
                    image_paths=(source_path,),
                    media_types=("video",),
                    media_durations=(4.0,),
                ),
                timeline=SimpleNamespace(image_duration=4.0),
            )
            diagnostics = FFmpegDiagnostics(output_path=final_path, scene_count=1)
            failure = subprocess.CalledProcessError(
                8, ["ffmpeg", "-i", str(source_path)], stderr="normalize failed"
            )
            with patch(
                "app.modules.video.ffmpeg.i2v_normalizer.MediaProbe.get_video_frame_count",
                return_value=48,
            ), patch("app.modules.video.ffmpeg.i2v_normalizer.Runner") as runner_class, self.assertRaises(OperationalError) as caught:
                runner_class.return_value.run.side_effect = failure
                I2VClipNormalizer().normalize(context, diagnostics)

            self.assertEqual("FFMPEG", caught.exception.context.family)
            self.assertEqual(str(diagnostics.path), caught.exception.context.diagnostic_reference)
            self.assertIs(caught.exception.__cause__, failure)
            diagnostic = diagnostics.path.read_text(encoding="utf-8")
            self.assertIn("normalize failed", diagnostic)
            self.assertIn('"FAILED"', diagnostic)

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
