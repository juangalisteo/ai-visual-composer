import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import main
from app.core.start import ejecutar_studio_montaje
from app.modules.studio import (
    StudioInputPreparationService,
    StudioMontageError,
    StudioMontagePlanningService,
    StudioMontageResult,
    StudioMontageService,
)
from app.shared.media_probe import MediaInfo, MediaProbe
from app.shared.profile_identity import ProfileKey
from app.shared.operational_error import OperationalError


class StudioMontagePhase2Test(unittest.TestCase):

    def setUp(self):
        self.profile_key = ProfileKey.for_component("studio", "instagram")
        self.input_profile = SimpleNamespace(video_extensions=(".mp4",))
        self.output_profile = SimpleNamespace(
            width=320,
            height=180,
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
            max_duration_difference=0.2,
            transition_duration=0.50,
        )

    @staticmethod
    def _info(**overrides):
        values = {
            "duration": 1.5,
            "width": 320,
            "height": 180,
            "fps": 24.0,
            "pixel_format": "yuv420p",
            "video_codec": "h264",
            "audio_codec": "aac",
            "audio_sample_rate": 48000,
            "audio_channels": 2,
            "audio_channel_layout": "stereo",
            "nominal_fps": 24.0,
            "time_base": "1/12288",
            "sample_aspect_ratio": "1:1",
        }
        values.update(overrides)
        return MediaInfo(**values)

    def _plan(self, root, names=("A.mp4", "B.mp4", "C.mp4"), order="1 3 2"):
        directory = root / "montaje_videos"
        directory.mkdir()
        for name in names:
            (directory / name).write_bytes(f"source:{name}".encode("ascii"))
        planner = StudioMontagePlanningService(
            StudioInputPreparationService(root)
        )
        candidates = planner.discover(self.input_profile)
        return planner.create_plan(
            profile_key=self.profile_key,
            transitions_enabled=False,
            clips=planner.parse_order(order, candidates),
        )

    def _service(self, infos, generated_info=None, validator=None, runner=None):
        probe = Mock()
        probe.inspect.side_effect = tuple(infos) + (
            generated_info or infos[0],
        )
        use_default_runner = runner is None
        runner = runner or Mock()

        def write_concat(command):
            if command[:2] == ["ffmpeg", "-y"]:
                Path(command[-1]).write_bytes(b"mounted")
            return SimpleNamespace(stderr="")

        if use_default_runner:
            runner.run.side_effect = write_concat
        if validator is None:
            validator = Mock()
            validator.validate.return_value = sum(info.duration for info in infos)
        return StudioMontageService(
            probe=probe,
            runner=runner,
            validator=validator,
        ), probe, runner, validator

    def test_plan_order_is_preserved_in_manifest_and_partial_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = self._plan(root)
            infos = (self._info(), self._info(), self._info())
            service, _, _, _ = self._service(infos)
            captured = {}
            original_writer = service.write_concat_manifest

            def capture(manifest_path, sources):
                captured["sources"] = tuple(sources)
                original_writer(manifest_path, sources)
                captured["content"] = Path(manifest_path).read_text(
                    encoding="utf-8"
                )

            service.write_concat_manifest = capture
            output_path = root / "output" / "montaje.mp4"
            result = service.compose(plan, output_path, self.output_profile)

            self.assertEqual(("A.mp4", "C.mp4", "B.mp4"), tuple(
                path.name for path in captured["sources"]
            ))
            self.assertLess(
                captured["content"].index("A.mp4"),
                captured["content"].index("C.mp4"),
            )
            self.assertLess(
                captured["content"].index("C.mp4"),
                captured["content"].index("B.mp4"),
            )
            self.assertEqual(3, result.clip_count)
            self.assertEqual(4.5, result.expected_duration)
            self.assertTrue(output_path.is_file())
            self.assertFalse(any(root.glob("**/*.ffconcat")))

    def test_manifest_escapes_paths_with_spaces_without_touching_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = self._plan(
                root,
                names=("A one.mp4", "B two.mp4"),
                order="2 1",
            )
            hashes = {
                clip.path: hashlib.sha256(clip.path.read_bytes()).digest()
                for clip in plan.clips
            }
            service, _, _, _ = self._service((self._info(), self._info()))
            captured = {}
            original_writer = service.write_concat_manifest

            def capture(manifest_path, sources):
                original_writer(manifest_path, sources)
                captured["content"] = Path(manifest_path).read_text(
                    encoding="utf-8"
                )

            service.write_concat_manifest = capture
            service.compose(plan, root / "out.mp4", self.output_profile)

            self.assertIn("B two.mp4", captured["content"])
            self.assertIn("A one.mp4", captured["content"])
            for path, digest in hashes.items():
                self.assertEqual(digest, hashlib.sha256(path.read_bytes()).digest())

    def test_each_required_technical_difference_requires_normalization(self):
        cases = (
            ("width", 640, "resolucion"),
            ("nominal_fps", 30.0, "FPS nominal"),
            ("video_codec", "hevc", "codec de video"),
            ("pixel_format", "yuv444p", "pixel format"),
            ("sample_aspect_ratio", "4:3", "SAR"),
            ("time_base", "1/90000", "time_base"),
            ("audio_codec", "mp3", "codec de audio"),
            ("audio_sample_rate", 44100, "sample rate de audio"),
            ("audio_channels", 1, "canales de audio"),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = self._plan(root, names=("A.mp4", "B.mp4"), order="1 2")
            for field, value, label in cases:
                with self.subTest(field=field):
                    service, _, _, _ = self._service(
                        (self._info(), self._info(**{field: value}))
                    )
                    contract = service._build_contract(
                        ((plan.clips[0], self._info()),),
                        self.output_profile,
                    )
                    self.assertTrue(
                        service._requires_normalization(
                            self._info(**{field: value}),
                            contract,
                        ),
                        label,
                    )

    def test_clip_without_audio_requires_normalization(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = self._plan(root, names=("A.mp4", "B.mp4"), order="1 2")
            no_audio = self._info(
                audio_codec=None,
                audio_sample_rate=None,
                audio_channels=None,
            )
            service, _, _, _ = self._service((self._info(), no_audio))
            contract = service._build_contract(
                ((plan.clips[0], self._info()),),
                self.output_profile,
            )
            self.assertTrue(service._requires_normalization(no_audio, contract))

    def test_corrupt_or_incomplete_clip_metadata_fails_before_concat(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = self._plan(root, names=("A.mp4", "B.mp4"), order="1 2")
            for probe_result, message in (
                (RuntimeError("bad media"), "No se pudo inspeccionar"),
                (self._info(width=None), "Metadata de video insuficiente"),
            ):
                with self.subTest(probe_result=probe_result):
                    probe = Mock()
                    if isinstance(probe_result, BaseException):
                        probe.inspect.side_effect = probe_result
                    else:
                        probe.inspect.return_value = probe_result
                    runner = Mock()
                    service = StudioMontageService(
                        probe=probe,
                        runner=runner,
                        validator=Mock(),
                    )
                    with self.assertRaisesRegex(StudioMontageError, message):
                        service.compose(
                            plan,
                            root / "out.mp4",
                            self.output_profile,
                        )
                    runner.run.assert_not_called()

    def test_concat_or_validation_failure_never_promotes_final_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = self._plan(root, names=("A.mp4", "B.mp4"), order="1 2")
            output_path = root / "out.mp4"
            for stage in ("concat", "validation"):
                with self.subTest(stage=stage):
                    runner = Mock()
                    validator = Mock()
                    if stage == "concat":
                        runner.run.side_effect = subprocess.CalledProcessError(
                            1, ["ffmpeg"]
                        )
                    else:
                        def write(command):
                            if command[:2] == ["ffmpeg", "-y"]:
                                Path(command[-1]).write_bytes(b"invalid")
                        runner.run.side_effect = write
                        validator.validate.side_effect = RuntimeError("invalid")
                    service, _, _, _ = self._service(
                        (self._info(), self._info()),
                        runner=runner,
                        validator=validator,
                    )
                    if stage == "concat":
                        with self.assertRaises(OperationalError) as caught:
                            service.compose(plan, output_path, self.output_profile)
                        self.assertEqual("FFMPEG", caught.exception.context.family)
                        self.assertEqual("STUDIO/montaje_videos", caught.exception.context.operation)
                    else:
                        with self.assertRaises(StudioMontageError):
                            service.compose(plan, output_path, self.output_profile)
                    self.assertFalse(output_path.exists())

    def test_output_time_base_remux_change_is_validated_and_promoted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = self._plan(root, names=("A.mp4", "B.mp4"), order="2 1")
            source_info = self._info(time_base="1/30")
            remuxed_info = self._info(time_base="1/15360")
            service, _, _, _ = self._service(
                (source_info, source_info),
                generated_info=remuxed_info,
            )
            output_path = root / "out.mp4"

            result = service.compose(plan, output_path, self.output_profile)
            self.assertEqual(output_path, result.output_path)
            self.assertTrue(output_path.is_file())

    def test_output_contract_keeps_other_stream_checks_and_reports_them(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = self._plan(root, names=("A.mp4", "B.mp4"), order="1 2")
            source_info = self._info(time_base="1/30")
            invalid_output = self._info(
                time_base="1/15360",
                sample_aspect_ratio="4:3",
            )
            service, _, _, _ = self._service(
                (source_info, source_info),
                generated_info=invalid_output,
            )

            with self.assertRaisesRegex(
                StudioMontageError,
                "Comprobacion: .*SAR",
            ):
                service.compose(plan, root / "out.mp4", self.output_profile)

    def test_montage_summary_uses_real_result_stages_and_global_clock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = self._plan(root, names=("A.mp4", "B.mp4"), order="1 2")
            result = StudioMontageResult(
                output_path=root / "out.mp4",
                command=("ffmpeg",),
                expected_duration=1.5,
                generated_duration=1.5,
                clip_count=1,
                preparation_duration=0.4,
                montage_duration=0.6,
                normalization_duration=0.2,
                normalized_clip_count=1,
            )
            options = {
                "project_name": "montaje",
                "profile_id": "studio_instagram",
                "profile_platform": "instagram",
                "studio_montage_plan": plan,
            }
            with patch("app.managers.pipeline_summary.ProgressLogger.info") as logger:
                main._print_studio_montage_summary(options, result, 1.25)

        rendered = logger.call_args.args[0]
        self.assertIn("MONTAJE DE VIDEOS", rendered)
        self.assertIn("Preparacion clips", rendered)
        self.assertIn("Normalizacion clips", rendered)
        self.assertIn("Normalizados", rendered)
        self.assertIn("Montaje de videos", rendered)
        self.assertIn("1.25 s", rendered)

    def test_montage_summary_omits_normalization_for_fast_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = self._plan(root, names=("A.mp4", "B.mp4"), order="1 2")
            result = StudioMontageResult(
                output_path=root / "out.mp4",
                command=("ffmpeg",),
                expected_duration=1.5,
                generated_duration=1.5,
                clip_count=1,
                preparation_duration=0.4,
                montage_duration=0.6,
            )
            options = {
                "project_name": "montaje",
                "profile_id": "studio_instagram",
                "profile_platform": "instagram",
                "studio_montage_plan": plan,
            }
            with patch("app.managers.pipeline_summary.ProgressLogger.info") as logger:
                main._print_studio_montage_summary(options, result, 9.0)

        rendered = logger.call_args.args[0]
        self.assertIn("Preparacion clips", rendered)
        self.assertNotIn("Normalizacion clips", rendered)
        self.assertIn("Montaje de videos", rendered)
        self.assertIn("9.00 s", rendered)


@unittest.skipUnless(
    shutil.which("ffmpeg") and shutil.which("ffprobe"),
    "FFmpeg y FFprobe son obligatorios para la prueba real de montaje.",
)
class StudioMontagePhase2RealFFmpegTest(unittest.TestCase):

    profile = SimpleNamespace(
        movflags="+faststart",
        max_duration_difference=0.25,
    )

    @staticmethod
    def _source(path, color, frequency):
        command = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c={color}:s=160x90:r=24:d=0.6",
            "-f", "lavfi", "-i", (
                f"sine=frequency={frequency}:sample_rate=48000:duration=0.6"
            ),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "48000", "-ac", "2",
            "-video_track_timescale", "30",
            str(path),
        ]
        subprocess.run(command, capture_output=True, check=True)

    @staticmethod
    def _plan(root, order):
        directory = root / "montaje_videos"
        directory.mkdir()
        StudioMontagePhase2RealFFmpegTest._source(
            directory / "A_red.mp4", "red", 440
        )
        StudioMontagePhase2RealFFmpegTest._source(
            directory / "B_green.mp4", "green", 550
        )
        StudioMontagePhase2RealFFmpegTest._source(
            directory / "C_blue.mp4", "blue", 660
        )
        profile = SimpleNamespace(video_extensions=(".mp4",))
        planner = StudioMontagePlanningService(
            StudioInputPreparationService(root)
        )
        candidates = planner.discover(profile)
        return planner.create_plan(
            ProfileKey.for_component("studio", "instagram"),
            False,
            planner.parse_order(order, candidates),
        )

    @staticmethod
    def _pixel(path, timestamp):
        result = subprocess.run(
            [
                "ffmpeg", "-v", "error", "-ss", str(timestamp),
                "-i", str(path), "-vf", "crop=1:1:80:45,format=rgb24",
                "-frames:v", "1", "-f", "rawvideo", "-",
            ],
            capture_output=True,
            check=True,
        )
        return tuple(result.stdout[:3])

    def test_real_three_compatible_clips_are_stream_copied_in_plan_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = self._plan(root, "3 1 2")
            sources = tuple(clip.path for clip in plan.clips)
            hashes = {
                path: hashlib.sha256(path.read_bytes()).digest()
                for path in sources
            }
            output_path = root / "output" / "montaje.mp4"
            result = StudioMontageService().compose(
                plan,
                output_path,
                self.profile,
            )
            info = MediaProbe.inspect(output_path)
            source_info = MediaProbe.inspect(plan.clips[0].path)

            self.assertEqual("copy", result.command[result.command.index("-c") + 1])
            self.assertNotIn("-filter_complex", result.command)
            self.assertTrue(info.has_audio)
            self.assertEqual("h264", info.video_codec)
            self.assertEqual("aac", info.audio_codec)
            self.assertEqual("1/30", source_info.time_base)
            self.assertNotEqual(source_info.time_base, info.time_base)
            self.assertLessEqual(
                abs(result.generated_duration - result.expected_duration),
                self.profile.max_duration_difference,
            )
            first = self._pixel(output_path, 0.10)
            second = self._pixel(output_path, 0.72)
            third = self._pixel(output_path, 1.34)
            self.assertGreater(first[2], first[0])
            self.assertGreater(first[2], first[1])
            self.assertGreater(second[0], second[1])
            self.assertGreater(second[0], second[2])
            self.assertGreater(third[1], third[0])
            self.assertGreater(third[1], third[2])
            for path, digest in hashes.items():
                self.assertEqual(digest, hashlib.sha256(path.read_bytes()).digest())

    def test_real_two_compatible_clips_decode_with_audio_and_video(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = self._plan(root, "2 1")
            output_path = root / "output" / "montaje.mp4"
            result = StudioMontageService().compose(
                plan,
                output_path,
                self.profile,
            )
            decode = subprocess.run(
                [
                    "ffmpeg", "-v", "error", "-i", str(output_path),
                    "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(0, decode.returncode, decode.stderr)
            self.assertEqual(2, result.clip_count)


if __name__ == "__main__":
    unittest.main()
