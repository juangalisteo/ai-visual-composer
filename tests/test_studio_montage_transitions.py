import hashlib
from dataclasses import replace
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from app.modules.studio import (
    StudioMontageClip,
    StudioMontageInputError,
    StudioMontagePlan,
    StudioMontagePreparedClip,
    StudioMontageService,
)
from app.modules.studio.montage import StudioMontageError
from app.shared.media_probe import MediaInfo
from app.shared.profile_identity import OperationalProfileKey
from app.shared.profile_resolver import ProfileResolver
from app.modules.studio import StudioProfileLoader


STUDIO_PROFILE_IDS = {
    "vertical": "studio_vertical",
    "horizontal": "studio_horizontal",
}


def _load_studio_profile(profile_key):
    operational_key = OperationalProfileKey(
        profile_key.component,
        profile_key.format,
        profile_key.profile_id,
    )
    return StudioProfileLoader().load(
        ProfileResolver().load_operational(operational_key),
        operational_key,
    )


class StudioMontageTransitionsContractTest(unittest.TestCase):

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
    def _info(duration=2.0, **overrides):
        values = {
            "duration": duration,
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
            "video_duration": duration,
        }
        values.update(overrides)
        return MediaInfo(**values)

    def _prepared(self, root, durations):
        prepared = []
        for index, duration in enumerate(durations, start=1):
            path = root / f"clip_{index}.mp4"
            path.write_bytes(b"source")
            clip = StudioMontageClip(index, path, path.name)
            prepared.append(
                StudioMontagePreparedClip(clip, self._info(duration))
            )
        return tuple(prepared)

    def _plan(self, root, count, transitions_enabled=True):
        clips = []
        for index in range(1, count + 1):
            path = root / f"clip_{index}.mp4"
            path.write_bytes(b"source")
            clips.append(StudioMontageClip(index, path, path.name))
        return StudioMontagePlan(
            profile_key=OperationalProfileKey(
                "studio", "vertical", "studio_vertical"
            ),
            transitions_enabled=transitions_enabled,
            clips=tuple(clips),
        )

    def test_four_clips_use_visual_padding_and_sequential_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            prepared = self._prepared(Path(directory), (2.0, 2.0, 2.0, 2.0))
            service = StudioMontageService()
            script = service.build_transition_filter_script(
                prepared,
                self.profile,
            )

        self.assertEqual(3, script.count("xfade=transition=fade"))
        self.assertEqual(3, script.count("tpad=stop_mode=clone:stop_duration=0.500"))
        self.assertNotIn("acrossfade=", script)
        self.assertNotIn("atrim=", script)
        self.assertIn("concat=n=4:v=0:a=1[aout]", script)
        for offset in ("2.000000", "4.000000", "6.000000"):
            self.assertIn(f"offset={offset}", script)
        self.assertIn("[vout]", script)
        self.assertIn("[aout]", script)

    def test_transition_duration_preserves_the_full_content_timeline(self):
        with tempfile.TemporaryDirectory() as directory:
            prepared = self._prepared(Path(directory), (2.0, 3.5, 4.0, 2.5))
            expected = StudioMontageService()._expected_transition_duration(
                prepared,
                self.profile,
            )

        self.assertEqual(12.0, expected)

    def test_profile_duration_controls_filters_offsets_and_expected_duration(self):
        profile = SimpleNamespace(
            **{**vars(self.profile), "transition_duration": 0.30}
        )
        with tempfile.TemporaryDirectory() as directory:
            prepared = self._prepared(Path(directory), (2.0, 2.0))
            service = StudioMontageService()
            script = service.build_transition_filter_script(prepared, profile)
            expected = service._expected_transition_duration(prepared, profile)

        self.assertIn("duration=0.300", script)
        self.assertIn("tpad=stop_mode=clone:stop_duration=0.300", script)
        self.assertNotIn("acrossfade=", script)
        self.assertNotIn("atrim=", script)
        self.assertIn("concat=n=2:v=0:a=1[aout]", script)
        self.assertIn("offset=2.000000", script)
        self.assertEqual(4.0, expected)

    def test_visual_padding_preserves_audio_longer_than_video(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prepared = self._prepared(root, (2.050, 3.100))
            prepared = (
                replace(prepared[0], media_info=self._info(2.050, video_duration=2.0)),
                replace(prepared[1], media_info=self._info(3.100, video_duration=3.0)),
            )
            script = StudioMontageService().build_transition_filter_script(
                prepared,
                self.profile,
            )

        self.assertIn(
            "tpad=stop_mode=clone:stop_duration=0.550",
            script,
        )
        self.assertIn(
            "tpad=stop_mode=clone:stop_duration=0.100",
            script,
        )
        self.assertIn("offset=2.050000", script)
        self.assertIn("concat=n=2:v=0:a=1[aout]", script)
        self.assertNotIn("atrim=", script)

    def test_large_transition_graph_is_linear_and_uses_no_command_graph(self):
        with tempfile.TemporaryDirectory() as directory:
            prepared = self._prepared(Path(directory), (2.0,) * 230)
            service = StudioMontageService()
            script = service.build_transition_filter_script(prepared, self.profile)
            command = service.build_transition_command(
                sources=tuple(item.path for item in prepared),
                filter_path=Path(directory) / "transitions.ffscript",
                output_path=Path(directory) / "output.mp4",
                profile=self.profile,
            )

        self.assertEqual(229, script.count("xfade=transition=fade"))
        self.assertEqual(
            229,
            script.count("tpad=stop_mode=clone:stop_duration=0.500"),
        )
        self.assertNotIn("acrossfade=", script)
        self.assertNotIn("atrim=", script)
        self.assertIn("concat=n=230:v=0:a=1[aout]", script)
        self.assertIn("-filter_complex_script", command)
        self.assertNotIn("-filter_complex", command)

    def test_one_clip_is_rejected_before_transition_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(StudioMontageInputError, "al menos dos clips"):
                self._plan(root, 1)

    def test_short_clip_with_transitions_fails_before_ffmpeg(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = self._plan(root, 2)
            probe = Mock()
            probe.inspect.side_effect = (self._info(0.5), self._info(2.0))
            runner = Mock()
            service = StudioMontageService(
                probe=probe,
                runner=runner,
                validator=Mock(),
            )

            with self.assertRaisesRegex(StudioMontageError, "duración suficiente"):
                service.compose(plan, root / "output.mp4", self.profile)

        runner.run.assert_not_called()

    def test_short_clip_uses_the_duration_from_the_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = self._plan(root, 2)
            profile = SimpleNamespace(
                **{**vars(self.profile), "transition_duration": 0.30}
            )
            probe = Mock()
            probe.inspect.side_effect = (self._info(0.30), self._info(2.0))
            runner = Mock()
            service = StudioMontageService(
                probe=probe,
                runner=runner,
                validator=Mock(),
            )

            with self.assertRaisesRegex(StudioMontageError, "0.30 s"):
                service.compose(plan, root / "output.mp4", profile)

        runner.run.assert_not_called()

    def test_transition_compose_uses_filter_script_and_profile_encoding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = self._plan(root, 2)
            source_info = self._info(2.0)
            output_info = self._info(4.0)
            probe = Mock()
            probe.inspect.side_effect = (
                source_info,
                source_info,
                output_info,
            )
            validator = Mock()
            validator.validate.return_value = 4.0
            runner = Mock()

            def write_output(command):
                if command[:2] == ["ffmpeg", "-y"]:
                    Path(command[-1]).write_bytes(b"rendered")

            runner.run.side_effect = write_output
            service = StudioMontageService(
                probe=probe,
                runner=runner,
                validator=validator,
            )
            result = service.compose(plan, root / "output.mp4", self.profile)

        command = runner.run.call_args_list[0].args[0]
        self.assertIn("-filter_complex_script", command)
        self.assertNotIn("copy", command)
        self.assertEqual(1, result.transition_count)
        self.assertEqual(4.0, result.expected_duration)
        self.assertEqual(4.0, result.generated_duration)

    def test_no_transition_command_remains_stream_copy(self):
        command = StudioMontageService().build_concat_command(
            "montage.ffconcat",
            "output.mp4",
            "+faststart",
        )
        self.assertIn("-c", command)
        self.assertEqual("copy", command[command.index("-c") + 1])
        self.assertNotIn("-filter_complex_script", command)


@unittest.skipUnless(
    shutil.which("ffmpeg") and shutil.which("ffprobe"),
    "FFmpeg y FFprobe son obligatorios para las transiciones STUDIO.",
)
class StudioMontageTransitionsRealFFmpegTest(unittest.TestCase):

    profile = StudioMontageTransitionsContractTest.profile

    @staticmethod
    def _source(
        path,
        color,
        frequency=440,
        size="160x90",
        fps=24,
        sample_rate=48000,
        with_audio=True,
        duration=0.8,
    ):
        command = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c={color}:s={size}:r={fps}:d={duration}",
        ]
        if with_audio:
            command.extend([
                "-f", "lavfi", "-i",
                f"sine=frequency={frequency}:sample_rate={sample_rate}:duration={duration}",
                "-map", "0:v:0", "-map", "1:a:0",
            ])
        else:
            command.extend(["-map", "0:v:0", "-an"])
        command.extend([
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
        ])
        if with_audio:
            command.extend(["-c:a", "aac", "-ar", str(sample_rate), "-ac", "2"])
        command.append(str(path))
        subprocess.run(command, capture_output=True, check=True)

    @staticmethod
    def _boundary_source(
        path,
        color,
        start_frequency,
        end_frequency,
        base_frequency=440,
        size="160x90",
        fps=24,
        sample_rate=48000,
        duration=1.0,
        marker_duration=0.04,
    ):
        command = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c={color}:s={size}:r={fps}:d={duration}",
            "-f", "lavfi", "-i",
            (
                f"sine=frequency={start_frequency}:sample_rate={sample_rate}:"
                f"duration={marker_duration}"
            ),
            "-f", "lavfi", "-i",
            (
                f"sine=frequency={base_frequency}:sample_rate={sample_rate}:"
                f"duration={duration}"
            ),
            "-f", "lavfi", "-i",
            (
                f"sine=frequency={end_frequency}:sample_rate={sample_rate}:"
                f"duration={marker_duration}"
            ),
            "-filter_complex",
            (
                "[1:a]adelay=0|0[start];"
                f"[3:a]adelay={int((duration - marker_duration) * 1000)}|"
                f"{int((duration - marker_duration) * 1000)}[end];"
                "[2:a][start][end]amix=inputs=3:duration=first:normalize=0[a]"
            ),
            "-map", "0:v:0", "-map", "[a]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", str(sample_rate), "-ac", "2",
            str(path),
        ]
        subprocess.run(command, capture_output=True, check=True)

    def _plan(self, root, sources):
        clips = tuple(
            StudioMontageClip(index, source, source.name)
            for index, source in enumerate(sources, start=1)
        )
        return StudioMontagePlan(
            profile_key=OperationalProfileKey(
                "studio", "vertical", "studio_vertical"
            ),
            transitions_enabled=True,
            clips=clips,
        )

    def _assert_decodes(self, path):
        result = subprocess.run([
            "ffmpeg", "-v", "error", "-i", str(path),
            "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-",
        ], capture_output=True, text=True, check=False)
        self.assertEqual(0, result.returncode, result.stderr)

    @staticmethod
    def _bandpass_mean_volume(path, start, frequency, duration=0.10):
        result = subprocess.run([
            "ffmpeg", "-v", "info", "-i", str(path),
            "-map", "0:a:0",
            "-af",
            (
                f"atrim=start={start:.3f}:duration={duration:.3f},"
                f"bandpass=f={frequency}:width_type=h:width=80,volumedetect"
            ),
            "-f", "null", "-",
        ], capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise AssertionError(result.stderr)
        match = re.search(r"mean_volume: (-?[0-9.]+) dB", result.stderr)
        if match is None:
            raise AssertionError(result.stderr)
        return float(match.group(1))

    @staticmethod
    def _audio_duration(path):
        result = subprocess.run([
            "ffprobe", "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ], capture_output=True, text=True, check=True)
        return float(result.stdout.strip())

    def _assert_boundary_markers(
        self,
        path,
        boundary,
        previous_end_frequency,
        next_start_frequency,
    ):
        marker_window = 0.012
        previous_start = boundary - 0.016
        next_start = boundary + 0.004
        previous_end = self._bandpass_mean_volume(
            path,
            previous_start,
            previous_end_frequency,
            marker_window,
        )
        previous_next = self._bandpass_mean_volume(
            path,
            previous_start,
            next_start_frequency,
            marker_window,
        )
        next_previous = self._bandpass_mean_volume(
            path,
            next_start,
            previous_end_frequency,
            marker_window,
        )
        next_marker = self._bandpass_mean_volume(
            path,
            next_start,
            next_start_frequency,
            marker_window,
        )
        self.assertGreater(previous_end - previous_next, 12.0)
        self.assertGreater(next_marker - next_previous, 12.0)

    def _render_from_prepared(self, service, prepared_clips, profile, root):
        filter_path = root / "transitions.ffscript"
        output_path = root / "montage.mp4"
        service.write_transition_filter_script(
            filter_path,
            prepared_clips,
            profile,
        )
        subprocess.run(
            service.build_transition_command(
                tuple(prepared.path for prepared in prepared_clips),
                filter_path,
                output_path,
                profile,
            ),
            capture_output=True,
            check=True,
        )
        return output_path

    def _render_sequential_audio_reference(self, prepared_clips, profile, root):
        output_path = root / "audio-reference.m4a"
        command = ["ffmpeg", "-y"]
        filter_parts = []
        audio_filters = (
            f"aresample={profile.audio_sample_rate},"
            "aformat="
            f"sample_rates={profile.audio_sample_rate}:"
            "channel_layouts=stereo,"
            "asetpts=PTS-STARTPTS"
        )
        for index, prepared in enumerate(prepared_clips):
            command.extend(["-i", str(prepared.path)])
            filter_parts.append(f"[{index}:a:0]{audio_filters}[a{index}]")
        filter_parts.append(
            "".join(f"[a{index}]" for index in range(len(prepared_clips)))
            + f"concat=n={len(prepared_clips)}:v=0:a=1[aout]"
        )
        command.extend([
            "-filter_complex", ";".join(filter_parts),
            "-map", "[aout]",
            "-c:a", profile.audio_codec,
            "-ar", str(profile.audio_sample_rate),
            "-ac", str(profile.audio_channels),
            str(output_path),
        ])
        subprocess.run(command, capture_output=True, check=True)
        return output_path

    def test_two_and_four_compatible_clips_apply_real_transitions(self):
        for count in (2, 4):
            with self.subTest(count=count), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                sources = []
                for index, color in enumerate(("red", "blue", "green", "yellow")[:count]):
                    path = root / f"{index}.mp4"
                    self._source(path, color, frequency=440 + index * 110)
                    sources.append(path)
                hashes = {
                    path: hashlib.sha256(path.read_bytes()).digest()
                    for path in sources
                }
                result = StudioMontageService().compose(
                    self._plan(root, sources),
                    root / "output" / "montage.mp4",
                    self.profile,
                )

                self.assertEqual(count - 1, result.transition_count)
                self.assertLessEqual(
                    abs(result.generated_duration - 0.8 * count),
                    self.profile.max_duration_difference,
                )
                self._assert_decodes(result.output_path)
                for path, digest in hashes.items():
                    self.assertEqual(digest, hashlib.sha256(path.read_bytes()).digest())

    def test_transition_keeps_distinct_audio_sequential_at_the_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.mp4"
            second = root / "second.mp4"
            self._source(first, "red", frequency=440)
            self._source(second, "blue", frequency=880)
            hashes = {
                path: hashlib.sha256(path.read_bytes()).digest()
                for path in (first, second)
            }

            result = StudioMontageService().compose(
                self._plan(root, (first, second)),
                root / "output" / "montage.mp4",
                self.profile,
            )

            first_440 = self._bandpass_mean_volume(
                result.output_path,
                0.60,
                440,
            )
            first_880 = self._bandpass_mean_volume(
                result.output_path,
                0.60,
                880,
            )
            second_440 = self._bandpass_mean_volume(
                result.output_path,
                0.95,
                440,
            )
            second_880 = self._bandpass_mean_volume(
                result.output_path,
                0.95,
                880,
            )

            self.assertLessEqual(
                abs(result.generated_duration - 1.6),
                self.profile.max_duration_difference,
            )
            self.assertGreater(first_440 - first_880, 12.0)
            self.assertGreater(second_880 - second_440, 12.0)
            self._assert_decodes(result.output_path)
            for path, digest in hashes.items():
                self.assertEqual(digest, hashlib.sha256(path.read_bytes()).digest())

    def test_boundary_markers_keep_the_final_audible_samples_across_contracts(self):
        cases = (
            (
                "compatible_to_compatible_vertical",
                "vertical",
                (
                    ("red", 600, 1600, "160x90", 24, 48000),
                    ("blue", 880, 1700, "160x90", 24, 48000),
                ),
                0,
                1.0,
                1600,
                880,
            ),
            (
                "normalized_to_compatible_vertical",
                "vertical",
                (
                    ("yellow", 300, 350, "160x90", 24, 48000),
                    ("red", 600, 1600, "320x180", 30, 44100),
                    ("blue", 880, 1700, "160x90", 24, 48000),
                ),
                1,
                2.0,
                1600,
                880,
            ),
            (
                "compatible_to_normalized_vertical",
                "vertical",
                (
                    ("red", 600, 1600, "160x90", 24, 48000),
                    ("blue", 880, 1700, "320x180", 30, 44100),
                ),
                1,
                1.0,
                1600,
                880,
            ),
            (
                "compatible_to_compatible_horizontal",
                "horizontal",
                (
                    ("red", 600, 1600, "160x90", 24, 48000),
                    ("blue", 880, 1700, "160x90", 24, 48000),
                ),
                0,
                1.0,
                1600,
                880,
            ),
        )
        for (
            label,
            profile_format,
            source_specs,
            expected_normalized_count,
            boundary,
            previous_end_frequency,
            next_start_frequency,
        ) in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                profile_key = OperationalProfileKey(
                    "studio", profile_format, STUDIO_PROFILE_IDS[profile_format]
                )
                loaded_profile = _load_studio_profile(profile_key)
                profile = replace(
                    loaded_profile,
                    width=160,
                    height=90,
                    fps=24,
                    preset="ultrafast",
                )
                sources = []
                for index, (
                    color,
                    start_frequency,
                    end_frequency,
                    size,
                    fps,
                    sample_rate,
                ) in enumerate(source_specs, start=1):
                    path = root / f"{index}.mp4"
                    self._boundary_source(
                        path,
                        color,
                        start_frequency,
                        end_frequency,
                        size=size,
                        fps=fps,
                        sample_rate=sample_rate,
                    )
                    sources.append(path)
                hashes = {
                    path: hashlib.sha256(path.read_bytes()).digest()
                    for path in sources
                }
                plan = self._plan(root, sources)
                service = StudioMontageService()
                prepared, _, _ = service.prepare(plan, profile, root)
                previous_index = int(boundary) - 1
                previous_source = sources[previous_index]
                previous_prepared = prepared[previous_index].path
                for path in (previous_source, previous_prepared):
                    end_marker = self._bandpass_mean_volume(
                        path,
                        0.984,
                        previous_end_frequency,
                        0.012,
                    )
                    other_marker = self._bandpass_mean_volume(
                        path,
                        0.984,
                        next_start_frequency,
                        0.012,
                    )
                    self.assertGreater(end_marker - other_marker, 12.0)

                output_path = self._render_from_prepared(
                    service,
                    prepared,
                    profile,
                    root,
                )
                reference_audio_path = self._render_sequential_audio_reference(
                    prepared,
                    profile,
                    root,
                )
                self.assertEqual(
                    expected_normalized_count,
                    sum(item.was_normalized for item in prepared),
                )
                self.assertLessEqual(
                    abs(
                        self._audio_duration(output_path)
                        - self._audio_duration(reference_audio_path)
                    ),
                    1 / profile.audio_sample_rate,
                )
                self._assert_boundary_markers(
                    output_path,
                    boundary,
                    previous_end_frequency,
                    next_start_frequency,
                )
                self._assert_boundary_markers(
                    reference_audio_path,
                    boundary,
                    previous_end_frequency,
                    next_start_frequency,
                )
                self._assert_decodes(output_path)
                for path, digest in hashes.items():
                    self.assertEqual(digest, hashlib.sha256(path.read_bytes()).digest())

    def test_boundary_markers_survive_multiple_consecutive_transitions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            specs = (
                ("red", 600, 1600),
                ("blue", 880, 1700),
                ("green", 900, 1800),
            )
            sources = []
            for index, (color, start_frequency, end_frequency) in enumerate(
                specs,
                start=1,
            ):
                path = root / f"{index}.mp4"
                self._boundary_source(
                    path,
                    color,
                    start_frequency,
                    end_frequency,
                )
                sources.append(path)
            hashes = {
                path: hashlib.sha256(path.read_bytes()).digest()
                for path in sources
            }
            service = StudioMontageService()
            prepared, _, _ = service.prepare(
                self._plan(root, sources),
                self.profile,
                root,
            )
            output_path = self._render_from_prepared(
                service,
                prepared,
                self.profile,
                root,
            )
            reference_audio_path = self._render_sequential_audio_reference(
                prepared,
                self.profile,
                root,
            )

            self.assertLessEqual(
                abs(
                    self._audio_duration(output_path)
                    - self._audio_duration(reference_audio_path)
                ),
                1 / self.profile.audio_sample_rate,
            )
            self._assert_boundary_markers(output_path, 1.0, 1600, 880)
            self._assert_boundary_markers(output_path, 2.0, 1700, 900)
            self._assert_boundary_markers(reference_audio_path, 1.0, 1600, 880)
            self._assert_boundary_markers(reference_audio_path, 2.0, 1700, 900)
            self._assert_decodes(output_path)
            for path, digest in hashes.items():
                self.assertEqual(digest, hashlib.sha256(path.read_bytes()).digest())

    def test_real_transition_duration_uses_each_studio_format_value(self):
        for profile_format, expected_transition_duration in (
            ("vertical", 0.25),
            ("horizontal", 0.50),
        ):
            with self.subTest(profile_format=profile_format), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                profile_key = OperationalProfileKey(
                    "studio", profile_format, STUDIO_PROFILE_IDS[profile_format]
                )
                loaded_profile = _load_studio_profile(profile_key)
                profile = replace(
                    loaded_profile,
                    width=160,
                    height=90,
                    fps=24,
                    preset="ultrafast",
                )
                first = root / "first.mp4"
                second = root / "second.mp4"
                self._source(first, "red", frequency=440)
                self._source(second, "blue", frequency=550)
                hashes = {
                    path: hashlib.sha256(path.read_bytes()).digest()
                    for path in (first, second)
                }
                result = StudioMontageService().compose(
                    self._plan(root, (first, second)),
                    root / "output" / "montage.mp4",
                    profile,
                )

                self.assertEqual(1, result.transition_count)
                self.assertEqual(
                    expected_transition_duration,
                    profile.transition_duration,
                )
                self.assertLessEqual(
                    abs(
                        result.generated_duration
                        - 1.6
                    ),
                    profile.max_duration_difference,
                )
                self._assert_decodes(result.output_path)
                for path, digest in hashes.items():
                    self.assertEqual(
                        digest,
                        hashlib.sha256(path.read_bytes()).digest(),
                    )

    def test_heterogeneous_and_silent_clips_normalize_before_transitions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.mp4"
            second = root / "second.mp4"
            third = root / "third.mp4"
            self._source(first, "red", frequency=440)
            self._source(
                second,
                "blue",
                frequency=550,
                size="320x180",
                fps=30,
                sample_rate=44100,
            )
            self._source(third, "green", size="320x180", with_audio=False)
            sources = (first, second, third)
            hashes = {
                path: hashlib.sha256(path.read_bytes()).digest()
                for path in sources
            }
            result = StudioMontageService().compose(
                self._plan(root, sources),
                root / "output" / "montage.mp4",
                self.profile,
            )

            self.assertEqual(2, result.transition_count)
            self.assertEqual(2, result.normalized_clip_count)
            self.assertLessEqual(
                abs(result.generated_duration - 2.4),
                self.profile.max_duration_difference,
            )
            self._assert_decodes(result.output_path)
            for path, digest in hashes.items():
                self.assertEqual(digest, hashlib.sha256(path.read_bytes()).digest())
