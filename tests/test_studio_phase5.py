from dataclasses import replace
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import main
from app.controllers.interaction.contracts import (
    StudioOperationalSelection,
    StudioProfileSelection,
    StudioSubtitleSelection,
)
from app.controllers.run_controller import RunController
from app.core.start import ejecutar_studio, iniciar
from app.modules.studio import (
    StudioOutputPathResolver,
    StudioProfileLoader,
    StudioRenderService,
)
from app.modules.video.intro_outro import (
    IntroOutroCatalog,
    IntroOutroComposer,
    IntroOutroComposition,
    IntroOutroMediaInfo,
    IntroOutroPlan,
    IntroOutroSelection,
)
from app.shared.profile_identity import OperationalProfileKey
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


class StudioPhase5Test(unittest.TestCase):

    def setUp(self):
        self.profile_key = OperationalProfileKey(
            "studio", "instagram", "studio_instagram"
        )
        self.profile = _load_studio_profile(self.profile_key)
        self.subtitle_profile = SubtitleProfileResolver().load(
            SubtitleProfileKey(
                "studio",
                "instagram",
                "subtitulo_studio_instagram_linea_unica",
                "estandar",
            )
        )

    @staticmethod
    def _selection(path, position):
        return IntroOutroSelection(Path(path), position)

    @staticmethod
    def _media_info(duration=1.0, width=1080, height=1920, audio=True):
        return IntroOutroMediaInfo(
            duration=duration,
            width=width,
            height=height,
            fps=30.0,
            time_base="1/15360",
            sample_aspect_ratio="1:1",
            pixel_format="yuv420p",
            video_codec="h264",
            audio_codec="aac" if audio else None,
            audio_sample_rate=48000 if audio else None,
            audio_channels=2 if audio else None,
        )

    def test_none_keeps_phase_four_controller_contract(self):
        controller = RunController()
        subtitle_key = controller.subtitle_profile_resolver.discover_profiles_for_family(
            "studio", "instagram", "estandar",
        )[0].key
        with patch.object(
            controller, "select_visual_pipeline", return_value="studio"
        ), patch.object(
            controller,
            "_select_studio_profile_selection",
            return_value=StudioProfileSelection(
                operational=StudioOperationalSelection(
                    self.profile_key,
                    self.profile,
                ),
                subtitle=StudioSubtitleSelection(subtitle_key, False),
            ),
        ), patch.object(
            controller,
            "select_studio_input_mode",
            return_value="srt_video",
        ), patch.object(
            controller,
            "select_studio_input_files",
            return_value=SimpleNamespace(
                video_path=Path("input/studio/srt_video/source.mp4"),
                subtitle_path=Path("input/studio/srt_video/source.srt"),
            ),
        ), patch.object(
            controller, "select_studio_music", return_value=None
        ), patch.object(
            controller, "select_studio_intro_outro", return_value=None
        ), patch.object(
            controller, "ask_project_name", return_value="studio project"
        ), patch.object(
            controller, "ask_clear_output", return_value=False
        ):
            options = controller.run()

        self.assertIsNone(options["intro_outro_selection"])

    def test_studio_menu_selects_intro_outro_and_allows_same_asset(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            intro = root / "instagram" / "intro"
            outro = root / "instagram" / "outro"
            intro.mkdir(parents=True)
            outro.mkdir(parents=True)
            intro_asset = intro / "brand.mp4"
            outro_asset = outro / "brand.mp4"
            intro_asset.touch()
            outro_asset.touch()
            controller = RunController(
                intro_outro_catalog=IntroOutroCatalog(root)
            )
            with patch("builtins.input", side_effect=("4", "1", "1")):
                plan = controller.select_studio_intro_outro(self.profile_key)

        self.assertEqual(intro_asset, plan.intro.asset_path)
        self.assertEqual(outro_asset, plan.outro.asset_path)

    def test_studio_menu_selects_single_positions_dynamically(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            intro_directory = root / "instagram" / "intro"
            outro_directory = root / "instagram" / "outro"
            intro_directory.mkdir(parents=True)
            outro_directory.mkdir(parents=True)
            first = intro_directory / "a.mp4"
            second = intro_directory / "b.MP4"
            outro_asset = outro_directory / "c.mp4"
            first.touch()
            second.touch()
            outro_asset.touch()
            controller = RunController(
                intro_outro_catalog=IntroOutroCatalog(root)
            )
            with patch("builtins.input", side_effect=("2", "2")):
                intro = controller.select_studio_intro_outro(self.profile_key)
            with patch("builtins.input", side_effect=("3", "1")):
                outro_plan = controller.select_studio_intro_outro(self.profile_key)

        self.assertEqual(second, intro.intro.asset_path)
        self.assertIsNone(intro.outro)
        self.assertEqual(outro_asset, outro_plan.outro.asset_path)
        self.assertIsNone(outro_plan.intro)

    def test_requested_selection_without_assets_fails_fast(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = RunController(
                intro_outro_catalog=IntroOutroCatalog(directory)
            )
            with patch("builtins.input", return_value="2"), self.assertRaisesRegex(
                FileNotFoundError, "No hay archivos MP4"
            ):
                controller.select_studio_intro_outro(self.profile_key)

    def test_main_and_start_transport_structured_plan(self):
        intro = self._selection(
            "assets/videos/intro_outro/instagram/intro/a.mp4",
            "intro",
        )
        plan = IntroOutroPlan(intro=intro)
        options = {
            "profile_component": "studio",
            "profile_platform": "instagram",
            "profile_id": "studio_instagram",
            "voice_config": "",
            "music_category": None,
            "project_name": "studio intro outro",
            "visual_pipeline": "studio",
            "script_source": "external",
            "design_target": "",
            "pipeline_mode": "studio",
            "studio_music_path": None,
            "studio_input_mode": "srt_video",
            "intro_outro_selection": plan,
            "clear_output": False,
        }
        with patch.dict("os.environ", {}, clear=True), patch(
            "main.RunController"
        ) as controller, patch("main.iniciar") as start:
            controller.return_value.run.return_value = options
            self.assertEqual(0, main.main())
        start.assert_called_once()
        request = start.call_args.kwargs["request"]
        self.assertIs(plan, request.route.intro_outro_plan)
        self.assertEqual("srt_video", request.route.input_mode.value)
        self.assertEqual({"request"}, set(start.call_args.kwargs))

        with patch("app.core.start.ejecutar_studio") as studio, patch(
            "app.core.start.ProjectManager"
        ) as projects:
            iniciar(request=request)
        studio.assert_called_once()
        self.assertIs(plan, studio.call_args.kwargs["intro_outro_selection"])
        self.assertIsNone(studio.call_args.kwargs["music_path"])
        self.assertEqual("srt_video", studio.call_args.kwargs["input_mode"])
        projects.assert_called_once_with(project_name="studio intro outro")

    def test_phase_two_transports_plan_to_project_output_and_renderer(self):
        plan = IntroOutroPlan(
            intro=self._selection("intro.mp4", "intro"),
            outro=self._selection("outro.mp4", "outro"),
        )
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
        with patch(
            "app.core.start._persist_studio_subtitle_base",
            return_value=Path("output/studio/subtitles/result.srt"),
        ), patch(
            "app.core.start._persist_studio_render_subtitle",
            return_value=Path(
                "output/studio/subtitles/result_single_line.srt"
            ),
        ):
            result = ejecutar_studio(
                subtitle_profile_key=self.subtitle_profile.key,
                input_mode="srt_video",
                intro_outro_selection=plan,
                preparation_service=Mock(return_value=preparation),
                render_service=renderer,
                output_path_resolver=resolver,
                project=project,
            )
        self.assertEqual("rendered", result)
        self.assertEqual(
            {
                "profile_key": preparation.profile_key,
                "project": project,
            },
            resolver.resolve.call_args.kwargs,
        )
        self.assertIs(
            plan, renderer.render.call_args.kwargs["intro_outro_selection"]
        )

    def test_output_path_is_not_derived_from_intro_outro_assets(self):
        project = Mock()
        project.video_path.return_value = Path("output/studio/video/studio.mp4")
        self.assertEqual(
            Path("output/studio/video/studio.mp4"),
            StudioOutputPathResolver(project).resolve(self.profile_key),
        )

    def test_composer_uses_one_three_source_concat_and_normalizes_only_asset(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            main_path = root / "main.mp4"
            intro_path = root / "intro.mp4"
            outro_path = root / "outro.mp4"
            for path in (main_path, intro_path, outro_path):
                path.write_bytes(path.name.encode("ascii"))
            main_info = self._media_info(duration=4.0)
            intro_info = self._media_info(duration=1.0)
            incompatible_outro = self._media_info(
                duration=2.0, width=720, height=1280
            )
            normalized_outro = self._media_info(duration=2.0)
            probe = Mock()
            probe.inspect.side_effect = (
                main_info,
                intro_info,
                incompatible_outro,
                normalized_outro,
            )
            runner = Mock(return_value=SimpleNamespace(stderr=""))
            runner.run.return_value = SimpleNamespace(stderr="")
            validator = Mock()
            composer = IntroOutroComposer(probe, runner, validator)
            captured_sources = []
            original_writer = composer.write_concat_list

            def capture(path, sources):
                captured_sources.extend(sources)
                original_writer(path, sources)

            composer.write_concat_list = capture
            result = composer.compose(
                main_path,
                root / "final.mp4",
                IntroOutroPlan(
                    intro=self._selection(intro_path, "intro"),
                    outro=self._selection(outro_path, "outro"),
                ),
                self.profile,
                4.0,
            )

        self.assertEqual("intro", Path(captured_sources[0]).stem)
        self.assertEqual(main_path, captured_sources[1])
        self.assertIn("outro", Path(captured_sources[2]).stem)
        self.assertEqual(("outro",), result.normalized_positions)
        self.assertEqual(2, runner.run.call_count)
        concat_command = runner.run.call_args_list[-1].args[0]
        self.assertEqual("copy", concat_command[concat_command.index("-c") + 1])
        self.assertNotIn("-filter_complex", concat_command)
        self.assertEqual(7.0, result.expected_duration)

    def test_studio_validates_principal_then_composition_before_promotion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mp4"
            subtitle = root / "source.srt"
            asset = root / "intro.mp4"
            output = root / "final.mp4"
            source.touch()
            asset.touch()
            subtitle.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\nText\n",
                encoding="utf-8",
            )
            runner = Mock()

            def render(command):
                Path(command[-1]).write_bytes(b"principal")

            runner.run.side_effect = render
            validator = Mock()
            validator.validate.side_effect = (4.0, 5.0)
            composer = Mock()

            def compose(**kwargs):
                composition = root / "final.intro-outro.rendering.mp4"
                composition.write_bytes(b"composition")
                return IntroOutroComposition(
                    composition,
                    ("ffmpeg", "-c", "copy"),
                    "",
                    5.0,
                    False,
                )

            composer.compose.side_effect = compose
            service = StudioRenderService(
                runner=runner,
                probe=Mock(
                    inspect=Mock(
                        return_value=SimpleNamespace(
                            duration=4.0, has_audio=True
                        )
                    )
                ),
                output_validator=validator,
                intro_outro_composer=composer,
            )
            plan = IntroOutroPlan(
                intro=self._selection(asset, "intro")
            )
            with patch.object(
                service.style_builder, "build", return_value="style"
            ), patch(
                "app.modules.studio.render_service.SubtitleConfigLoader"
            ) as subtitle_loader, patch(
                "app.modules.studio.render_service.time.perf_counter",
                side_effect=(10.0, 13.0, 20.0, 22.0),
            ), patch(
                "app.modules.studio.render_service.ProgressLogger"
            ) as progress_logger:
                subtitle_loader.return_value.load_render_style.return_value = (
                    SimpleNamespace(offset=0.0, dynamic=False)
                )
                result = service.render(
                    source,
                    subtitle,
                    self.profile_key,
                    self.profile,
                    self.subtitle_profile,
                    output,
                    intro_outro_selection=plan,
                )
            self.assertEqual(b"composition", output.read_bytes())
            self.assertEqual(2, validator.validate.call_count)
            self.assertEqual(output, result.output_path)
            self.assertFalse(service._principal_path(output).exists())
            self.assertEqual(3.0, result.render_duration)
            self.assertEqual(2.0, result.intro_outro_duration)
            self.assertEqual(
                [
                    "RENDERIZANDO STUDIO",
                    "COMPONIENDO INTRO / OUTRO",
                ],
                [call.args[0] for call in progress_logger.start.call_args_list],
            )
            self.assertEqual(
                [
                    "RENDER STUDIO COMPLETADO",
                    "INTRO / OUTRO COMPLETADO",
                ],
                [call.args[0] for call in progress_logger.finish.call_args_list],
            )

    def test_final_collision_fails_before_render(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mp4"
            subtitle = root / "source.srt"
            asset = root / "intro.mp4"
            output = root / "final.mp4"
            for path in (source, asset, output):
                path.touch()
            subtitle.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\nText\n",
                encoding="utf-8",
            )
            runner = Mock()
            with self.assertRaises(FileExistsError):
                StudioRenderService(runner=runner).render(
                    source,
                    subtitle,
                    self.profile_key,
                    self.profile,
                    self.subtitle_profile,
                    output,
                    intro_outro_selection=IntroOutroPlan(
                        intro=self._selection(asset, "intro")
                    ),
                )
        runner.run.assert_not_called()

    def test_concat_failure_keeps_validated_principal_and_no_final(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mp4"
            subtitle = root / "source.srt"
            asset = root / "intro.mp4"
            output = root / "final.mp4"
            source.touch()
            asset.touch()
            subtitle.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\nText\n",
                encoding="utf-8",
            )
            runner = Mock()

            def render(command):
                Path(command[-1]).write_bytes(b"validated-principal")

            runner.run.side_effect = render
            composer = Mock()
            composer.compose.side_effect = RuntimeError("concat failed")
            service = StudioRenderService(
                runner=runner,
                probe=Mock(
                    inspect=Mock(
                        return_value=SimpleNamespace(
                            duration=4.0, has_audio=True
                        )
                    )
                ),
                output_validator=Mock(
                    validate=Mock(return_value=4.0)
                ),
                intro_outro_composer=composer,
            )
            with patch.object(
                service.style_builder, "build", return_value="style"
            ), patch(
                "app.modules.studio.render_service.SubtitleConfigLoader"
            ) as subtitle_loader, self.assertRaisesRegex(
                RuntimeError, "concat failed"
            ):
                subtitle_loader.return_value.load_render_style.return_value = (
                    SimpleNamespace(offset=0.0, dynamic=False)
                )
                service.render(
                    source,
                    subtitle,
                    self.profile_key,
                    self.profile,
                    self.subtitle_profile,
                    output,
                    intro_outro_selection=IntroOutroPlan(
                        intro=self._selection(asset, "intro")
                    ),
                )

            principal = service._principal_path(output)
            self.assertEqual(b"validated-principal", principal.read_bytes())
            self.assertFalse(output.exists())


@unittest.skipUnless(
    shutil.which("ffmpeg") and shutil.which("ffprobe"),
    "FFmpeg y FFprobe son obligatorios para la prueba real STUDIO Fase 5.",
)
class StudioPhase5RealFFmpegTest(unittest.TestCase):

    class _FirstAssetRng:
        @staticmethod
        def choice(values):
            return values[0]

    def setUp(self):
        self.profile_key = OperationalProfileKey(
            "studio", "instagram", "studio_instagram"
        )
        profile = _load_studio_profile(self.profile_key)
        self.profile = replace(
            profile,
            width=320,
            height=568,
            fps=12,
            preset="ultrafast",
        )
        self.subtitle_profile = SubtitleProfileResolver().load(
            SubtitleProfileKey(
                "studio",
                "instagram",
                "subtitulo_studio_instagram_linea_unica",
                "estandar",
            )
        )

    @staticmethod
    def _run(command):
        subprocess.run(command, capture_output=True, check=True)

    def _video(self, path, duration, color, size="320x568", audio=True):
        command = [
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            f"color=c={color}:s={size}:r=12:d={duration}",
        ]
        if audio:
            command.extend([
                "-f", "lavfi", "-i",
                f"sine=frequency=440:sample_rate=48000:duration={duration}",
                "-shortest",
            ])
        command.extend([
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-r", "12",
        ])
        if audio:
            command.extend(["-c:a", "aac", "-ar", "48000", "-ac", "2"])
        command.append(str(path))
        self._run(command)

    @staticmethod
    def _srt(path):
        path.write_text(
            "1\n00:00:00,100 --> 00:00:00,800\nSTUDIO FIVE\n",
            encoding="utf-8",
        )

    def _render_principal(self, root, music=None):
        source = root / "source.mp4"
        subtitle = root / "source.srt"
        self._video(source, 1.5, "black")
        self._srt(subtitle)
        result = StudioRenderService().render(
            source,
            subtitle,
            self.profile_key,
            self.profile,
            self.subtitle_profile,
            root / "principal.mp4",
            music_path=music,
        )
        return source, subtitle, result.output_path

    @staticmethod
    def _packet_payloads(path, stream):
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-select_streams", stream,
                "-show_packets", "-show_data", "-show_entries", "packet=data",
                "-of", "json", str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        payloads = []
        for packet in json.loads(result.stdout)["packets"]:
            raw = bytearray()
            for line in packet.get("data", "").splitlines():
                if ":" not in line:
                    continue
                hex_part = line.split(":", 1)[1].split("  ", 1)[0]
                raw.extend(bytes.fromhex("".join(hex_part.split())))
            payloads.append(hashlib.sha256(raw).hexdigest())
        return payloads

    def _compose(self, principal, output, intro=None, outro=None):
        return IntroOutroComposer().compose(
            principal,
            output,
            IntroOutroPlan(
                intro=(
                    IntroOutroSelection(intro, "intro")
                    if intro is not None else None
                ),
                outro=(
                    IntroOutroSelection(outro, "outro")
                    if outro is not None else None
                ),
            ),
            self.profile,
            1.5,
        )

    def test_real_intro_compatible_preserves_main_packet_payloads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, _, principal = self._render_principal(root)
            intro = root / "intro.mp4"
            self._video(intro, 0.5, "red")
            before_video = self._packet_payloads(principal, "v:0")
            before_audio = self._packet_payloads(principal, "a:0")
            intro_video_count = len(self._packet_payloads(intro, "v:0"))
            intro_audio_count = len(self._packet_payloads(intro, "a:0"))
            result = self._compose(
                principal, root / "case_a.mp4", intro=intro
            )
            final_video = self._packet_payloads(result.output_path, "v:0")
            final_audio = self._packet_payloads(result.output_path, "a:0")
            main_video = final_video[
                intro_video_count:intro_video_count + len(before_video)
            ]
            main_audio = final_audio[
                intro_audio_count:intro_audio_count + len(before_audio)
            ]

        self.assertEqual(before_audio, main_audio)
        self.assertLessEqual(
            sum(a != b for a, b in zip(before_video, main_video)),
            1,
        )

    def test_real_outro_incompatible_normalizes_only_outro(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, _, principal = self._render_principal(root)
            outro = root / "outro.mp4"
            self._video(outro, 0.5, "blue", size="160x160")
            principal_hash = hashlib.sha256(principal.read_bytes()).digest()
            result = self._compose(
                principal, root / "case_b.mp4", outro=outro
            )
            self.assertEqual(("outro",), result.normalized_positions)
            self.assertEqual(
                principal_hash,
                hashlib.sha256(principal.read_bytes()).digest(),
            )

    def test_real_both_assets_use_one_concat_and_correct_temporal_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, _, principal = self._render_principal(root)
            intro = root / "intro.mp4"
            outro = root / "outro.mp4"
            self._video(intro, 0.5, "red")
            self._video(outro, 0.5, "blue")
            result = self._compose(
                principal, root / "case_c.mp4", intro, outro
            )
            self.assertEqual("copy", result.command[result.command.index("-c") + 1])
            self.assertNotIn("-filter_complex", result.command)
            self.assertLessEqual(abs(result.expected_duration - 2.5), 0.05)

    def test_real_silent_assets_receive_audio_without_altering_main(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, _, principal = self._render_principal(root)
            intro = root / "silent.mp4"
            self._video(intro, 0.5, "green", audio=False)
            principal_hash = hashlib.sha256(principal.read_bytes()).digest()
            result = self._compose(
                principal, root / "case_d.mp4", intro=intro
            )
            self.assertEqual(("intro",), result.normalized_positions)
            self.assertEqual(
                principal_hash,
                hashlib.sha256(principal.read_bytes()).digest(),
            )

    def test_real_complete_combination_preserves_all_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            music = root / "music.wav"
            self._run([
                "ffmpeg", "-y", "-f", "lavfi", "-i",
                "sine=frequency=880:sample_rate=48000:duration=0.3",
                "-c:a", "pcm_s16le", str(music),
            ])
            source = root / "source.mp4"
            subtitle = root / "source.srt"
            self._video(source, 1.5, "black")
            self._srt(subtitle)
            intro = root / "intro.mp4"
            outro = root / "outro.mp4"
            self._video(intro, 0.5, "red")
            self._video(outro, 0.5, "blue")
            protected = {
                path: hashlib.sha256(path.read_bytes()).digest()
                for path in (source, subtitle, music, intro, outro)
            }
            service = StudioRenderService()
            result = service.render(
                source,
                subtitle,
                self.profile_key,
                self.profile,
                self.subtitle_profile,
                root / "case_e.mp4",
                music_path=music,
                intro_outro_selection=IntroOutroPlan(
                    intro=IntroOutroSelection(intro, "intro"),
                    outro=IntroOutroSelection(outro, "outro"),
                ),
            )
            probe = subprocess.run(
                [
                    "ffprobe", "-v", "error", "-show_entries",
                    "stream=codec_type,codec_name,pix_fmt,sample_rate,channels",
                    "-of", "json", str(result.output_path),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            streams = json.loads(probe.stdout)["streams"]
            for path, digest in protected.items():
                self.assertEqual(digest, hashlib.sha256(path.read_bytes()).digest())

        self.assertEqual("copy", result.intro_outro_command[
            result.intro_outro_command.index("-c") + 1
        ])
        self.assertLessEqual(abs(result.generated_duration - 2.5), 0.2)
        self.assertTrue(any(
            stream.get("codec_type") == "video"
            and stream.get("codec_name") == "h264"
            and stream.get("pix_fmt") == "yuv420p"
            for stream in streams
        ))
        self.assertTrue(any(
            stream.get("codec_type") == "audio"
            and stream.get("codec_name") == "aac"
            and stream.get("sample_rate") == "48000"
            and stream.get("channels") == 2
            for stream in streams
        ))


if __name__ == "__main__":
    unittest.main()
