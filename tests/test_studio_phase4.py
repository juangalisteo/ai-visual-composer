from array import array
from copy import deepcopy
from dataclasses import replace
import hashlib
import math
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import main
from app.controllers.run_controller import RunController
from app.core.start import ejecutar_studio, iniciar
from app.modules.audio.music_selector import MusicSelector
from app.modules.studio import (
    StudioLightLeakOperation,
    StudioLightLeakSelector,
    StudioOutputPathResolver,
    StudioProfileLoader,
    StudioRenderService,
)
from app.shared.media_probe import MediaInfo, MediaProbe
from app.shared.profile_identity import ProfileKey
from app.shared.profile_resolver import ProfileResolver
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


class StudioPhase4Test(unittest.TestCase):

    def setUp(self):
        self.profile_key = ProfileKey.for_component("studio", "instagram")
        self.profile = StudioProfileLoader().load(
            ProfileResolver().load(self.profile_key),
            self.profile_key,
        )
        self.subtitle_profile = SubtitleProfileResolver().load(
            SubtitleProfileKey.for_profile(self.profile_key, "single_line")
        )
        self.source_info = MediaInfo(
            duration=6.2,
            width=320,
            height=568,
            fps=12.0,
            pixel_format="yuv420p",
            video_codec="h264",
            audio_codec="aac",
            audio_sample_rate=48000,
            audio_channels=2,
        )

    def test_music_contract_is_explicit_and_isolated_by_platform(self):
        for platform in ("instagram", "youtube"):
            key = ProfileKey.for_component("studio", platform)
            profile = StudioProfileLoader().load(ProfileResolver().load(key), key)
            self.assertEqual(0.25, profile.music.volume)
            self.assertTrue(profile.music.loop_shorter)
            self.assertEqual(0.95, profile.music.limiter_limit)

    def test_music_contract_fails_fast(self):
        raw = ProfileResolver().load(self.profile_key)
        cases = (
            ("volume", 0, "volume"),
            ("loop_shorter", False, "loop_shorter"),
            ("limiter_limit", 0.01, "limiter_limit"),
        )
        for field, value, message in cases:
            with self.subTest(field=field):
                invalid = deepcopy(raw)
                invalid["studio"]["music"][field] = value
                with self.assertRaisesRegex(ValueError, message):
                    StudioProfileLoader().load(invalid, self.profile_key)

    def test_controller_skips_catalog_when_music_is_disabled(self):
        selector = Mock()
        controller = RunController(studio_music_selector=selector)
        with patch("builtins.input", return_value="1"):
            self.assertIsNone(controller.select_studio_music())
        selector.discover_tracks.assert_not_called()

    def test_controller_discovers_and_selects_track_explicitly(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            category = root / "ambient"
            category.mkdir()
            first = category / "first.mp3"
            second = category / "second.wav"
            first.touch()
            second.touch()
            controller = RunController(
                studio_music_selector=MusicSelector(root)
            )
            with patch("builtins.input", side_effect=("2", "2")):
                self.assertEqual(second, controller.select_studio_music())

    def test_main_and_start_transport_selected_music(self):
        selected = Path("assets/music/ambient/ambient_001.mp3")
        options = {
            "profile_component": "studio",
            "profile_platform": "instagram",
            "profile_id": "studio_instagram",
            "subtitle_config": "single_line",
            "voice_config": "",
            "music_category": None,
            "overlays_mode": "off",
            "project_name": "",
            "visual_pipeline": "studio",
            "script_source": "external",
            "design_target": "",
            "pipeline_mode": "studio",
            "studio_light_leaks_enabled": True,
            "studio_music_path": str(selected),
            "intro_outro_selection": None,
            "clear_output": False,
        }
        with patch.dict("os.environ", {}, clear=True), patch(
            "main.RunController"
        ) as controller, patch(
            "main.iniciar"
        ) as start, patch("main.OutputManager"):
            controller.return_value.run.return_value = options
            self.assertEqual(0, main.main())
        start.assert_called_once_with(
            subtitle_style="single_line",
            studio_light_leaks_enabled=True,
            studio_music_path=str(selected),
        )

        with patch.dict("os.environ", {"MC_PIPELINE_MODE": "studio"}, clear=True), patch(
            "app.core.start.ejecutar_studio"
        ) as studio, patch("app.core.start.ProjectManager") as project_manager:
            iniciar(subtitle_style="single_line", studio_music_path=selected)
        studio.assert_called_once_with(
            subtitle_style="single_line",
            light_leaks_enabled=False,
            music_path=selected,
        )
        project_manager.assert_not_called()

    def test_phase_two_transports_track_to_naming_and_renderer(self):
        track = Path("assets/music/ambient/ambient_001.mp3")
        preparation = SimpleNamespace(
            video_path=Path("input/studio/source.mp4"),
            subtitle_path=Path("input/studio/source.srt"),
            profile_key=self.profile_key,
            profile=self.profile,
            subtitle_profile=self.subtitle_profile,
        )
        renderer = Mock()
        renderer.render.return_value = "rendered"
        resolver = Mock()
        resolver.resolve.return_value = Path("output/studio/result.mp4")
        result = ejecutar_studio(
            subtitle_style="single_line",
            light_leaks_enabled=True,
            music_path=track,
            preparation_service=Mock(return_value=preparation),
            render_service=renderer,
            output_path_resolver=resolver,
        )
        self.assertEqual("rendered", result)
        self.assertEqual(track, resolver.resolve.call_args.kwargs["music_path"])
        self.assertEqual(track, renderer.render.call_args.kwargs["music_path"])

    def test_output_name_identifies_music_after_light_leaks(self):
        resolver = StudioOutputPathResolver(Path("output/studio"))
        music = Path("assets/music/My Track (Final).mp3")
        music_only = resolver.resolve(
            "source.mp4",
            self.profile_key,
            self.subtitle_profile,
            music_path=music,
        )
        combined = resolver.resolve(
            "source.mp4",
            self.profile_key,
            self.subtitle_profile,
            light_leaks_enabled=True,
            music_path=music,
        )
        self.assertTrue(music_only.name.endswith("_music_My_Track_Final.mp4"))
        self.assertTrue(
            combined.name.endswith("_light_leaks_music_My_Track_Final.mp4")
        )

    def test_four_input_combinations_use_explicit_indices(self):
        operation = StudioLightLeakOperation(
            start_time=0.0,
            end_time=1.0,
            asset_path=Path("leak.mp4"),
            input_position=0,
            opacity=0.15,
            blend_mode="screen",
        )
        silent_info = replace(
            self.source_info,
            audio_codec=None,
            audio_sample_rate=None,
            audio_channels=None,
        )
        cases = (
            (self.source_info, (), None, "[0:a:0]", None),
            (self.source_info, (operation,), None, "[0:a:0]", "[1:v]"),
            (self.source_info, (), "music.mp3", "[0:a:0]", "[1:a:0]"),
            (self.source_info, (operation,), "music.mp3", "[0:a:0]", "[2:a:0]"),
            (silent_info, (operation,), "music.mp3", "[2:a:0]", "[3:a:0]"),
        )
        for info, operations, music, audio_label, added_label in cases:
            with self.subTest(operations=len(operations), music=music, audio=info.has_audio):
                command = StudioRenderService().build_command(
                    "source.mp4",
                    "source.srt",
                    "result.mp4",
                    info,
                    self.profile,
                    "FontName=Arial",
                    operations,
                    music,
                )
                graph = command[command.index("-filter_complex") + 1]
                self.assertIn(audio_label, graph)
                if added_label:
                    self.assertIn(added_label, graph)

    def test_music_graph_preserves_source_gain_and_uses_profile_mix_contract(self):
        command = StudioRenderService().build_command(
            "source.mp4",
            "source.srt",
            "result.mp4",
            self.source_info,
            self.profile,
            "FontName=Arial",
            music_path="music.mp3",
        )
        graph = command[command.index("-filter_complex") + 1]
        self.assertIn("[0:a:0]aresample=48000", graph)
        self.assertIn("[1:a:0]volume=0.250000", graph)
        self.assertIn("amix=inputs=2:duration=first:dropout_transition=0:normalize=0", graph)
        self.assertIn("alimiter=limit=0.950000:level=false:latency=true", graph)
        self.assertEqual(1, command.count("-c:v"))

    def test_music_uses_loop_and_trim_without_second_render(self):
        command = StudioRenderService().build_command(
            "source.mp4",
            "source.srt",
            "result.mp4",
            self.source_info,
            self.profile,
            "FontName=Arial",
            music_path="music.mp3",
        )
        graph = command[command.index("-filter_complex") + 1]
        self.assertEqual(1, command.count("ffmpeg"))
        self.assertEqual(1, command.count("-stream_loop"))
        self.assertEqual(2, graph.count("atrim=duration=6.200000"))
        self.assertEqual("6.200000", command[command.index("-t") + 1])

    def test_missing_music_fails_before_render_and_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mp4"
            subtitle = root / "source.srt"
            source.touch()
            subtitle.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\nText\n",
                encoding="utf-8",
            )
            runner = Mock()
            with self.assertRaisesRegex(FileNotFoundError, "pista musical"):
                StudioRenderService(runner=runner).render(
                    source,
                    subtitle,
                    self.profile_key,
                    self.profile,
                    self.subtitle_profile,
                    root / "result.mp4",
                    music_path=root / "missing.mp3",
                )
            runner.run.assert_not_called()
            self.assertFalse((root / "result.mp4").exists())


@unittest.skipUnless(
    shutil.which("ffmpeg") and shutil.which("ffprobe"),
    "FFmpeg y FFprobe son obligatorios para la prueba real STUDIO.",
)
class StudioPhase4RealFFmpegTest(unittest.TestCase):

    class _FirstAssetRng:
        @staticmethod
        def choice(values):
            return values[0]

    def setUp(self):
        self.profile_key = ProfileKey.for_component("studio", "instagram")
        profile = StudioProfileLoader().load(
            ProfileResolver().load(self.profile_key),
            self.profile_key,
        )
        self.profile = replace(
            profile,
            width=320,
            height=568,
            fps=12,
            preset="ultrafast",
        )
        self.subtitle_profile = SubtitleProfileResolver().load(
            SubtitleProfileKey.for_profile(self.profile_key, "single_line")
        )

    @staticmethod
    def _run(command):
        subprocess.run(command, capture_output=True, check=True)

    def _source(self, path, duration=6.2, with_audio=True):
        command = [
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            f"color=c=black:s=320x568:r=12:d={duration}",
        ]
        if with_audio:
            command.extend([
                "-f", "lavfi", "-i",
                f"sine=frequency=440:sample_rate=48000:duration={duration}",
                "-shortest",
            ])
        command.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p"])
        if with_audio:
            command.extend(["-c:a", "aac"])
        command.append(str(path))
        self._run(command)

    def _music(self, path, duration=0.7):
        self._run([
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            f"sine=frequency=880:sample_rate=48000:duration={duration}",
            "-c:a", "pcm_s16le", str(path),
        ])

    def _leak(self, path, duration=1.0):
        self._run([
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            f"color=c=white:s=320x568:r=12:d={duration}",
            "-f", "lavfi", "-i",
            f"sine=frequency=1760:sample_rate=48000:duration={duration}",
            "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", str(path),
        ])

    @staticmethod
    def _srt(path):
        path.write_text(
            "1\n00:00:00,200 --> 00:00:00,900\nSUBTITLE ABOVE LEAK\n",
            encoding="utf-8",
        )

    @staticmethod
    def _tone_amplitude(path, frequency, start=0.1, duration=0.5):
        result = subprocess.run(
            [
                "ffmpeg", "-v", "error", "-ss", str(start), "-i", str(path),
                "-t", str(duration), "-map", "0:a:0", "-ac", "1", "-ar", "8000",
                "-f", "f32le", "-",
            ],
            capture_output=True,
            check=True,
        )
        samples = array("f")
        samples.frombytes(result.stdout)
        if sys.byteorder != "little":
            samples.byteswap()
        count = len(samples)
        real = sum(
            sample * math.cos(2 * math.pi * frequency * index / 8000)
            for index, sample in enumerate(samples)
        )
        imaginary = sum(
            sample * math.sin(2 * math.pi * frequency * index / 8000)
            for index, sample in enumerate(samples)
        )
        return 2 * math.hypot(real, imaginary) / count

    @staticmethod
    def _frame_mean(path, timestamp):
        result = subprocess.run(
            [
                "ffmpeg", "-v", "error", "-ss", str(timestamp), "-i", str(path),
                "-vf", "format=gray", "-frames:v", "1", "-f", "rawvideo", "-",
            ],
            capture_output=True,
            check=True,
        )
        return sum(result.stdout) / len(result.stdout)

    @staticmethod
    def _subtitle_peak(path, timestamp):
        result = subprocess.run(
            [
                "ffmpeg", "-v", "error", "-ss", str(timestamp), "-i", str(path),
                "-vf", "signalstats,metadata=print:file=-", "-frames:v", "1",
                "-f", "null", "-",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        values = [
            float(line.split("=", 1)[1])
            for line in result.stdout.splitlines()
            if "lavfi.signalstats.YMAX=" in line
        ]
        return values[-1]

    def _render(self, root, name, source, subtitle, music=None, leaks=False):
        selector = None
        if leaks:
            selector = StudioLightLeakSelector(
                root / "Light Leaks",
                self._FirstAssetRng(),
            )
        return StudioRenderService(light_leaks_selector=selector).render(
            source,
            subtitle,
            self.profile_key,
            self.profile,
            self.subtitle_profile,
            root / name,
            light_leaks_enabled=leaks,
            music_path=music,
        )

    def test_real_source_audio_and_music_preserve_both_signals(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mp4"
            subtitle = root / "source.srt"
            music = root / "music.wav"
            self._source(source, duration=2.2)
            self._srt(subtitle)
            self._music(music, duration=4.0)
            hashes = {path: hashlib.sha256(path.read_bytes()).digest() for path in (source, subtitle, music)}
            result = self._render(root, "case_a.mp4", source, subtitle, music)
            self.assertGreater(self._tone_amplitude(result.output_path, 440), 0.04)
            self.assertGreater(self._tone_amplitude(result.output_path, 880), 0.01)
            self.assertLessEqual(abs(result.generated_duration - 2.2), 0.2)
            for path, digest in hashes.items():
                self.assertEqual(digest, hashlib.sha256(path.read_bytes()).digest())

    def test_real_silent_source_with_music_has_valid_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "silent.mp4"
            subtitle = root / "source.srt"
            music = root / "music.wav"
            self._source(source, duration=2.2, with_audio=False)
            self._srt(subtitle)
            self._music(music)
            result = self._render(root, "case_b.mp4", source, subtitle, music)
            info = MediaProbe.inspect(result.output_path)
            self.assertTrue(result.silence_added)
            self.assertEqual(("aac", 48000, 2), (
                info.audio_codec, info.audio_sample_rate, info.audio_channels
            ))
            self.assertGreater(self._tone_amplitude(result.output_path, 880), 0.01)

    def test_real_short_music_loops_without_gaps_or_duration_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mp4"
            subtitle = root / "source.srt"
            music = root / "short.wav"
            self._source(source, duration=3.2, with_audio=False)
            self._srt(subtitle)
            self._music(music, duration=0.35)
            result = self._render(root, "case_c.mp4", source, subtitle, music)
            self.assertGreater(
                self._tone_amplitude(result.output_path, 880, start=2.6, duration=0.4),
                0.01,
            )
            self.assertLessEqual(abs(result.generated_duration - 3.2), 0.2)

    def test_real_light_leaks_music_subtitles_and_audio_are_isolated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            leaks = root / "Light Leaks"
            leaks.mkdir()
            source = root / "source.mp4"
            subtitle = root / "source.srt"
            music = root / "music.wav"
            leak = leaks / "leak.mp4"
            self._source(source)
            self._srt(subtitle)
            self._music(music)
            self._leak(leak)
            hashes = {path: hashlib.sha256(path.read_bytes()).digest() for path in (source, subtitle, music, leak)}
            result = self._render(
                root, "case_d.mp4", source, subtitle, music, leaks=True
            )
            info = MediaProbe.inspect(result.output_path)
            self.assertEqual(2, len(result.light_leaks_operations))
            self.assertEqual((320, 568, 12.0), (info.width, info.height, info.fps))
            self.assertEqual(("h264", "yuv420p", "aac"), (
                info.video_codec, info.pixel_format, info.audio_codec
            ))
            self.assertGreater(self._tone_amplitude(result.output_path, 440), 0.04)
            self.assertGreater(self._tone_amplitude(result.output_path, 880), 0.01)
            self.assertLess(self._tone_amplitude(result.output_path, 1760), 0.005)
            self.assertGreater(self._frame_mean(result.output_path, 0.1), 10)
            self.assertLess(self._frame_mean(result.output_path, 2.5), 5)
            self.assertGreater(self._frame_mean(result.output_path, 5.2), 10)
            self.assertGreater(self._subtitle_peak(result.output_path, 0.5), 32)
            self.assertLessEqual(abs(result.generated_duration - 6.2), 0.2)
            for path, digest in hashes.items():
                self.assertEqual(digest, hashlib.sha256(path.read_bytes()).digest())


if __name__ == "__main__":
    unittest.main()
