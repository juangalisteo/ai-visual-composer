from pathlib import Path
import tempfile
import unittest

from app.modules.video.ffmpeg.command_builder import CommandBuilder
from app.modules.video.ffmpeg.command_plan import CommandPlanBuilder


class CommandBuilderTest(
    unittest.TestCase
):

    def build_command(
        self,
        **overrides
    ):
        options = {
            "images": [
                Path("img_01.png"),
                Path("img_02.png")
            ],
            "audio_path": Path("audio.mp3"),
            "output_path": Path("out.mp4"),
            "filter_complex": "[0:v]null[vout]",
            "codec": "libx264",
            "preset": "medium",
            "crf": 18,
            "fps": 30,
            "pixel_format": "yuv420p",
            "audio_codec": "aac",
            "audio_bitrate": "192k",
            "movflags": "+faststart",
            "audio_duration": 4.0,
            "transition_duration": 0.4
        }
        options.update(
            overrides
        )

        return CommandBuilder().build(
            **options
        )

    def test_build_preserves_basic_command_order_and_options(
        self
    ):
        command = self.build_command()

        self.assertEqual(
            command,
            [
                "ffmpeg",
                "-y",
                "-loop",
                "1",
                "-framerate",
                "30",
                "-t",
                "2.400000",
                "-i",
                "img_01.png",
                "-loop",
                "1",
                "-framerate",
                "30",
                "-t",
                "2.000000",
                "-i",
                "img_02.png",
                "-i",
                "audio.mp3",
                "-filter_complex",
                "[0:v]null[vout]",
                "-map",
                "[vout]",
                "-map",
                "2:a",
                "-t",
                "4.000000",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "18",
                "-r",
                "30",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                "out.mp4"
            ]
        )

    def test_auxiliary_inputs_keep_overlay_then_visual_effect_order(
        self
    ):
        with tempfile.TemporaryDirectory() as tmp:
            overlay = Path(tmp) / "overlay.mov"
            effect = Path(tmp) / "effect.mov"
            overlay.touch()
            effect.touch()

            command = self.build_command(
                overlay_inputs=(
                    overlay,
                ),
                visual_effect_inputs=(
                    effect,
                )
            )

        audio_input = command.index(
            "audio.mp3"
        )
        overlay_input = command.index(
            str(
                overlay
            )
        )
        effect_input = command.index(
            str(
                effect
            )
        )

        self.assertLess(
            audio_input,
            overlay_input
        )
        self.assertLess(
            overlay_input,
            effect_input
        )
        self.assertEqual(
            command[
                overlay_input - 3:overlay_input + 1
            ],
            [
                "-stream_loop",
                "-1",
                "-i",
                str(
                    overlay
                )
            ]
        )
        self.assertEqual(
            command[
                effect_input - 3:effect_input + 1
            ],
            [
                "-stream_loop",
                "-1",
                "-i",
                str(
                    effect
                )
            ]
        )
        self.assertIn(
            "2:a",
            command
        )

    def test_video_clip_inputs_are_not_file_looped_or_image_looped(
        self
    ):
        command = self.build_command(
            images=[
                Path("scene_001.mp4"),
                Path("scene_002.mp4")
            ],
            media_types=(
                "video",
                "video",
            )
        )

        self.assertEqual(
            command[
                2:4
            ],
            [
                "-i",
                "scene_001.mp4"
            ]
        )
        self.assertEqual(
            command[
                4:6
            ],
            [
                "-i",
                "scene_002.mp4"
            ]
        )
        self.assertNotIn(
            "-framerate",
            command[
                2:6
            ]
        )
        self.assertNotIn(
            "-stream_loop",
            command[
                2:6
            ]
        )

    def test_loop_file_false_omits_stream_loop_for_that_layer(
        self
    ):
        with tempfile.TemporaryDirectory() as tmp:
            overlay = Path(tmp) / "overlay.mov"
            effect = Path(tmp) / "effect.mov"
            overlay.touch()
            effect.touch()

            command = self.build_command(
                overlay_inputs=(
                    overlay,
                ),
                visual_effect_inputs=(
                    effect,
                ),
                overlay_loop_file=False,
                visual_effect_loop_file=True
            )

        overlay_input = command.index(
            str(
                overlay
            )
        )
        effect_input = command.index(
            str(
                effect
            )
        )

        self.assertEqual(
            command[
                overlay_input - 1:overlay_input + 1
            ],
            [
                "-i",
                str(
                    overlay
                )
            ]
        )
        self.assertEqual(
            command[
                effect_input - 3:effect_input + 1
            ],
            [
                "-stream_loop",
                "-1",
                "-i",
                str(
                    effect
                )
            ]
        )

    def test_plan_builder_rejects_empty_images_with_existing_message(
        self
    ):
        with self.assertRaisesRegex(
            ValueError,
            "No hay im"
        ):
            CommandPlanBuilder().build(
                images=[],
                audio_path=Path("audio.mp3"),
                output_path=Path("out.mp4"),
                filter_complex="[vout]",
                codec="libx264",
                preset="medium",
                crf=18,
                fps=30,
                pixel_format="yuv420p",
                audio_codec="aac",
                audio_bitrate="192k",
                movflags="+faststart",
                audio_duration=4.0,
                transition_duration=0.4
            )

    def test_plan_builder_preserves_filter_complex_and_audio_index(
        self
    ):
        plan = CommandPlanBuilder().build(
            images=[
                Path("a.png"),
                Path("b.png"),
                Path("c.png")
            ],
            audio_path=Path("audio.mp3"),
            output_path=Path("out.mp4"),
            filter_complex="[x][y]blend[vout]",
            codec="libx264",
            preset="slow",
            crf=20,
            fps=24,
            pixel_format="yuv420p",
            audio_codec="aac",
            audio_bitrate="128k",
            movflags="+faststart",
            audio_duration=6.0,
            transition_duration=0.5
        )

        self.assertEqual(
            plan.output_options.filter_complex,
            "[x][y]blend[vout]"
        )
        self.assertEqual(
            plan.output_options.audio_index,
            3
        )
        self.assertEqual(
            plan.inputs[0].arguments,
            (
                "-loop",
                "1",
                "-framerate",
                "24",
                "-t",
                "2.500000",
                "-i",
                "a.png"
            )
        )
        self.assertEqual(
            plan.inputs[2].arguments,
            (
                "-loop",
                "1",
                "-framerate",
                "24",
                "-t",
                "2.000000",
                "-i",
                "c.png"
            )
        )

    def test_plan_builder_rejects_mismatched_media_types(self):
        with self.assertRaisesRegex(
            ValueError,
            "tipos de media"
        ):
            CommandPlanBuilder().build(
                images=[
                    Path("a.mp4"),
                    Path("b.mp4")
                ],
                media_types=(
                    "video",
                ),
                audio_path=Path("audio.mp3"),
                output_path=Path("out.mp4"),
                filter_complex="[vout]",
                codec="libx264",
                preset="medium",
                crf=18,
                fps=30,
                pixel_format="yuv420p",
                audio_codec="aac",
                audio_bitrate="192k",
                movflags="+faststart",
                audio_duration=4.0,
                transition_duration=0.4
            )


if __name__ == "__main__":
    unittest.main()
