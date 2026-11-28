import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

from app.core.pipeline_telemetry import (
    PipelineTelemetry,
    PipelineTelemetryArtifacts,
)
from app.managers.pipeline_summary import PipelineSummary


class _Clock:

    def __init__(self, *values):
        self._values = iter(values)

    def __call__(self):
        return next(self._values)


class _MediaProbe:

    def __init__(self, duration):
        self.duration = duration
        self.paths = []

    def get_duration(self, path):
        self.paths.append(Path(path))
        return self.duration


class PipelineTelemetryTest(unittest.TestCase):

    def test_artifact_paths_are_immutable_technical_paths(self):
        artifacts = PipelineTelemetryArtifacts(
            storyboard_path="storyboard.json",
            images_manifest_path="images_manifest.json",
            final_audio_path="audio_final.mp3",
            audio_path="voz.mp3",
        )

        self.assertEqual(Path("storyboard.json"), artifacts.storyboard_path)
        with self.assertRaises(FrozenInstanceError):
            artifacts.audio_path = Path("other.mp3")

    def test_measure_stage_returns_result_and_elapsed_seconds(self):
        telemetry = PipelineTelemetry(
            clock=_Clock(10.0, 12.5)
        )

        result, elapsed = telemetry.measure_stage(
            lambda value: value * 2,
            21,
        )

        self.assertEqual(42, result)
        self.assertEqual(2.5, elapsed)

    def test_measure_stage_preserves_function_exception(self):
        telemetry = PipelineTelemetry(
            clock=_Clock(10.0)
        )

        with self.assertRaisesRegex(ValueError, "original"):
            telemetry.measure_stage(
                self._raise_original_error
            )

    def test_complete_orders_known_stages_and_never_lowers_total(self):
        summary = PipelineSummary("telemetry")
        summary.set_total_time(10.0)
        telemetry = PipelineTelemetry(
            clock=_Clock(5.0)
        )

        with patch.object(summary, "print") as print_summary:
            telemetry.complete(
                summary=summary,
                stage_times={
                    "Voz": 2.0,
                    "Guion": 1.0,
                    "Etapa desconocida": 4.0,
                },
                pipeline_start=1.0,
            )

        self.assertEqual(
            ("Guion", "Voz"),
            tuple(summary.stage_times),
        )
        self.assertEqual(10.0, summary.total_time())
        print_summary.assert_called_once_with()

    def test_complete_enriches_metrics_with_final_audio_preference(self):
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            storyboard_path = directory_path / "storyboard.json"
            images_manifest_path = directory_path / "images_manifest.json"
            final_audio_path = directory_path / "audio_final.mp3"
            audio_path = directory_path / "voz.mp3"
            storyboard_path.write_text(
                json.dumps([{"scene": 1}]),
                encoding="utf-8",
            )
            images_manifest_path.write_text(
                json.dumps([{"image": "scene_001.png"}]),
                encoding="utf-8",
            )
            final_audio_path.touch()
            audio_path.touch()
            media_probe = _MediaProbe(12.5)
            telemetry = PipelineTelemetry(
                clock=_Clock(9.0),
                media_probe=media_probe,
            )
            summary = PipelineSummary("telemetry")

            with patch.object(summary, "print") as print_summary:
                telemetry.complete(
                    summary=summary,
                    stage_times={"Audio": 2.0},
                    pipeline_start=1.0,
                    artifacts=PipelineTelemetryArtifacts(
                        storyboard_path=storyboard_path,
                        images_manifest_path=images_manifest_path,
                        final_audio_path=final_audio_path,
                        audio_path=audio_path,
                    ),
                )

        self.assertEqual(1, summary.scene_count)
        self.assertEqual(1, summary.image_count)
        self.assertEqual(12.5, summary.media_duration)
        self.assertEqual([final_audio_path], media_probe.paths)
        self.assertEqual(8.0, summary.total_time())
        print_summary.assert_called_once_with()

    def test_complete_without_artifacts_preserves_direct_i2v_summary(self):
        summary = PipelineSummary("telemetry")
        summary.set_media_duration(4.0)
        telemetry = PipelineTelemetry(
            clock=_Clock(7.0)
        )

        with patch.object(summary, "print") as print_summary:
            telemetry.complete(
                summary=summary,
                stage_times={"Clips de vídeo": 3.0},
                pipeline_start=1.0,
            )

        self.assertEqual(0, summary.scene_count)
        self.assertEqual(0, summary.image_count)
        self.assertEqual(4.0, summary.media_duration)
        self.assertEqual(("Clips de vídeo",), tuple(summary.stage_times))
        self.assertEqual(6.0, summary.total_time())
        print_summary.assert_called_once_with()

    def test_summary_shows_real_seconds_per_image_with_storyboard(self):
        summary = PipelineSummary("telemetry")
        summary.set_scene_count(3)
        summary.set_image_count(3)
        summary.set_media_duration(34.0)

        rendered = summary.render()

        self.assertIn("Segundos por imagen", rendered)
        self.assertIn("11,33", rendered)
        self.assertIn("Duración", rendered)
        self.assertIn("Imágenes", rendered)

    def test_summary_omits_seconds_per_image_without_scenes(self):
        summary = PipelineSummary("telemetry")
        summary.set_media_duration(34.0)

        rendered = summary.render()

        self.assertNotIn("Segundos por imagen", rendered)

    def test_summary_seconds_per_image_is_unavailable_without_metrics(self):
        for scene_count, duration in ((None, 34.0), (3, None)):
            with self.subTest(scene_count=scene_count, duration=duration):
                summary = PipelineSummary("telemetry")
                summary.set_scene_count(scene_count)
                summary.set_media_duration(duration)

                rendered = summary.render()

                line = next(
                    line
                    for line in rendered.splitlines()
                    if line.startswith("Segundos por imagen")
                )
                self.assertTrue(line.endswith(" No disponible"))

    def test_summary_without_visual_metrics_hides_storyboard_metrics(self):
        summary = PipelineSummary(
            "telemetry",
            include_visual_metrics=False,
        )
        summary.set_scene_count(3)
        summary.set_image_count(3)
        summary.set_media_duration(34.0)

        rendered = summary.render()

        for label in (
            "Escenas",
            "Imágenes",
            "Duración",
            "Segundos por imagen",
        ):
            self.assertNotIn(label, rendered)

    def test_summary_shows_media_duration_without_visual_metrics(self):
        summary = PipelineSummary(
            "telemetry",
            include_visual_metrics=False,
            include_media_duration=True,
        )
        summary.set_media_duration(34.0)

        rendered = summary.render()

        self.assertIn("Duración", rendered)
        for label in (
            "Escenas",
            "Imágenes",
            "Segundos por imagen",
        ):
            self.assertNotIn(label, rendered)

    def test_summary_omits_images_when_none_were_generated(self):
        summary = PipelineSummary("telemetry")
        summary.set_scene_count(3)
        summary.set_image_count(0)
        summary.set_media_duration(34.0)

        rendered = summary.render()

        self.assertNotIn("Imágenes", rendered)
        for label in (
            "Escenas",
            "Duración",
            "Segundos por imagen",
        ):
            self.assertIn(label, rendered)

    @staticmethod
    def _raise_original_error():
        raise ValueError("original")


if __name__ == "__main__":
    unittest.main()
