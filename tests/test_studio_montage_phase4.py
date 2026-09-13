from pathlib import Path
import hashlib
import shutil
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import ANY, Mock, patch

import main
from app.core.start import ejecutar_studio_montaje
from app.controllers.run_controller import RunController
from app.modules.studio import (
    StudioMontageClip,
    StudioMontageFullResult,
    StudioMontageMode,
    StudioMontagePlan,
    StudioMontageResult,
    StudioRenderResult,
)
from app.shared.profile_identity import ProfileKey
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


class StudioMontagePhase4Test(unittest.TestCase):

    def setUp(self):
        self.profile_key = ProfileKey.for_component("studio", "instagram")
        self.profile = SimpleNamespace(
            fps=30,
            max_duration_difference=0.2,
            music=SimpleNamespace(volume=0.10),
        )
        self.subtitle_profile = object()

    def _plan(
        self,
        root,
        mode=StudioMontageMode.MONTAJE_COMPLETO,
        transitions_enabled=False,
        clip_count=1,
    ):
        clips = []
        for index in range(1, clip_count + 1):
            source = root / f"source-{index}.mp4"
            source.write_bytes(b"source")
            clips.append(StudioMontageClip(index, source, source.name))
        return StudioMontagePlan(
            profile_key=self.profile_key,
            mode=mode,
            transitions_enabled=transitions_enabled,
            clips=tuple(clips),
        )

    def _dependencies(self, root):
        project = Mock()
        profile_resolver = Mock()
        profile_resolver.load.return_value = {"studio": {}}
        profile_loader = Mock()
        profile_loader.load.return_value = self.profile
        output_path = root / "output" / "demo" / "video" / "demo.mp4"
        output_resolver = Mock()
        output_resolver.resolve.return_value = output_path
        config_manager = Mock()
        config_manager.get_subtitle_profile.return_value = self.subtitle_profile
        return (
            project,
            profile_resolver,
            profile_loader,
            output_resolver,
            config_manager,
            output_path,
        )

    def test_full_montage_uses_one_temporal_principal_and_common_studio_flow(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = self._plan(
                root,
                transitions_enabled=True,
                clip_count=2,
            )
            source_hashes = {
                clip.path: hashlib.sha256(clip.path.read_bytes()).digest()
                for clip in plan.clips
            }
            (
                project,
                profile_resolver,
                profile_loader,
                output_resolver,
                config_manager,
                output_path,
            ) = self._dependencies(root)
            montage = Mock()
            stages = []

            def compose(*, plan, output_path, profile):
                stages.append("montage")
                Path(output_path).write_bytes(b"principal")
                return StudioMontageResult(
                    output_path=Path(output_path),
                    command=("ffmpeg",),
                    expected_duration=2.0,
                    generated_duration=2.0,
                    clip_count=1,
                    preparation_duration=0.2,
                    montage_duration=0.3,
                )

            montage.compose.side_effect = compose
            subtitle_service = Mock()

            def prepare(*, video_path, working_directory):
                stages.append("whisper")
                subtitle_path = Path(working_directory) / "whisper.srt"
                subtitle_path.write_text(
                    "1\n00:00:00,000 --> 00:00:01,000\nTexto\n",
                    encoding="utf-8",
                )
                return SimpleNamespace(
                    subtitle_path=subtitle_path,
                    timing=object(),
                )

            subtitle_service.prepare.side_effect = prepare
            renderer = Mock()
            renderer.render.side_effect = lambda **kwargs: (
                stages.append("render")
                or StudioRenderResult(
                    source_video_path=Path("principal.mp4"),
                    source_subtitle_path=Path("whisper.srt"),
                    output_path=output_path,
                    command=("ffmpeg",),
                    expected_duration=2.0,
                    generated_duration=2.0,
                    source_had_audio=True,
                    silence_added=False,
                    music_path=Path("music.mp3"),
                    render_duration=0.4,
                )
            )

            base_subtitle_path = (
                root / "output" / "demo" / "subtitles" / "demo.srt"
            )
            render_subtitle_path = (
                root
                / "output"
                / "demo"
                / "subtitles"
                / "demo_single_line.srt"
            )
            with patch(
                "app.core.start._persist_studio_subtitle_base",
                return_value=base_subtitle_path,
            ), patch(
                "app.core.start._persist_studio_render_subtitle",
                return_value=render_subtitle_path,
            ):
                result = ejecutar_studio_montaje(
                    plan,
                    subtitle_style="single_line",
                    music_path=Path("music.mp3"),
                    intro_outro_selection=SimpleNamespace(
                        intro=object(), outro=None
                    ),
                    project=project,
                    profile_resolver=profile_resolver,
                    profile_loader=profile_loader,
                    output_path_resolver=output_resolver,
                    montage_service=montage,
                    config_manager=config_manager,
                    render_service=renderer,
                    external_subtitle_preparation_service=subtitle_service,
                )

            self.assertIsInstance(result, StudioMontageFullResult)
            principal_path = montage.compose.call_args.kwargs["output_path"]
            self.assertNotEqual(output_path, principal_path)
            self.assertEqual("montage-principal.mp4", Path(principal_path).name)
            subtitle_service.prepare.assert_called_once_with(
                video_path=principal_path,
                working_directory=ANY,
            )
            self.assertEqual(
                principal_path,
                renderer.render.call_args.kwargs["video_path"],
            )
            self.assertEqual(["montage", "whisper", "render"], stages)
            self.assertTrue(
                montage.compose.call_args.kwargs["plan"].transitions_enabled
            )
            self.assertIs(
                self.subtitle_profile,
                renderer.render.call_args.kwargs["subtitle_profile"],
            )
            self.assertEqual(Path("music.mp3"), renderer.render.call_args.kwargs["music_path"])
            self.assertEqual(
                render_subtitle_path,
                renderer.render.call_args.kwargs["subtitle_path"],
            )
            for clip in plan.clips:
                self.assertEqual(
                    source_hashes[clip.path],
                    hashlib.sha256(clip.path.read_bytes()).digest(),
                )

    def test_full_montage_requires_a_studio_subtitle_style(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = self._plan(
                root,
                transitions_enabled=True,
                clip_count=2,
            )
            dependencies = self._dependencies(root)
            montage = Mock()

            with self.assertRaisesRegex(ValueError, "estilo de subtitulos"):
                ejecutar_studio_montaje(
                    plan,
                    project=dependencies[0],
                    profile_resolver=dependencies[1],
                    profile_loader=dependencies[2],
                    output_path_resolver=dependencies[3],
                    montage_service=montage,
                )
            montage.compose.assert_not_called()

    def test_full_montage_without_subtitles_skips_whisper_and_srt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = self._plan(
                root,
                transitions_enabled=True,
                clip_count=2,
            )
            (
                project,
                profile_resolver,
                profile_loader,
                output_resolver,
                config_manager,
                output_path,
            ) = self._dependencies(root)
            montage = Mock()
            stages = []

            def compose(*, plan, output_path, profile):
                stages.append("montage")
                Path(output_path).write_bytes(b"principal")
                return StudioMontageResult(
                    output_path=Path(output_path),
                    command=("ffmpeg",),
                    expected_duration=2.0,
                    generated_duration=2.0,
                    clip_count=1,
                    preparation_duration=0.2,
                    montage_duration=0.3,
                )

            montage.compose.side_effect = compose
            subtitle_service = Mock()
            renderer = Mock()
            renderer.render.side_effect = lambda **kwargs: (
                stages.append("render")
                or StudioRenderResult(
                    source_video_path=Path("principal.mp4"),
                    source_subtitle_path=None,
                    output_path=output_path,
                    command=("ffmpeg",),
                    expected_duration=2.0,
                    generated_duration=2.0,
                    source_had_audio=True,
                    silence_added=False,
                    music_path=Path("music.mp3"),
                    render_duration=0.4,
                    intro_outro_duration=0.1,
                )
            )

            result = ejecutar_studio_montaje(
                plan,
                subtitles_enabled=False,
                music_path=Path("music.mp3"),
                intro_outro_selection=SimpleNamespace(
                    intro=object(),
                    outro=None,
                ),
                project=project,
                profile_resolver=profile_resolver,
                profile_loader=profile_loader,
                output_path_resolver=output_resolver,
                montage_service=montage,
                config_manager=config_manager,
                render_service=renderer,
                external_subtitle_preparation_service=subtitle_service,
            )

        self.assertIsInstance(result, StudioMontageFullResult)
        self.assertEqual(["montage", "render"], stages)
        self.assertTrue(
            montage.compose.call_args.kwargs["plan"].transitions_enabled
        )
        config_manager.get_subtitle_profile.assert_not_called()
        subtitle_service.prepare.assert_not_called()
        render_kwargs = renderer.render.call_args.kwargs
        self.assertNotIn("subtitle_path", render_kwargs)
        self.assertNotIn("subtitle_profile", render_kwargs)
        self.assertEqual(Path("music.mp3"), render_kwargs["music_path"])
        self.assertNotIn("subtitle_timing", render_kwargs)
        self.assertFalse(
            (root / "output" / "demo" / "subtitles" / "demo.srt").exists()
        )

    def test_full_montage_summary_includes_common_studio_stages(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = self._plan(
                root,
                transitions_enabled=True,
                clip_count=2,
            )
            montage_result = StudioMontageResult(
                output_path=root / "principal.mp4",
                command=("ffmpeg",),
                expected_duration=2.0,
                generated_duration=2.0,
                clip_count=2,
                preparation_duration=0.2,
                normalization_duration=0.3,
                montage_duration=0.4,
                normalized_clip_count=1,
            )
            render_result = StudioRenderResult(
                source_video_path=root / "principal.mp4",
                source_subtitle_path=root / "whisper.srt",
                output_path=root / "final.mp4",
                command=("ffmpeg",),
                expected_duration=2.0,
                generated_duration=2.0,
                source_had_audio=True,
                silence_added=False,
                music_path=None,
                generated_subtitle_path=root / "subtitles" / "final.srt",
                subtitle_preparation_duration=0.5,
                render_duration=0.6,
                intro_outro_duration=0.7,
            )
            result = StudioMontageFullResult(montage_result, render_result)
            options = {
                "project_name": "demo",
                "profile_id": "studio_instagram",
                "profile_platform": "instagram",
                "studio_montage_plan": plan,
                "subtitle_config": "single_line",
                "studio_subtitles_enabled": True,
                "studio_music_path": None,
                "intro_outro_selection": SimpleNamespace(intro=object(), outro=None),
            }
            with patch("app.managers.pipeline_summary.ProgressLogger.info") as logger:
                main._print_studio_montage_summary(options, result, 2.7)

        rendered = logger.call_args.args[0]
        for label in (
            "Subtítulos", "Estilo", "Música", "Intro / Outro", "SRT",
            "Preparacion clips", "Normalizacion clips", "Montaje de videos",
            "Preparación subtítulos", "Render STUDIO", "Intro / Outro",
        ):
            self.assertIn(label, rendered)
        self.assertNotIn("\u00c3", rendered)
        self.assertIn("2.70 s", rendered)

    def test_full_montage_summary_without_subtitles_omits_srt_stages(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = self._plan(root)
            montage_result = StudioMontageResult(
                output_path=root / "principal.mp4",
                command=("ffmpeg",),
                expected_duration=2.0,
                generated_duration=2.0,
                clip_count=2,
                preparation_duration=0.2,
                montage_duration=0.4,
            )
            render_result = StudioRenderResult(
                source_video_path=root / "principal.mp4",
                source_subtitle_path=None,
                output_path=root / "final.mp4",
                command=("ffmpeg",),
                expected_duration=2.0,
                generated_duration=2.0,
                source_had_audio=True,
                silence_added=False,
                music_path=Path("music.mp3"),
                render_duration=0.6,
                intro_outro_duration=0.7,
            )
            result = StudioMontageFullResult(montage_result, render_result)
            options = {
                "project_name": "demo",
                "profile_id": "studio_instagram",
                "profile_platform": "instagram",
                "studio_montage_plan": plan,
                "subtitle_config": "",
                "studio_subtitles_enabled": False,
                "studio_music_path": "music.mp3",
                "intro_outro_selection": SimpleNamespace(
                    intro=object(),
                    outro=None,
                ),
            }
            with patch("app.managers.pipeline_summary.ProgressLogger.info") as logger:
                main._print_studio_montage_summary(options, result, 1.7)

        rendered = logger.call_args.args[0]
        self.assertIn("Subtítulos", rendered)
        self.assertIn("No", rendered)
        self.assertIn("Música", rendered)
        self.assertIn("Intro / Outro", rendered)
        self.assertIn("Render STUDIO", rendered)
        self.assertNotIn("Estilo", rendered)
        self.assertNotIn("SRT", rendered)
        self.assertNotIn("Preparación subtítulos", rendered)
        self.assertNotIn("\u00c3", rendered)

    def test_solo_montage_keeps_direct_output_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = self._plan(root, StudioMontageMode.SOLO_MONTAJE)
            dependencies = self._dependencies(root)
            montage = Mock()
            expected = Mock()
            montage.compose.return_value = expected

            result = ejecutar_studio_montaje(
                plan,
                project=dependencies[0],
                profile_resolver=dependencies[1],
                profile_loader=dependencies[2],
                output_path_resolver=dependencies[3],
                montage_service=montage,
            )

        self.assertIs(expected, result)
        self.assertEqual(
            dependencies[5],
            montage.compose.call_args.kwargs["output_path"],
        )

    def test_full_montage_cli_reuses_studio_options_after_the_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = self._plan(root)
            profile_loader = Mock()
            profile_loader.load.return_value = self.profile
            controller = RunController(studio_profile_loader=profile_loader)
            controller.select_profile = Mock(return_value={
                "profile_key": self.profile_key,
            })
            controller.select_studio_input_mode = Mock(
                return_value="montaje_videos"
            )
            controller.select_studio_montage_plan = Mock(return_value=plan)
            controller.select_studio_montage_subtitle_options = Mock(
                return_value=(True, "word_by_word")
            )
            controller.select_studio_music = Mock(return_value=Path("music.mp3"))
            intro_outro = SimpleNamespace(intro=object(), outro=object())
            controller.select_studio_intro_outro = Mock(return_value=intro_outro)
            controller.ask_project_name = Mock(return_value="demo")
            controller.ask_clear_output = Mock(return_value=False)

            options = controller._run_studio()

        self.assertEqual("word_by_word", options["subtitle_config"])
        self.assertTrue(options["studio_subtitles_enabled"])
        self.assertEqual("music.mp3", options["studio_music_path"])
        self.assertIs(intro_outro, options["intro_outro_selection"])
        controller.select_studio_montage_subtitle_options.assert_called_once_with(
            self.profile_key
        )
        controller.select_studio_music.assert_called_once_with()
        controller.select_studio_intro_outro.assert_called_once_with()

    def test_solo_montage_does_not_offer_subtitle_options(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = self._plan(root, StudioMontageMode.SOLO_MONTAJE)
            profile_loader = Mock()
            profile_loader.load.return_value = self.profile
            controller = RunController(studio_profile_loader=profile_loader)
            controller.select_profile = Mock(return_value={
                "profile_key": self.profile_key,
            })
            controller.select_studio_input_mode = Mock(
                return_value="montaje_videos"
            )
            controller.select_studio_montage_plan = Mock(return_value=plan)
            controller.select_studio_montage_subtitle_options = Mock()
            controller.select_studio_music = Mock()
            controller.select_studio_intro_outro = Mock()
            controller.ask_project_name = Mock(return_value="demo")
            controller.ask_clear_output = Mock(return_value=False)

            options = controller._run_studio()

        self.assertEqual("", options["subtitle_config"])
        self.assertIsNone(options["studio_subtitles_enabled"])
        controller.select_studio_montage_subtitle_options.assert_not_called()
        controller.select_studio_music.assert_not_called()
        controller.select_studio_intro_outro.assert_not_called()

    def test_montage_subtitle_prompt_no_skips_style_selection(self):
        controller = RunController()
        controller._print = Mock()
        controller._select_from_list = Mock(return_value=False)

        enabled, style = controller.select_studio_montage_subtitle_options(
            self.profile_key
        )

        self.assertFalse(enabled)
        self.assertEqual("", style)
        self.assertEqual(
            [
                "\nSUBTÍTULOS\n",
                "1. Sí",
                "2. No",
            ],
            [call.args[0] for call in controller._print.call_args_list],
        )

    def test_montage_subtitle_prompt_yes_shows_styles(self):
        controller = RunController()
        controller._print = Mock()
        controller._select_from_list = Mock(
            side_effect=(
                True,
                "subtitulo_studio_instagram_palabra_por_palabra",
            )
        )

        enabled, style = controller.select_studio_montage_subtitle_options(
            self.profile_key
        )

        self.assertTrue(enabled)
        self.assertEqual(
            "subtitulo_studio_instagram_palabra_por_palabra",
            style,
        )
        self.assertIn(
            "\nESTILO DE SUBTÍTULOS\n",
            [call.args[0] for call in controller._print.call_args_list],
        )


    def test_design_montage_uses_its_declared_style_without_style_selector(self):
        profile_key = ProfileKey.for_component(
            "studio",
            "instagram",
            family="design",
            profile_id="studio_instagram_design_modo_conciencia_reels",
        )
        controller = RunController()
        controller._print = Mock()
        controller._select_from_list = Mock(return_value=True)

        enabled, style = controller.select_studio_montage_subtitle_options(
            profile_key
        )

        self.assertTrue(enabled)
        self.assertEqual("word_by_word", style)
        controller._select_from_list.assert_called_once_with((True, False))
        self.assertNotIn(
            "ESTILO DE SUBTÍTULOS",
            [call.args[0] for call in controller._print.call_args_list],
        )


@unittest.skipUnless(
    shutil.which("ffmpeg") and shutil.which("ffprobe"),
    "FFmpeg y FFprobe son obligatorios para el E2E de MONTAJE COMPLETO.",
)
class StudioMontagePhase4RealFFmpegTest(unittest.TestCase):

    profile_key = ProfileKey.for_component("studio", "instagram")

    @staticmethod
    def _source(path, color, frequency):
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c={color}:s=160x284:r=24:d=0.6",
            "-f", "lavfi", "-i",
            f"sine=frequency={frequency}:sample_rate=48000:duration=0.6",
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-video_track_timescale", "30",
            "-c:a", "aac", "-ar", "48000", "-ac", "2",
            str(path),
        ], capture_output=True, check=True)

    @staticmethod
    def _profile():
        return SimpleNamespace(
            width=160,
            height=284,
            fps=24,
            codec="libx264",
            preset="ultrafast",
            crf=18,
            pixel_format="yuv420p",
            movflags="+faststart",
            audio_codec="aac",
            audio_bitrate="192k",
            audio_sample_rate=48000,
            audio_channels=2,
            max_duration_difference=0.25,
            transition_duration=0.50,
            music=SimpleNamespace(
                volume=0.10,
                loop_shorter=True,
                limiter_limit=0.95,
            ),
        )

    def test_complete_montage_renders_one_principal_and_persists_one_srt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clips = root / "clips"
            clips.mkdir()
            first = clips / "first.mp4"
            second = clips / "second.mp4"
            self._source(first, "red", 440)
            self._source(second, "blue", 550)
            source_hashes = {
                path: hashlib.sha256(path.read_bytes()).digest()
                for path in (first, second)
            }
            plan = StudioMontagePlan(
                profile_key=self.profile_key,
                mode=StudioMontageMode.MONTAJE_COMPLETO,
                transitions_enabled=True,
                clips=(
                    StudioMontageClip(2, second, second.name),
                    StudioMontageClip(1, first, first.name),
                ),
            )
            profile = self._profile()
            profile_resolver = Mock()
            profile_resolver.load.return_value = {"studio": {}}
            profile_loader = Mock()
            profile_loader.load.return_value = profile
            output_path = root / "output" / "demo" / "video" / "demo.mp4"
            output_resolver = Mock()
            output_resolver.resolve.return_value = output_path
            subtitle_profile = SubtitleProfileResolver().load(
                SubtitleProfileKey.for_profile(self.profile_key, "single_line")
            )
            config_manager = Mock()
            config_manager.get_subtitle_profile.return_value = subtitle_profile
            subtitle_service = Mock()

            def prepare(*, video_path, working_directory):
                subtitle_path = Path(working_directory) / "whisper.srt"
                subtitle_path.write_text(
                    "1\n00:00:00,000 --> 00:00:00,900\nMontaje completo\n",
                    encoding="utf-8",
                )
                return SimpleNamespace(subtitle_path=subtitle_path, timing=None)

            subtitle_service.prepare.side_effect = prepare
            result = ejecutar_studio_montaje(
                plan,
                subtitle_style="single_line",
                project=Mock(),
                profile_resolver=profile_resolver,
                profile_loader=profile_loader,
                output_path_resolver=output_resolver,
                config_manager=config_manager,
                external_subtitle_preparation_service=subtitle_service,
            )

            self.assertIsInstance(result, StudioMontageFullResult)
            self.assertTrue(output_path.is_file())
            self.assertTrue(
                (root / "output" / "demo" / "subtitles" / "demo.srt").is_file()
            )
            subtitle_service.prepare.assert_called_once()
            principal_path = subtitle_service.prepare.call_args.kwargs["video_path"]
            self.assertFalse(Path(principal_path).exists())
            self.assertFalse(output_path.with_name("montage-principal.mp4").exists())
            decoded = subprocess.run([
                "ffmpeg", "-v", "error", "-i", str(output_path),
                "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-",
            ], capture_output=True, text=True, check=False)
            self.assertEqual(0, decoded.returncode, decoded.stderr)
            self.assertLessEqual(
                abs(
                    result.generated_duration
                    - result.montage_result.expected_duration
                ),
                0.25,
            )
            for path, digest in source_hashes.items():
                self.assertEqual(digest, hashlib.sha256(path.read_bytes()).digest())

    def test_complete_montage_without_subtitles_renders_without_srt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clips = root / "clips"
            clips.mkdir()
            first = clips / "first.mp4"
            second = clips / "second.mp4"
            self._source(first, "red", 440)
            self._source(second, "blue", 550)
            plan = StudioMontagePlan(
                profile_key=self.profile_key,
                mode=StudioMontageMode.MONTAJE_COMPLETO,
                transitions_enabled=True,
                clips=(
                    StudioMontageClip(1, first, first.name),
                    StudioMontageClip(2, second, second.name),
                ),
            )
            profile_resolver = Mock()
            profile_resolver.load.return_value = {"studio": {}}
            profile_loader = Mock()
            profile_loader.load.return_value = self._profile()
            output_path = root / "output" / "demo" / "video" / "demo.mp4"
            output_resolver = Mock()
            output_resolver.resolve.return_value = output_path
            subtitle_service = Mock()

            result = ejecutar_studio_montaje(
                plan,
                subtitles_enabled=False,
                project=Mock(),
                profile_resolver=profile_resolver,
                profile_loader=profile_loader,
                output_path_resolver=output_resolver,
                external_subtitle_preparation_service=subtitle_service,
            )

            self.assertIsInstance(result, StudioMontageFullResult)
            self.assertTrue(output_path.is_file())
            self.assertIsNone(result.render_result.source_subtitle_path)
            self.assertIsNone(result.render_result.generated_subtitle_path)
            self.assertFalse((root / "output" / "demo" / "subtitles").exists())
            subtitle_service.prepare.assert_not_called()
            graph = result.render_result.command[
                result.render_result.command.index("-filter_complex") + 1
            ]
            self.assertNotIn("subtitles=", graph)
            decoded = subprocess.run([
                "ffmpeg", "-v", "error", "-i", str(output_path),
                "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-",
            ], capture_output=True, text=True, check=False)
            self.assertEqual(0, decoded.returncode, decoded.stderr)
            self.assertLessEqual(
                abs(
                    result.generated_duration
                    - result.montage_result.expected_duration
                ),
                0.25,
            )
