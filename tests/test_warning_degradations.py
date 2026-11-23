import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.pipeline_telemetry import (
    PipelineTelemetry,
    PipelineTelemetryArtifacts,
)
from app.managers.pipeline_summary import PipelineSummary
from app.shared.operational_error import create_operational_error
from app.shared.operation_warnings import OperationWarnings
from app.shared.progress_logger import ProgressLogger


class _AsciiStdout:
    encoding = "ascii"

    def __init__(self):
        self.buffer = io.StringIO()

    def write(self, value):
        return self.buffer.write(value)

    def flush(self):
        return None

    def getvalue(self):
        return self.buffer.getvalue()


class WarningDegradationsTest(unittest.TestCase):

    def test_failed_json_metric_is_unavailable_and_warned(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.json"
            manifest.write_text("{broken", encoding="utf-8")
            summary = PipelineSummary("warnings")

            count = PipelineTelemetry()._count_json_items(
                manifest,
                warnings=summary.warnings,
                metric_name="escenas",
            )

        summary.set_scene_count(count)
        rendered = summary.render()
        self.assertIsNone(count)
        self.assertIn("No disponible", rendered)
        self.assertIn("AVISO", rendered)
        self.assertEqual(1, len(summary.warnings))

    def test_real_zero_metric_remains_zero_without_warning(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.json"
            manifest.write_text(json.dumps([]), encoding="utf-8")
            warnings = OperationWarnings()

            count = PipelineTelemetry()._count_json_items(
                manifest,
                warnings=warnings,
                metric_name="im\u00e1genes",
            )

        self.assertEqual(0, count)
        self.assertEqual(0, len(warnings))

    def test_failed_duration_metric_is_not_rendered_as_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            media_path = Path(directory) / "audio.mp3"
            media_path.touch()
            summary = PipelineSummary("warnings")
            with patch(
                "app.core.pipeline_telemetry.MediaProbe.get_duration",
                side_effect=RuntimeError("probe unavailable"),
            ):
                duration = PipelineTelemetry()._resolve_media_duration(
                    PipelineTelemetryArtifacts(
                        storyboard_path=media_path,
                        images_manifest_path=media_path,
                        final_audio_path=media_path,
                        audio_path=media_path,
                    ),
                    warnings=summary.warnings,
                )

        summary.set_media_duration(duration)
        rendered = summary.render()
        self.assertIsNone(duration)
        self.assertIn("No disponible", rendered)
        self.assertEqual(1, len(summary.warnings))

    def test_unicode_fallback_warns_once_per_operation(self):
        warnings = OperationWarnings()
        stream = _AsciiStdout()

        with patch("sys.stdout", stream):
            ProgressLogger.info(
                "Informaci\u00f3n visible",
                warnings=warnings,
                operation="Resumen del pipeline",
            )
            ProgressLogger.info(
                "Informaci\u00f3n visible",
                warnings=warnings,
                operation="Resumen del pipeline",
            )

        self.assertIn("\\x", stream.getvalue())
        self.assertEqual(1, len(warnings))
        warning = warnings.snapshot()[0]
        self.assertEqual("DEGRADATION", warning.family)
        self.assertEqual("progress_logger", warning.technical_metadata["source"])

    def test_fatal_errors_remain_operational_errors(self):
        error = create_operational_error(
            family="FILESYSTEM",
            user_message="No se pudo leer el recurso.",
            recommended_action="Revisa la ruta.",
            operation="Lectura",
        )

        self.assertEqual("FILESYSTEM", error.context.family)
        self.assertFalse(hasattr(error, "warning"))


if __name__ == "__main__":
    unittest.main()
