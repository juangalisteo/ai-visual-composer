import contextlib
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from app.modules.video_component import clip_batch
from app.modules.video_component.profile_parameters import (
    video_progress_interval_seconds,
)
from app.shared.profile_identity import OperationalProfileKey, ProfileComponent
from app.shared.profile_resolver import ProfileResolver
from app.shared.progress_heartbeat import ProgressHeartbeat, format_elapsed


class FormatElapsedTest(unittest.TestCase):

    def test_whole_seconds_in_spanish_terminal_style(self):
        cases = (
            (0, "0 s"),
            (0.4, "0 s"),
            (29.6, "30 s"),
            (45, "45 s"),
            (60, "1 min"),
            (90, "1 min 30 s"),
            (125.2, "2 min 5 s"),
            (3600, "1 h 0 min"),
            (3725, "1 h 2 min 5 s"),
            (-3, "0 s"),
        )
        for seconds, expected in cases:
            with self.subTest(seconds=seconds):
                self.assertEqual(expected, format_elapsed(seconds))


class ProgressHeartbeatTest(unittest.TestCase):

    def test_prints_label_and_elapsed_on_each_interval(self):
        now = [100.0]
        lines = []
        ticks = iter((False, False, False, True))

        def wait(interval):
            self.assertEqual(30, interval)
            now[0] += 30
            return next(ticks)

        heartbeat = ProgressHeartbeat(
            "Clip 2/3",
            30,
            clock=lambda: now[0],
            emit=lines.append,
            wait=wait,
        )
        heartbeat._start = 100.0
        heartbeat.run()

        self.assertEqual(
            ["Clip 2/3 · 30 s", "Clip 2/3 · 1 min", "Clip 2/3 · 1 min 30 s"],
            lines,
        )

    def test_no_line_after_the_step_ends(self):
        lines = []
        heartbeat = ProgressHeartbeat("Clip 1/1", 30, emit=lines.append)

        def wait(interval):
            heartbeat._stop.set()
            return False

        heartbeat._wait = wait
        heartbeat._start = 0.0
        heartbeat.run()

        self.assertEqual([], lines)

    def test_undeclared_interval_starts_no_thread(self):
        lines = []
        with patch("app.shared.progress_heartbeat.threading.Thread") as thread:
            with ProgressHeartbeat("Clip 1/1", None, emit=lines.append):
                pass

        thread.assert_not_called()
        self.assertEqual([], lines)

    def test_thread_runs_during_the_step_and_is_joined_at_exit(self):
        lines = []
        emitted = threading.Event()

        def emit(line):
            lines.append(line)
            emitted.set()

        with ProgressHeartbeat("Clip 1/1", 0.01, emit=emit) as heartbeat:
            self.assertTrue(emitted.wait(5))
        count = len(lines)

        self.assertFalse(heartbeat._thread.is_alive())
        self.assertTrue(all(line.startswith("Clip 1/1 · ") for line in lines))
        self.assertEqual(count, len(lines))

    def test_step_errors_propagate_and_stop_the_thread(self):
        with self.assertRaises(RuntimeError):
            with ProgressHeartbeat("Clip 1/1", 60, emit=lambda line: None) as heartbeat:
                raise RuntimeError("fallo de WAN")

        self.assertFalse(heartbeat._thread.is_alive())


class VideoProgressIntervalTest(unittest.TestCase):

    def test_reads_the_declared_interval(self):
        profile = {"video_component": {"progress_interval_seconds": 30}}
        self.assertEqual(30.0, video_progress_interval_seconds(profile))
        self.assertIsNone(video_progress_interval_seconds({"video_component": {}}))

    def test_rejects_invalid_intervals(self):
        for value in (0, -5, True, "30", []):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    video_progress_interval_seconds(
                        {"video_component": {"progress_interval_seconds": value}}
                    )

    def test_official_wan_documents_declare_the_interval(self):
        resolver = ProfileResolver()
        for profile_format, profile_id in (
            ("vertical", "video_vertical"),
            ("horizontal", "video_horizontal"),
        ):
            with self.subTest(profile_format=profile_format):
                document = resolver.load_video_component(
                    OperationalProfileKey(
                        ProfileComponent.VIDEO,
                        profile_format,
                        profile_id,
                    )
                )
                self.assertEqual(30.0, video_progress_interval_seconds(document))


class _RecordingHeartbeat:
    instances = []

    def __init__(self, label, interval_seconds):
        self.label = label
        self.interval_seconds = interval_seconds
        self.inside = False
        _RecordingHeartbeat.instances.append(self)

    def __enter__(self):
        self.inside = True
        return self

    def __exit__(self, *exc):
        self.inside = False
        return False

    def elapsed(self):
        return 92.4


class _Project:
    def __init__(self, base_path):
        self.base_path = Path(base_path)


class _Result:
    def __init__(self, output_clip, source_image):
        self.output_clip = Path(output_clip)
        self.source_image = Path(source_image)
        self.manifest_path = None
        for name in (
            "prompt_id", "backend", "model", "workflow", "seed", "frames", "fps",
            "generation_width", "generation_height", "steps", "cfg", "sampler",
            "scheduler", "profile_name", "duration_seconds", "fingerprint",
            "positive_prompt", "negative_prompt", "motion_summary",
            "camera_motion", "motion_intensity", "stability", "temporal_rhythm",
            "motion_level", "preservation_constraints", "avoidance_constraints",
            "source_trace",
        ):
            setattr(self, name, None)


class _Builder:
    def __init__(self):
        self.inside_heartbeat = []

    def generate_clip(self, source_path=None, output_dir=None,
                      output_name="clip.mp4", storyboard_scene=None, **overrides):
        self.inside_heartbeat.append(_RecordingHeartbeat.instances[-1].inside)
        output_clip = Path(output_dir) / output_name
        output_clip.write_bytes(b"clip")
        return _Result(output_clip, source_path)


class ClipBatchProgressTest(unittest.TestCase):

    def test_each_wan_clip_reports_its_number_and_time(self):
        _RecordingHeartbeat.instances = []
        profile = {
            "format": "vertical",
            "video_component": {
                "generation": {"width": 448, "height": 800},
                "frames": 49,
                "fps": 12,
                "seed_mode": "fixed",
                "seed": 7,
                "progress_interval_seconds": 45,
                "sampling": {"steps": 2, "cfg": 5.0, "sampler": "uni_pc",
                             "scheduler": "simple"},
            },
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            scenes, images = [], []
            for number in (1, 2):
                image = root / f"scene_{number:03d}.png"
                image.write_bytes(b"png")
                scenes.append({"scene": number, "text": "texto",
                               "visible_subject": "sujeto",
                               "visible_action": "accion",
                               "visible_environment": "laboratorio",
                               "filmable_interpretation": "plano fijo"})
                images.append({"scene": number, "image": str(image)})
            storyboard = root / "storyboard.json"
            storyboard.write_text(json.dumps(scenes), encoding="utf-8")
            manifest = root / "images_manifest.json"
            manifest.write_text(json.dumps(images), encoding="utf-8")
            builder = _Builder()
            output = io.StringIO()

            with patch.object(clip_batch, "load_video_component_parameters",
                              return_value=profile), \
                    patch.object(clip_batch, "ProgressHeartbeat", _RecordingHeartbeat), \
                    patch.object(clip_batch, "_build_video_clip_manifest_entry",
                                 return_value={}), \
                    contextlib.redirect_stdout(output):
                clip_batch.generate_video_clips(
                    storyboard_path=storyboard,
                    images_manifest_path=manifest,
                    project=_Project(root / "project"),
                    video_builder=builder,
                    profile_key="unused",
                )

        lines = output.getvalue().splitlines()
        self.assertIn("GENERANDO CLIPS DE VÍDEO (WAN)...", lines)
        self.assertEqual(
            ["Clip 1/2", "Clip 2/2"],
            [heartbeat.label for heartbeat in _RecordingHeartbeat.instances],
        )
        self.assertEqual(
            [45.0, 45.0],
            [h.interval_seconds for h in _RecordingHeartbeat.instances],
        )
        self.assertEqual([True, True], builder.inside_heartbeat)
        self.assertIn("Clip 1/2 listo · 1 min 32 s", lines)
        self.assertIn("Clip 2/2 listo · 1 min 32 s", lines)


if __name__ == "__main__":
    unittest.main()
