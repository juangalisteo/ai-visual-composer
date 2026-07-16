import io
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from app.modules.video.video_validator import VideoValidator
from app.shared.media_probe import MediaProbe
from app.shared.progress_logger import ProgressLogger


class Cp1252Stdout:
    encoding = "cp1252"

    def __init__(self):
        self.output = []

    def write(self, text):
        text.encode(
            self.encoding
        )
        self.output.append(
            text
        )

    def flush(self):
        pass


class TextEncodingQualityTest(unittest.TestCase):

    def setUp(self):
        ProgressLogger._stdout_configured = False
        ProgressLogger._stdout_stream = None

    def tearDown(self):
        ProgressLogger._stdout_configured = False
        ProgressLogger._stdout_stream = None

    def test_progress_logger_prints_spanish_accents_without_mojibake(self):
        stream = io.StringIO()

        with patch.object(
            sys,
            "stdout",
            stream
        ):
            ProgressLogger.info(
                "Duración esperada: 16.82 segundos"
            )

        output = stream.getvalue()

        self.assertIn(
            "Duración esperada",
            output
        )
        self.assertNotIn(
            "Duraci" + "\u00c3",
            output
        )

    def test_progress_logger_handles_windows_stdout_without_reconfigure(self):
        stream = Cp1252Stdout()

        with patch.object(
            sys,
            "stdout",
            stream
        ):
            ProgressLogger.info(
                "Transición 1→2: smoothleft"
            )

        output = "".join(
            stream.output
        )

        self.assertIn(
            "Transición",
            output
        )
        self.assertIn(
            "\\u2192",
            output
        )

    def test_progress_logger_does_not_require_pythonioencoding(self):
        stream = Cp1252Stdout()

        with patch.dict(
            os.environ,
            {},
            clear=True
        ), patch.object(
            sys,
            "stdout",
            stream
        ):
            ProgressLogger.info(
                "Duración esperada: 16.82 segundos"
            )

        output = "".join(
            stream.output
        )

        self.assertIn(
            "Duración esperada",
            output
        )

    def test_video_validator_logs_duration_messages_without_mojibake(self):
        stream = io.StringIO()

        with patch.object(
            MediaProbe,
            "get_duration",
            return_value=16.81
        ), patch.object(
            sys,
            "stdout",
            stream
        ):
            output_file = Path(
                "tests"
            ) / "__init__.py"
            VideoValidator().validate(
                output_path=output_file,
                expected_duration=16.82,
                max_duration_difference=0.5
            )

        output = stream.getvalue()

        self.assertIn(
            "Duración esperada",
            output
        )
        self.assertIn(
            "Duración generada",
            output
        )
        self.assertIn(
            "Diferencia de duración",
            output
        )
        self.assertNotIn(
            "Duraci" + "\u00c3",
            output
        )

    def test_runtime_sources_do_not_contain_mojibake_sequences(self):
        roots = [
            Path("app"),
            Path("tests"),
            Path("docs"),
            Path("README.md"),
            Path("ARCHITECTURE.md"),
            Path("CHANGELOG.md"),
            Path("ROADMAP.md"),
            Path("main.py"),
        ]
        forbidden = [
            "\u00c3",
            "\u00c2",
            "\ufffd",
            "\ufffd",
            "Duraci" + "\u00c3",
        ]

        scanned_files = []

        for root in roots:
            if root.is_dir():
                files = root.rglob(
                    "*"
                )
            else:
                files = [
                    root
                ]

            for file_path in files:
                if (
                    not file_path.is_file()
                    or file_path.suffix.lower()
                    not in {".py", ".md", ".json", ".txt"}
                    or "__pycache__" in file_path.parts
                ):
                    continue

                text = file_path.read_text(
                    encoding="utf-8"
                )
                scanned_files.append(
                    file_path
                )

                for sequence in forbidden:
                    self.assertNotIn(
                        sequence,
                        text,
                        f"{sequence!r} found in {file_path}"
                    )

        self.assertTrue(
            scanned_files
        )


if __name__ == "__main__":
    unittest.main()
