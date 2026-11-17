import io
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from app.controllers.run_controller import RunController
from app.managers.pipeline_summary import PipelineSummary
from app.modules.video.video_validator import VideoValidator
from app.shared.media_probe import MediaProbe
from app.shared.progress_logger import ProgressLogger
from tests.test_menu_helpers import MenuAnswers


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


class ReconfigurableBytesStdout:
    def __init__(self):
        self.encoding = "cp1252"
        self.errors = "strict"
        self.buffer = bytearray()

    def reconfigure(
        self,
        encoding=None,
        errors=None
    ):
        if encoding is not None:
            self.encoding = encoding

        if errors is not None:
            self.errors = errors

    def write(
        self,
        text
    ):
        self.buffer.extend(
            text.encode(
                self.encoding,
                errors=self.errors
            )
        )

    def flush(self):
        pass

    def get_utf8_output(self):
        return bytes(
            self.buffer
        ).decode(
            "utf-8"
        )


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

    def test_run_controller_menus_write_unicode_through_utf8_stdout_boundary(self):
        stream = ReconfigurableBytesStdout()
        controller = RunController()
        answers = MenuAnswers(
            "Vertical 9:16",
            "MODO CONCIENCIA",
            "Modo Conciencia | Palabra única",
            "Aleatoria",
            "Sí",
            screen=stream.get_utf8_output,
        )

        with patch.object(
            sys,
            "stdout",
            stream
        ), patch(
            "builtins.input",
            side_effect=answers.input
        ):
            controller.select_profile("image")
            controller.select_music_category()
            controller.select_overlays_mode()

        output = stream.get_utf8_output()

        self.assertIn(
            "SUBTÍTULOS",
            output
        )
        self.assertIn(
            "ESTILO ESTÁNDAR",
            output
        )
        self.assertIn(
            "MÚSICA",
            output
        )
        self.assertIn(
            "Sí",
            output
        )
        self.assertNotIn(
            "SUBT" + chr(0xFFFD) + "TULOS",
            output
        )
        self.assertNotIn(
            "M" + chr(0xFFFD) + "SICA",
            output
        )

    def test_run_controller_invalid_option_message_uses_utf8_stdout_boundary(self):
        stream = ReconfigurableBytesStdout()
        controller = RunController()

        with patch.object(
            sys,
            "stdout",
            stream
        ), patch(
            "builtins.input",
            side_effect=(
                "",
                "Proyecto"
            )
        ):
            controller.ask_project_name()

        output = stream.get_utf8_output()

        self.assertIn(
            "Opción no válida.",
            output
        )
        self.assertNotIn(
            "Opci" + chr(0xFFFD) + "n",
            output
        )

    def test_pipeline_summary_print_uses_utf8_stdout_boundary(self):
        stream = ReconfigurableBytesStdout()
        summary = PipelineSummary(
            "unicode"
        )
        summary.set_image_count(
            2
        )
        summary.set_media_duration(
            3
        )
        summary.add_stage(
            "Vídeo",
            1.0
        )
        summary.add_stage(
            "Transición 1→2",
            0.5
        )

        with patch.object(
            sys,
            "stdout",
            stream
        ):
            summary.print()

        output = stream.get_utf8_output()

        self.assertIn(
            "Imágenes",
            output
        )
        self.assertIn(
            "Duración",
            output
        )
        self.assertIn(
            "Vídeo",
            output
        )
        self.assertIn(
            "Transición 1→2",
            output
        )
        self.assertNotIn(
            "Im" + chr(0xFFFD) + "genes",
            output
        )
        self.assertNotIn(
            "Duraci" + chr(0xFFFD) + "n",
            output
        )

    def test_run_controller_unicode_output_still_supports_stringio_capture(self):
        stream = io.StringIO()
        controller = RunController()
        answers = MenuAnswers("Sí", screen=stream.getvalue)

        with patch.object(
            sys,
            "stdout",
            stream
        ), patch(
            "builtins.input",
            side_effect=answers.input
        ):
            controller.select_overlays_mode()

        output = stream.getvalue()

        self.assertIn(
            "OVERLAYS",
            output
        )
        self.assertIn(
            "Sí",
            output
        )


if __name__ == "__main__":
    unittest.main()
