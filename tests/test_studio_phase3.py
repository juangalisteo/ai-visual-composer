import hashlib
import random
import shutil
import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

from app.core.start import ejecutar_studio_fase_2
from app.modules.studio import (
    StudioLightLeakSelector,
    StudioLightLeaksPlanBuilder,
    StudioLightLeaksPlanner,
    StudioOutputPathResolver,
    StudioProfileLoader,
    StudioRenderService,
)
from app.shared.media_probe import MediaInfo, MediaProbe
from app.shared.profile_identity import ProfileKey
from app.shared.profile_resolver import ProfileResolver
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


class StudioPhase3Test(unittest.TestCase):

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
            duration=11.3,
            width=640,
            height=360,
            fps=24.0,
            pixel_format="yuv420p",
            video_codec="h264",
            audio_codec="aac",
            audio_sample_rate=48000,
            audio_channels=2,
        )

    def _profile_with_light_leaks(self, **changes):
        return replace(
            self.profile,
            light_leaks=replace(self.profile.light_leaks, **changes),
        )

    def _sources(self, root):
        video = root / "source.mp4"
        subtitle = root / "source.srt"
        video.write_bytes(b"source video")
        subtitle.write_text(
            "1\n00:00:00,200 --> 00:00:00,900\nTexto intacto\n",
            encoding="utf-8",
        )
        return video, subtitle

    def _service(self, directory, selector_rng=None):
        probe = Mock()
        probe.inspect.return_value = self.source_info
        selector = StudioLightLeakSelector(directory, selector_rng)
        return StudioRenderService(
            runner=Mock(),
            probe=probe,
            output_validator=Mock(),
            light_leaks_selector=selector,
        )

    def test_profile_exposes_explicit_ab_contract_for_both_platforms(self):
        for platform in ("instagram", "youtube"):
            key = ProfileKey.for_component("studio", platform)
            profile = StudioProfileLoader().load(ProfileResolver().load(key), key)
            self.assertEqual("AB", profile.light_leaks.pattern)
            self.assertEqual(1.0, profile.light_leaks.active_duration_seconds)
            self.assertEqual(4.0, profile.light_leaks.clean_duration_seconds)
            self.assertTrue(profile.light_leaks.avoid_immediate_repeat)
            self.assertEqual(0.15, profile.light_leaks.opacity)
            self.assertEqual("screen", profile.light_leaks.blend_mode)

    def test_invalid_light_leaks_contract_fails_fast(self):
        raw = ProfileResolver().load(self.profile_key)
        invalid_cases = (
            ("pattern", "BA", "pattern"),
            ("active_duration_seconds", 0, "active_duration_seconds"),
            ("clean_duration_seconds", -1, "clean_duration_seconds"),
            ("avoid_immediate_repeat", "yes", "booleana"),
        )
        for key, value, message in invalid_cases:
            with self.subTest(key=key):
                profile = {
                    **raw,
                    "studio": {
                        **raw["studio"],
                        "light_leaks": {
                            **raw["studio"]["light_leaks"],
                            key: value,
                        },
                    },
                }
                with self.assertRaisesRegex((TypeError, ValueError), message):
                    StudioProfileLoader().load(profile, self.profile_key)

    def test_planner_generates_ab_segments_and_trims_last_segment(self):
        segments = StudioLightLeaksPlanner(self.profile.light_leaks).build(11.3)
        self.assertEqual(
            (
                (0.0, 1.0, True),
                (1.0, 5.0, False),
                (5.0, 6.0, True),
                (6.0, 10.0, False),
                (10.0, 11.0, True),
                (11.0, 11.3, False),
            ),
            tuple((item.start_time, item.end_time, item.active) for item in segments),
        )

    def test_selector_uses_only_light_leaks_and_avoids_immediate_repeat(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "one.mp4").touch()
            (root / "two.mov").touch()
            (root / "ignored.avi").touch()
            selector = StudioLightLeakSelector(root, random.Random(7))
            selected = [selector.select(True) for _ in range(8)]
            self.assertTrue(all(path.parent == root.resolve() for path in selected))
            self.assertTrue(all(path.suffix.lower() in {".mp4", ".mov"} for path in selected))
            self.assertTrue(all(a != b for a, b in zip(selected, selected[1:])))

    def test_selector_accepts_one_asset_and_missing_assets_fail_clearly(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            asset = root / "only.mp4"
            asset.touch()
            selector = StudioLightLeakSelector(root, random.Random(1))
            self.assertEqual(asset.resolve(), selector.select(True))
            self.assertEqual(asset.resolve(), selector.select(True))
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(FileNotFoundError, "al menos un asset"):
                StudioLightLeakSelector(directory).select(True)

    def test_enabled_render_uses_one_ffmpeg_command_and_places_subtitles_last(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            leaks = root / "Light Leaks"
            leaks.mkdir()
            (leaks / "leak.mp4").touch()
            video, subtitle = self._sources(root)
            service = self._service(leaks, random.Random(3))
            operations = StudioLightLeaksPlanBuilder(
                StudioLightLeaksPlanner(self.profile.light_leaks),
                service.light_leaks_selector,
            ).build(self.source_info.duration)
            command = service.build_command(
                video,
                subtitle,
                root / "result.mp4",
                self.source_info,
                self.profile,
                "FontName=Arial",
                operations,
            )
            graph = command[command.index("-filter_complex") + 1]
            self.assertEqual(1, command.count("-c:v"))
            self.assertEqual(len(operations), command.count("-stream_loop"))
            self.assertIn("blend=all_mode=screen:all_opacity=0.150", graph)
            self.assertLess(graph.index("studio_leak0]"), graph.index("subtitles="))
            self.assertEqual(2, command.count("-map"))
            self.assertIn("[0:a:0]aresample", graph)

    def test_disabled_render_preserves_phase_two_command_and_output_name(self):
        resolver = StudioOutputPathResolver(Path("output/studio"))
        clean = resolver.resolve("source.mp4", self.profile_key, self.subtitle_profile)
        leaks = resolver.resolve(
            "source.mp4",
            self.profile_key,
            self.subtitle_profile,
            light_leaks_enabled=True,
        )
        self.assertEqual(
            Path("output/studio/instagram/source_studio_instagram_single_line.mp4"),
            clean,
        )
        self.assertEqual(
            Path("output/studio/instagram/source_studio_instagram_single_line_light_leaks.mp4"),
            leaks,
        )

    def test_enabled_render_preserves_sources_and_fails_before_output_without_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video, subtitle = self._sources(root)
            hashes = (
                hashlib.sha256(video.read_bytes()).digest(),
                hashlib.sha256(subtitle.read_bytes()).digest(),
            )
            (root / "Light Leaks").mkdir()
            with self.assertRaisesRegex(FileNotFoundError, "al menos un asset"):
                self._service(root / "Light Leaks").render(
                    video,
                    subtitle,
                    self.profile_key,
                    self.profile,
                    self.subtitle_profile,
                    root / "result.mp4",
                    light_leaks_enabled=True,
                )
            self.assertEqual(hashes[0], hashlib.sha256(video.read_bytes()).digest())
            self.assertEqual(hashes[1], hashlib.sha256(subtitle.read_bytes()).digest())
            self.assertFalse((root / "result.mp4").exists())

    def test_phase_two_transports_the_explicit_runtime_decision(self):
        preparation = Mock(
            video_path=Path("input/studio/source.mp4"),
            subtitle_path=Path("input/studio/source.srt"),
            profile_key=self.profile_key,
            profile=self.profile,
            subtitle_profile=self.subtitle_profile,
        )
        render = Mock()
        render.render.return_value = "rendered"
        resolver = Mock(return_value=Path("output/studio/result.mp4"))
        self.assertEqual(
            "rendered",
            ejecutar_studio_fase_2(
                subtitle_style="single_line",
                light_leaks_enabled=True,
                preparation_service=Mock(return_value=preparation),
                render_service=render,
                output_path_resolver=resolver,
            ),
        )
        resolver.resolve.assert_called_once_with(
            video_path=preparation.video_path,
            profile_key=preparation.profile_key,
            subtitle_profile=preparation.subtitle_profile,
            light_leaks_enabled=True,
            music_path=None,
        )
        self.assertTrue(render.render.call_args.kwargs["light_leaks_enabled"])


@unittest.skipUnless(
    shutil.which("ffmpeg") and shutil.which("ffprobe"),
    "FFmpeg y FFprobe son obligatorios para la prueba real STUDIO.",
)
class StudioPhase3RealFFmpegTest(unittest.TestCase):

    light_leaks_directory = Path("assets/videos/overlays/Light Leaks")

    def _profile(self):
        key = ProfileKey.for_component("studio", "instagram")
        profile = StudioProfileLoader().load(ProfileResolver().load(key), key)
        profile = replace(profile, width=320, height=568, fps=12, preset="ultrafast")
        subtitles = SubtitleProfileResolver().load(
            SubtitleProfileKey.for_profile(key, "single_line")
        )
        return key, profile, subtitles

    class _FirstAssetRng:

        @staticmethod
        def choice(values):
            return values[0]

    def _make_source(self, path):
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "lavfi", "-i",
                "color=c=black:s=320x568:r=12:d=11.2",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=11.2",
                "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", str(path),
            ],
            capture_output=True,
            check=True,
        )

    @staticmethod
    def _frame_rgb(path, timestamp):
        result = subprocess.run(
            [
                "ffmpeg", "-v", "error", "-ss", str(timestamp), "-i", str(path),
                "-vf", "format=rgb24", "-frames:v", "1",
                "-f", "rawvideo", "-",
            ],
            capture_output=True,
            check=True,
        )
        return result.stdout

    @staticmethod
    def _mean_frame_difference(left, right):
        return sum(
            abs(first - second)
            for first, second in zip(left, right)
        ) / len(left)

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

    def test_real_ab_render_preserves_sources_audio_and_subtitles(self):
        asset = sorted(
            (
                path
                for path in self.light_leaks_directory.iterdir()
                if path.suffix.lower() in {".mov", ".mp4"}
            ),
            key=lambda path: path.name.lower(),
        )[0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mp4"
            subtitle = root / "source.srt"
            self._make_source(source)
            subtitle.write_text(
                "1\n00:00:00,200 --> 00:00:00,900\nSUBTITLE ABOVE LEAK\n",
                encoding="utf-8",
            )
            hashes = {
                path: hashlib.sha256(path.read_bytes()).digest()
                for path in (source, subtitle, asset)
            }
            key, profile, subtitles = self._profile()
            selector = StudioLightLeakSelector(
                self.light_leaks_directory,
                self._FirstAssetRng(),
            )
            service = StudioRenderService(light_leaks_selector=selector)
            clean = service.render(
                source, subtitle, key, profile, subtitles, root / "clean.mp4"
            )
            rendered = service.render(
                source,
                subtitle,
                key,
                profile,
                subtitles,
                root / "leaks.mp4",
                light_leaks_enabled=True,
            )
            self.assertEqual(3, len(rendered.light_leaks_operations))
            self.assertLessEqual(abs(rendered.generated_duration - 11.2), 0.2)
            self.assertLessEqual(abs(clean.generated_duration - 11.2), 0.2)
            self.assertGreater(
                max(self._mean_frame_difference(
                    self._frame_rgb(rendered.output_path, point),
                    self._frame_rgb(clean.output_path, point),
                ) for point in (0.15, 0.45, 0.75)),
                1,
            )
            self.assertLessEqual(
                self._mean_frame_difference(
                    self._frame_rgb(rendered.output_path, 2.5),
                    self._frame_rgb(clean.output_path, 2.5),
                ),
                1,
            )
            self.assertGreater(self._subtitle_peak(rendered.output_path, 0.5), 32.0)
            info = MediaProbe.inspect(rendered.output_path)
            self.assertTrue(info.has_audio)
            self.assertEqual("aac", info.audio_codec)
            self.assertEqual(48000, info.audio_sample_rate)
            self.assertEqual(2, info.audio_channels)
            for path, digest in hashes.items():
                self.assertEqual(digest, hashlib.sha256(path.read_bytes()).digest())


if __name__ == "__main__":
    unittest.main()
