import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.modules.studio import (
    StudioInputPreparationService,
    StudioMontagePlanningService,
    StudioMontageService,
)
from app.shared.media_probe import MediaInfo, MediaProbe
from app.shared.profile_identity import OperationalProfileKey


class StudioMontagePhase3ContractTest(unittest.TestCase):

    profile = SimpleNamespace(
        width=160,
        height=90,
        fps=24,
        codec="libx264",
        preset="slow",
        crf=16,
        pixel_format="yuv420p",
        audio_codec="aac",
        audio_bitrate="192k",
        audio_sample_rate=48000,
        audio_channels=2,
        movflags="+faststart",
        max_duration_difference=0.25,
        transition_duration=0.50,
    )

    @staticmethod
    def _info(**overrides):
        values = {
            "duration": 1.0,
            "width": 160,
            "height": 90,
            "fps": 24.0,
            "nominal_fps": 24.0,
            "video_codec": "h264",
            "pixel_format": "yuv420p",
            "sample_aspect_ratio": "1:1",
            "time_base": "1/30",
            "audio_codec": "aac",
            "audio_sample_rate": 48000,
            "audio_channels": 2,
            "audio_channel_layout": "stereo",
        }
        values.update(overrides)
        return MediaInfo(**values)

    def test_missing_sar_is_not_assumed_and_requires_normalization(self):
        service = StudioMontageService()
        contract = service._build_contract(
            ((None, self._info()),),
            self.profile,
        )

        self.assertTrue(
            service._requires_normalization(
                self._info(sample_aspect_ratio=None),
                contract,
            )
        )
        self.assertIsNone(MediaProbe._optional_text("N/A"))

    def test_each_heterogeneous_field_requires_normalization(self):
        service = StudioMontageService()
        contract = service._build_contract(
            ((None, self._info()),),
            self.profile,
        )
        differences = {
            "width": 320,
            "height": 180,
            "nominal_fps": 30.0,
            "video_codec": "mpeg4",
            "pixel_format": "yuv444p",
            "sample_aspect_ratio": "4:3",
            "time_base": "1/90000",
            "audio_codec": "mp3",
            "audio_sample_rate": 44100,
            "audio_channels": 1,
            "audio_channel_layout": "mono",
        }
        for field, value in differences.items():
            with self.subTest(field=field):
                self.assertTrue(
                    service._requires_normalization(
                        self._info(**{field: value}),
                        contract,
                    )
                )

    def test_silent_clip_normalization_builds_profile_audio_silence(self):
        service = StudioMontageService()
        contract = service._build_contract(
            ((None, self._info()),),
            self.profile,
        )
        source = self._info(
            audio_codec=None,
            audio_sample_rate=None,
            audio_channels=None,
            audio_channel_layout=None,
        )
        command = service.build_normalize_command(
            source_path="source.mp4",
            output_path="prepared.mp4",
            source_info=source,
            contract=contract,
            profile=self.profile,
        )

        self.assertIn("anullsrc=r=48000:cl=stereo", command)
        self.assertIn(
            "atrim=duration=1.000000",
            command[command.index("-filter_complex") + 1],
        )
        self.assertIn("-video_track_timescale", command)
        self.assertTrue(service._requires_normalization(source, contract))

    def test_preparation_and_normalization_use_non_overlapping_clocks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_directory = root / "montaje_videos"
            source_directory.mkdir()
            (source_directory / "A.mp4").write_bytes(b"A")
            (source_directory / "B.mp4").write_bytes(b"B")
            planner = StudioMontagePlanningService(
                StudioInputPreparationService(root)
            )
            candidates = planner.discover(
                SimpleNamespace(video_extensions=(".mp4",))
            )
            plan = planner.create_plan(
                OperationalProfileKey("studio", "instagram", "studio_instagram"),
                False,
                planner.parse_order("1 2", candidates),
            )
            source_a = self._info()
            source_b = self._info(width=320)
            normalized_b = self._info()
            probe = Mock()
            probe.inspect.side_effect = (source_a, source_b, normalized_b)
            service = StudioMontageService(
                probe=probe,
                runner=Mock(),
                validator=Mock(),
            )

            with (
                patch(
                    "app.modules.studio.montage.time.perf_counter",
                    side_effect=(0.0, 0.4, 0.5, 2.0),
                ),
                patch("app.modules.studio.montage.ProgressLogger") as progress,
            ):
                prepared, preparation_duration, normalization_duration = (
                    service.prepare(plan, self.profile, root / "temporary")
                )

        self.assertEqual(0.4, preparation_duration)
        self.assertEqual(1.5, normalization_duration)
        self.assertEqual(("A.mp4", "0002_B.normalized.mp4"), tuple(
            prepared_clip.path.name for prepared_clip in prepared
        ))
        self.assertEqual(
            [
                ("PREPARANDO CLIPS",),
                ("NORMALIZANDO CLIPS",),
            ],
            [call.args for call in progress.start.call_args_list],
        )
        self.assertEqual(
            [
                ("CLIPS NORMALIZADOS", 1.5),
                ("CLIPS PREPARADOS", 0.4),
            ],
            [call.args for call in progress.finish.call_args_list],
        )


@unittest.skipUnless(
    shutil.which("ffmpeg") and shutil.which("ffprobe"),
    "FFmpeg y FFprobe son obligatorios para la prueba real de montaje.",
)
class StudioMontagePhase3RealFFmpegTest(unittest.TestCase):

    profile = StudioMontagePhase3ContractTest.profile

    @staticmethod
    def _source(
        path,
        color,
        frequency=440,
        size="160x90",
        fps=24,
        sample_rate=48000,
        sar="1/1",
        with_audio=True,
        time_scale=30,
    ):
        command = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c={color}:s={size}:r={fps}:d=0.6",
        ]
        if with_audio:
            command.extend([
                "-f", "lavfi", "-i",
                f"sine=frequency={frequency}:sample_rate={sample_rate}:duration=0.6",
                "-map", "0:v:0", "-map", "1:a:0",
            ])
        else:
            command.extend(["-map", "0:v:0", "-an"])
        command.extend([
            "-vf", f"setsar={sar}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-video_track_timescale", str(time_scale),
        ])
        if with_audio:
            command.extend(["-c:a", "aac", "-ar", str(sample_rate), "-ac", "2"])
        command.append(str(path))
        subprocess.run(command, capture_output=True, check=True)

    @staticmethod
    def _plan(root, names, order):
        directory = root / "montaje_videos"
        directory.mkdir()
        for name, options in names:
            StudioMontagePhase3RealFFmpegTest._source(
                directory / name,
                **options,
            )
        planner = StudioMontagePlanningService(
            StudioInputPreparationService(root)
        )
        candidates = planner.discover(SimpleNamespace(video_extensions=(".mp4",)))
        return planner.create_plan(
            OperationalProfileKey("studio", "instagram", "studio_instagram"),
            False,
            planner.parse_order(order, candidates),
        )

    def _compose(self, names, order):
        directory = tempfile.TemporaryDirectory()
        root = Path(directory.name)
        plan = self._plan(root, names, order)
        hashes = {
            clip.path: hashlib.sha256(clip.path.read_bytes()).digest()
            for clip in plan.clips
        }
        captured = {}
        service = StudioMontageService()
        original_writer = service.write_concat_manifest

        def capture(manifest_path, sources):
            captured["sources"] = tuple(sources)
            original_writer(manifest_path, sources)

        service.write_concat_manifest = capture
        result = service.compose(
            plan,
            root / "output" / "montaje.mp4",
            self.profile,
        )
        return directory, plan, hashes, captured, result

    def _assert_decodes(self, path):
        result = subprocess.run(
            [
                "ffmpeg", "-v", "error", "-i", str(path),
                "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)

    def test_compatible_clips_keep_the_stream_copy_fast_path(self):
        directory, plan, hashes, captured, result = self._compose(
            (
                ("A_red.mp4", {"color": "red", "frequency": 440}),
                ("B_blue.mp4", {"color": "blue", "frequency": 550}),
            ),
            "2 1",
        )
        try:
            self.assertEqual(0, result.normalized_clip_count)
            self.assertIsNone(result.normalization_duration)
            self.assertIn("-c", result.command)
            self.assertEqual("copy", result.command[result.command.index("-c") + 1])
            self.assertEqual(
                ("B_blue.mp4", "A_red.mp4"),
                tuple(path.name for path in captured["sources"]),
            )
            self._assert_decodes(result.output_path)
            self.assertFalse(any(
                path.exists()
                for path in captured["sources"]
                if path.name.endswith(".normalized.mp4")
            ))
            for path, digest in hashes.items():
                self.assertEqual(digest, hashlib.sha256(path.read_bytes()).digest())
        finally:
            directory.cleanup()

    def test_heterogeneous_video_and_audio_normalizes_only_needed_clip(self):
        directory, plan, hashes, captured, result = self._compose(
            (
                ("A_reference.mp4", {"color": "red", "frequency": 440}),
                (
                    "B_heterogeneous.mp4",
                    {
                        "color": "blue",
                        "frequency": 550,
                        "size": "120x90",
                        "fps": 30,
                        "sample_rate": 44100,
                        "sar": "4/3",
                        "time_scale": 90000,
                    },
                ),
            ),
            "1 2",
        )
        try:
            self.assertEqual(1, result.normalized_clip_count)
            self.assertIsNotNone(result.normalization_duration)
            self.assertEqual("A_reference.mp4", captured["sources"][0].name)
            self.assertTrue(
                captured["sources"][1].name.endswith(
                    "B_heterogeneous.normalized.mp4"
                )
            )
            info = MediaProbe.inspect(result.output_path)
            self.assertEqual((160, 90), (info.width, info.height))
            self.assertEqual(
                MediaProbe.inspect(plan.clips[0].path).nominal_fps,
                info.nominal_fps,
            )
            self.assertEqual("h264", info.video_codec)
            self.assertEqual("aac", info.audio_codec)
            self.assertEqual(48000, info.audio_sample_rate)
            self.assertEqual(2, info.audio_channels)
            self._assert_decodes(result.output_path)
            for path, digest in hashes.items():
                self.assertEqual(digest, hashlib.sha256(path.read_bytes()).digest())
        finally:
            directory.cleanup()

    def test_silent_clip_receives_timed_silence_without_changing_source(self):
        directory, plan, hashes, captured, result = self._compose(
            (
                ("A_reference.mp4", {"color": "red", "frequency": 440}),
                (
                    "B_silent.mp4",
                    {"color": "green", "with_audio": False},
                ),
            ),
            "1 2",
        )
        try:
            self.assertEqual(1, result.normalized_clip_count)
            self.assertEqual("A_reference.mp4", captured["sources"][0].name)
            self.assertTrue(
                captured["sources"][1].name.endswith(
                    "B_silent.normalized.mp4"
                )
            )
            self.assertTrue(MediaProbe.inspect(result.output_path).has_audio)
            self._assert_decodes(result.output_path)
            self.assertFalse(any(
                path.exists()
                for path in captured["sources"]
                if path.name.endswith(".normalized.mp4")
            ))
            for path, digest in hashes.items():
                self.assertEqual(digest, hashlib.sha256(path.read_bytes()).digest())
        finally:
            directory.cleanup()


if __name__ == "__main__":
    unittest.main()
