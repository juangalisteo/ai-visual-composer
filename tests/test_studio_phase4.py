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
        with patch("builtins.input", return_value="2"):
            self.assertIsNone(controller.select_studio_music())
        selector.select.assert_not_called()
        selector.discover_tracks.assert_not_called()

    def test_controller_selects_random_track_without_listing_catalog(self):
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
            with patch("builtins.input", return_value="1"), patch(
                "app.modules.audio.music_selector.random.choice",
                side_effect=lambda candidates: candidates[-1],
            ), patch.object(controller, "_print") as print_mock:
                self.assertEqual(second, controller.select_studio_music())

        printed = "\n".join(
            str(call.args[0])
            for call in print_mock.call_args_list
            if call.args
        )
        self.assertIn("MÚSICA", printed)
        self.assertIn("1. Sí", printed)
        self.assertIn("2. No", printed)
        self.assertNotIn("first.mp3", printed)
        self.assertNotIn("second.wav", printed)

    def test_main_and_start_transport_selected_music(self):
        selected = Path("assets/music/ambient/ambient_001.mp3")
        final_output = Path("output/studio/video/studio.mp4")
        options = {
            "profile_component": "studio",
            "profile_platform": "instagram",
            "profile_id": "studio_instagram",
            "subtitle_config": "single_line",
            "voice_config": "",
            "music_category": None,
            "project_name": "",
            "visual_pipeline": "studio",
            "script_source": "external",
            "design_target": "",
            "pipeline_mode": "studio",
            "studio_music_path": str(selected),
            "studio_input_mode": "srt_video",
            "intro_outro_selection": None,
            "clear_output": False,
        }
        with patch.dict("os.environ", {}, clear=True), patch(
            "main.RunController"
        ) as controller, patch(
            "main.iniciar"
        ) as start, patch("main.OutputManager"), patch(
            "builtins.print"
        ) as print_mock:
            controller.return_value.run.return_value = options
            start.return_value = SimpleNamespace(output_path=final_output)
            self.assertEqual(0, main.main())
        printed = "\n".join(
            str(call.args[0])
            for call in print_mock.call_args_list
            if call.args
        )
        self.assertIn("STUDIO COMPLETADO", printed)
        self.assertIn("Output:", printed)
        self.assertIn(str(final_output), printed)
        start.assert_called_once_with(
            subtitle_style="single_line",
            studio_music_path=str(selected),
            studio_input_mode="srt_video",
        )

        with patch.dict("os.environ", {"MC_PIPELINE_MODE": "studio"}, clear=True), patch(
            "app.core.start.ejecutar_studio"
        ) as studio, patch("app.core.start.ProjectManager") as project_manager:
            iniciar(
                subtitle_style="single_line",
                studio_music_path=selected,
                studio_input_mode="srt_video",
            )
        studio.assert_called_once_with(
            subtitle_style="single_line",
            music_path=selected,
            input_mode="srt_video",
            project=project_manager.return_value,
        )
        project_manager.return_value.setup.assert_called_once_with()

    def test_phase_two_transports_track_to_naming_and_renderer(self):
        track = Path("assets/music/ambient/ambient_001.mp3")
        preparation = SimpleNamespace(
            video_path=Path("input/studio/srt_video/source.mp4"),
            subtitle_path=Path("input/studio/srt_video/source.srt"),
            input_mode="srt_video",
            profile_key=self.profile_key,
            profile=self.profile,
            subtitle_profile=self.subtitle_profile,
        )
        renderer = Mock()
        renderer.render.return_value = "rendered"
        resolver = Mock()
        resolver.resolve.return_value = Path("output/studio/result.mp4")
        project = Mock()
        result = ejecutar_studio(
            subtitle_style="single_line",
            input_mode="srt_video",
            music_path=track,
            preparation_service=Mock(return_value=preparation),
            render_service=renderer,
            output_path_resolver=resolver,
            project=project,
        )
        self.assertEqual("rendered", result)
        resolver.resolve.assert_called_once_with(
            profile_key=preparation.profile_key,
            project=project,
        )
        self.assertEqual(track, renderer.render.call_args.kwargs["music_path"])

    def test_output_path_is_stable_when_music_changes(self):
        project = Mock()
        project.video_path.return_value = Path("output/studio/video/studio.mp4")
        resolver = StudioOutputPathResolver(project)
        self.assertEqual(
            Path("output/studio/video/studio.mp4"),
            resolver.resolve(self.profile_key),
        )

    def test_audio_inputs_use_explicit_indices(self):
        silent_info = replace(
            self.source_info,
            audio_codec=None,
            audio_sample_rate=None,
            audio_channels=None,
        )
        cases = (
            (self.source_info, None, "[0:a:0]", None),
            (self.source_info, "music.mp3", "[0:a:0]", "[1:a:0]"),
            (silent_info, "music.mp3", "[1:a:0]", "[2:a:0]"),
        )
        for info, music, audio_label, added_label in cases:
            with self.subTest(music=music, audio=info.has_audio):
                command = StudioRenderService().build_command(
                    "source.mp4",
                    "source.srt",
                    "result.mp4",
                    info,
                    self.profile,
                    "FontName=Arial",
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

    def _render(self, root, name, source, subtitle, music=None):
        return StudioRenderService().render(
            source,
            subtitle,
            self.profile_key,
            self.profile,
            self.subtitle_profile,
            root / name,
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

if __name__ == "__main__":
    unittest.main()
