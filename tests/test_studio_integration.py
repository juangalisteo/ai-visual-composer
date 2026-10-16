import hashlib
import math
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from array import array
from copy import deepcopy
from pathlib import Path

from app.core import start
from app.modules.studio import (
    StudioInputPreparationService,
    StudioInputMode,
    StudioOutputPathResolver,
    StudioProfileLoader,
    StudioRenderService,
)
from app.modules.video.intro_outro import (
    IntroOutroPlan,
    IntroOutroSelection,
)
from app.shared.media_probe import MediaProbe
from app.shared.profile_identity import OperationalProfileKey, ProfileKey
from app.shared.profile_resolver import ProfileResolver
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


def _load_studio_profile(profile_key):
    operational_key = OperationalProfileKey(
        profile_key.component,
        profile_key.platform,
        profile_key.profile_id,
    )
    return StudioProfileLoader().load(
        ProfileResolver().load_operational(operational_key),
        operational_key,
    )


class StudioFinalContractTest(unittest.TestCase):

    def test_design_subtitles_do_not_replace_the_studio_system_profile(self):
        system_key = ProfileKey.for_component("studio", "instagram")
        profile = _load_studio_profile(system_key)
        descriptors = SubtitleProfileResolver().discover_profiles_for_family(
            "studio", "instagram", "design",
        )

        self.assertEqual(1080, profile.width)
        self.assertEqual(
            {"word_by_word"},
            {descriptor.mode for descriptor in descriptors},
        )
        for descriptor in descriptors:
            subtitle = SubtitleProfileResolver().load(
                descriptor.key
            )
            self.assertEqual("design", subtitle.key.family)
            self.assertIn("design", subtitle.path.parts)


    def test_profiles_and_dynamic_subtitle_styles_cover_final_matrix(self):
        resolver = SubtitleProfileResolver()

        for platform, dimensions in {
            "instagram": (1080, 1920),
            "youtube": (1920, 1080),
        }.items():
            with self.subTest(platform=platform):
                key = ProfileKey.for_component("studio", platform)
                profile = _load_studio_profile(key)
                self.assertEqual(dimensions, (profile.width, profile.height))
                self.assertEqual(30, profile.fps)
                self.assertEqual("libx264", profile.codec)
                self.assertEqual("yuv420p", profile.pixel_format)
                self.assertEqual(("aac", 48000, 2), (
                    profile.audio_codec,
                    profile.audio_sample_rate,
                    profile.audio_channels,
                ))
                styles = {
                    style.value if hasattr(style, "value") else str(style)
                    for style in resolver.discover_styles(key)
                }
                descriptors = resolver.discover_profiles(key)
                self.assertEqual(
                    {descriptor.mode for descriptor in descriptors},
                    styles,
                )
                for descriptor in descriptors:
                    resolved = resolver.load(
                        descriptor.key
                    )
                    self.assertEqual(0, resolved.render_style["offset"])

    def test_realistic_input_names_are_discovered_without_hardcoding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_directory = root / "srt_video"
            source_directory.mkdir()
            video = source_directory / "Vídeo prueba (01).mp4"
            subtitle = source_directory / "Subtítulos vídeo 01.srt"
            video.touch()
            subtitle.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\nTexto íntegro.\n",
                encoding="utf-8",
            )
            key = ProfileKey.for_component("studio", "instagram")
            profile = _load_studio_profile(key)
            prepared = StudioInputPreparationService(root).prepare(
                profile,
                StudioInputMode.SRT_VIDEO,
            )

        self.assertEqual(video, prepared.video_path)
        self.assertEqual(subtitle, prepared.subtitle_path)

    def test_output_path_is_project_owned_for_all_feature_combinations(self):
        key = OperationalProfileKey("studio", "instagram", "studio_instagram")
        project = type("Project", (), {
            "video_path": lambda self: Path(
                "output/studio-test/video/studio-test.mp4"
            ),
        })()
        resolver = StudioOutputPathResolver(project)
        intro = IntroOutroSelection(Path("Intro marca (01).mp4"), "intro")
        outro = IntroOutroSelection(Path("Outro marca (01).mp4"), "outro")
        plans = {
            "none": None,
            "intro": IntroOutroPlan(intro=intro),
            "outro": IntroOutroPlan(outro=outro),
            "both": IntroOutroPlan(intro=intro, outro=outro),
        }
        paths = set()
        for music in (None, Path("Música ambiente 01.mp3")):
            for plan in plans.values():
                paths.add(resolver.resolve(key))

        self.assertEqual(
            {Path("output/studio-test/video/studio-test.mp4")},
            paths,
        )

    def test_runtime_scaffolding_names_are_retired(self):
        self.assertTrue(hasattr(start, "preparar_studio"))
        self.assertTrue(hasattr(start, "ejecutar_studio"))
        self.assertFalse(hasattr(start, "ejecutar_studio_fase_1"))
        self.assertFalse(hasattr(start, "ejecutar_studio_fase_2"))


@unittest.skipUnless(
    os.environ.get("RUN_STUDIO_FINAL_FFMPEG") == "1"
    and shutil.which("ffmpeg")
    and shutil.which("ffprobe"),
    "Set RUN_STUDIO_FINAL_FFMPEG=1 to run the native STUDIO certification.",
)
class StudioFinalRealFFmpegTest(unittest.TestCase):

    class _FirstAssetRng:
        @staticmethod
        def choice(values):
            return values[0]

    @staticmethod
    def _run(command):
        subprocess.run(command, capture_output=True, check=True)

    def _context(self, platform, style="single_line"):
        key = ProfileKey.for_component("studio", platform)
        profile = _load_studio_profile(key)
        subtitle = SubtitleProfileResolver().load(
            SubtitleProfileKey.for_profile(key, style)
        )
        return key, profile, subtitle

    def _video(
        self,
        path,
        duration,
        color="black",
        audio=True,
        frequency=440,
        size="640x360",
        fps=24,
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        command = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i",
            f"color=c={color}:s={size}:r={fps}:d={duration}",
        ]
        if audio:
            command.extend([
                "-f", "lavfi", "-i",
                f"sine=frequency={frequency}:sample_rate=48000:duration={duration}",
                "-shortest",
            ])
        command.extend([
            "-c:v", "libx264", "-preset", "ultrafast",
            "-pix_fmt", "yuv420p", "-r", str(fps),
        ])
        if audio:
            command.extend(["-c:a", "aac", "-ar", "48000", "-ac", "2"])
        command.append(str(path))
        self._run(command)

    def _asset(self, path, profile, duration, color, audio=True):
        self._video(
            path,
            duration,
            color=color,
            audio=audio,
            size=f"{profile.width}x{profile.height}",
            fps=profile.fps,
        )

    @staticmethod
    def _subtitle(path, duration):
        end_ms = min(int(duration * 1000) - 100, 1200)
        seconds, milliseconds = divmod(end_ms, 1000)
        content = (
            "1\n"
            f"00:00:00,150 --> 00:00:{seconds:02d},{milliseconds:03d}\n"
            "SUBTÍTULO STUDIO ÍNTEGRO\n"
        )
        path.write_text(content, encoding="utf-8")

    def _music(self, path, duration=0.35):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i",
            f"sine=frequency=880:sample_rate=48000:duration={duration}",
            "-c:a", "pcm_s16le", str(path),
        ])

    @staticmethod
    def _hashes(paths):
        return {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths
        }

    def _assert_hashes(self, expected):
        for path, digest in expected.items():
            self.assertEqual(digest, hashlib.sha256(path.read_bytes()).hexdigest())

    def _assert_output(self, result, profile, expected_duration):
        info = MediaProbe.inspect(result.output_path)
        self.assertEqual((profile.width, profile.height), (info.width, info.height))
        self.assertAlmostEqual(profile.fps, info.nominal_fps, places=2)
        self.assertEqual(("h264", "yuv420p"), (
            info.video_codec, info.pixel_format
        ))
        self.assertEqual(("aac", 48000, 2), (
            info.audio_codec, info.audio_sample_rate, info.audio_channels
        ))
        self.assertLessEqual(abs(info.duration - expected_duration), 0.2)

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
    def _center_rgb(path, timestamp):
        result = subprocess.run(
            [
                "ffmpeg", "-v", "error", "-ss", str(timestamp), "-i", str(path),
                "-vf", "crop=1:1:(iw-1)/2:(ih-1)/2,format=rgb24",
                "-frames:v", "1", "-f", "rawvideo", "-",
            ],
            capture_output=True,
            check=True,
        )
        return tuple(result.stdout[:3])

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

    def _render(
        self,
        root,
        platform,
        duration,
        style="single_line",
        source_audio=True,
        music=False,
        intro=False,
        outro=False,
        special_names=False,
    ):
        key, profile, subtitle_profile = self._context(platform, style)
        source_name = "Vídeo prueba (01).mp4" if special_names else "source.mp4"
        subtitle_name = (
            "Subtítulos vídeo 01.srt" if special_names else "source.srt"
        )
        source = root / source_name
        subtitle = root / subtitle_name
        self._video(source, duration, audio=source_audio)
        self._subtitle(subtitle, duration)
        protected = [source, subtitle]

        music_path = None
        if music:
            music_path = root / (
                "Música ambiente (01).wav" if special_names else "music.wav"
            )
            self._music(music_path)
            protected.append(music_path)

        intro_path = None
        outro_path = None
        if intro:
            intro_path = root / (
                "Introducción (área 01).mp4" if special_names else "intro.mp4"
            )
            self._asset(intro_path, profile, 0.5, "red", audio=True)
            protected.append(intro_path)
        if outro:
            outro_path = root / (
                "Cierre vídeo (02).mp4" if special_names else "outro.mp4"
            )
            self._asset(outro_path, profile, 0.5, "blue", audio=True)
            protected.append(outro_path)

        plan = None
        if intro or outro:
            plan = IntroOutroPlan(
                intro=(
                    IntroOutroSelection(intro_path, "intro") if intro else None
                ),
                outro=(
                    IntroOutroSelection(outro_path, "outro") if outro else None
                ),
            )
        project = type("Project", (), {
            "video_path": lambda self: (
                root / "salida STUDIO" / "video" / "studio.mp4"
            ),
        })()
        output = StudioOutputPathResolver(project).resolve(key)
        expected_duration = duration + (0.5 if intro else 0) + (0.5 if outro else 0)
        before = self._hashes(protected)
        result = StudioRenderService().render(
            source,
            subtitle,
            key,
            profile,
            subtitle_profile,
            output,
            music_path=music_path,
            intro_outro_selection=plan,
        )
        self._assert_output(result, profile, expected_duration)
        self._assert_hashes(before)
        self.assertGreater(self._subtitle_peak(result.output_path, 0.5 + (0.5 if intro else 0)), 32)
        if source_audio:
            self.assertGreater(
                self._tone_amplitude(result.output_path, 440, start=0.6 if intro else 0.1),
                0.03,
            )
        if music:
            self.assertGreater(
                self._tone_amplitude(result.output_path, 880, start=0.6 if intro else 0.1),
                0.008,
            )
        if plan is not None:
            self.assertEqual("copy", result.intro_outro_command[
                result.intro_outro_command.index("-c") + 1
            ])
            self.assertNotIn("-filter_complex", result.intro_outro_command)
            self.assertNotIn("libx264", result.intro_outro_command)
        if intro:
            red, green, blue = self._center_rgb(result.output_path, 0.2)
            self.assertGreater(red, green + 80)
            self.assertGreater(red, blue + 80)
        if outro:
            red, green, blue = self._center_rgb(
                result.output_path, expected_duration - 0.2
            )
            self.assertGreater(blue, red + 80)
            self.assertGreater(blue, green + 80)
        return result

    def test_case_a_instagram_minimal(self):
        with tempfile.TemporaryDirectory() as directory:
            self._render(Path(directory), "instagram", 1.4)

    def test_case_b_youtube_minimal(self):
        with tempfile.TemporaryDirectory() as directory:
            self._render(Path(directory), "youtube", 1.4, style="word_by_word")

    def test_case_c_instagram_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self._render(
                Path(directory), "instagram", 5.4,
                music=True, intro=True, outro=True,
            )
            self.assertGreater(self._frame_mean(result.output_path, 0.7), 10)
            self.assertLess(self._frame_mean(result.output_path, 3.0), 10)
            self.assertGreater(self._frame_mean(result.output_path, 5.7), 10)

    def test_case_d_youtube_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self._render(
                Path(directory), "youtube", 5.4,
                style="word_by_word", music=True,
                intro=True, outro=True,
            )
            self.assertGreater(self._frame_mean(result.output_path, 0.7), 10)
            self.assertLess(self._frame_mean(result.output_path, 3.0), 10)
            self.assertGreater(self._frame_mean(result.output_path, 5.7), 10)

    def test_case_e_source_without_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self._render(
                Path(directory), "instagram", 1.4,
                source_audio=False, music=True, intro=True, outro=True,
            )
            self.assertTrue(result.silence_added)

    def test_case_f_realistic_paths(self):
        with tempfile.TemporaryDirectory(prefix="STUDIO prueba (área) ") as directory:
            result = self._render(
                Path(directory), "youtube", 1.4,
                music=True, intro=True, outro=True,
                special_names=True,
            )
            self.assertNotIn(" ", result.output_path.name)
            self.assertNotIn("(", result.output_path.name)
            self.assertNotIn(")", result.output_path.name)


if __name__ == "__main__":
    unittest.main()
