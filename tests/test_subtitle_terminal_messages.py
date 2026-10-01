import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.modules.subtitles.io.subtitle_builder import SubtitleBuilder
from app.modules.subtitles.pipeline.srt_optimizer import SrtOptimizer


class SubtitleTerminalMessagesTest(unittest.TestCase):

    def test_whisper_generation_is_labeled_as_a_temporary_transcript(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audio_path = root / "source.wav"
            output_path = root / "subtitles.srt"
            audio_path.write_bytes(b"audio")

            def write_whisper_artifacts(command, check):
                output_directory = Path(command[command.index("--output_dir") + 1])
                (output_directory / "source.srt").write_text(
                    "1\n00:00:00,000 --> 00:00:01,000\nTemporal\n",
                    encoding="utf-8",
                )

            with patch(
                "app.modules.subtitles.io.subtitle_builder.subprocess.run",
                side_effect=write_whisper_artifacts,
            ), patch(
                "app.modules.subtitles.io.subtitle_builder.ProgressLogger.start"
            ) as start, patch(
                "app.modules.subtitles.io.subtitle_builder.ProgressLogger.finish"
            ) as finish:
                SubtitleBuilder().build(
                    audio_path=audio_path,
                    output_path=output_path,
                )

        start.assert_called_once_with("GENERANDO TRANSCRIPCI\u00d3N TEMPORAL")
        self.assertEqual(
            "TRANSCRIPCI\u00d3N TEMPORAL GENERADA",
            finish.call_args.args[0],
        )

    def test_optimizer_labels_its_output_as_final_subtitles(self):
        cue_policy = {
            "mode": "single_line",
            "max_chars_per_line": 120,
            "min_duration": 1.0,
            "max_duration": 3.0,
            "significant_gap_threshold": 0.35,
            "punctuation": {
                "remove_commas": False,
                "remove_periods": False,
                "remove_colons": False,
                "remove_semicolons": False,
                "remove_question_marks": False,
                "remove_exclamation_marks": False,
                "remove_ellipsis": False,
                "remove_hyphens": False,
                "remove_em_dashes": False,
                "remove_double_quotes": False,
                "remove_single_quotes": False,
                "remove_parentheses": False,
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "source.srt"
            output_path = root / "final.srt"
            input_path.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\nDefinitivo.\n",
                encoding="utf-8",
            )
            project = SimpleNamespace(audio_path=lambda: root / "audio.mp3")
            with patch(
                "app.modules.subtitles.pipeline.srt_optimizer.ProjectManager",
                return_value=project,
            ), patch(
                "app.modules.subtitles.pipeline.srt_optimizer.SubtitleTimingResolver.resolve",
                return_value=None,
            ), patch(
                "app.modules.subtitles.pipeline.srt_optimizer.ProgressLogger.start"
            ) as start, patch(
                "app.modules.subtitles.pipeline.srt_optimizer.ProgressLogger.finish"
            ) as finish:
                SrtOptimizer(
                    subtitle_profile=SimpleNamespace(cue_policy=cue_policy),
                    render_fps=30,
                ).optimize(
                    input_path=input_path,
                    output_path=output_path,
                )

        start.assert_called_once_with("OPTIMIZANDO SRT")
        self.assertEqual(
            "SUBT\u00cdTULOS FINALES GENERADOS",
            finish.call_args.args[0],
        )


if __name__ == "__main__":
    unittest.main()
