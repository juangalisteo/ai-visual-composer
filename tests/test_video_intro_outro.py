import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import main as app_main
from app.controllers.run_controller import RunController
from app.core.execution_request import (
    ApplicationExecutionRequest,
    StandardExecutionRequest,
)
from app.modules.video.intro_outro import (
    IntroOutroCatalog,
    IntroOutroComposer,
    IntroOutroComposition,
    IntroOutroMediaInfo,
    IntroOutroMediaProbe,
    IntroOutroPlan,
    IntroOutroSelection,
)
from app.modules.video.video_build_context import VideoBuildArtifacts
from app.modules.video.video_render_service import VideoRenderService
from app.shared.operational_error import OperationalError
from app.shared.profile_identity import OperationalProfileKey
from tests.test_menu_helpers import MenuAnswers


class IntroOutroTest(unittest.TestCase):

    def make_info(
        self,
        duration=2.0,
        width=1080,
        height=1920,
        fps=30.0,
        time_base="1/15360",
        sample_aspect_ratio="1:1",
        pixel_format="yuv420p",
        video_codec="h264",
        audio_codec="aac",
        audio_sample_rate=48000,
        audio_channels=2,
    ):
        return IntroOutroMediaInfo(
            duration=duration,
            width=width,
            height=height,
            fps=fps,
            time_base=time_base,
            sample_aspect_ratio=sample_aspect_ratio,
            pixel_format=pixel_format,
            video_codec=video_codec,
            audio_codec=audio_codec,
            audio_sample_rate=audio_sample_rate,
            audio_channels=audio_channels,
        )

    def make_config(self):
        return SimpleNamespace(
            width=1080,
            height=1920,
            fps=30,
            pixel_format="yuv420p",
            codec="libx264",
            preset="slow",
            crf=16,
            audio_codec="aac",
            audio_bitrate="192k",
            movflags="+faststart",
            validation=SimpleNamespace(
                max_duration_difference=0.2,
            ),
        )

    def test_catalog_lists_only_real_mp4_files_dynamically(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            intro_directory = root / "vertical" / "intro"
            outro_directory = root / "vertical" / "outro"
            intro_directory.mkdir(parents=True)
            outro_directory.mkdir(parents=True)
            (intro_directory / "Zulu.MP4").write_bytes(b"z")
            (intro_directory / "alpha.mp4").write_bytes(b"a")
            (outro_directory / "outro.mp4").write_bytes(b"o")
            (root / "ignored.mov").write_bytes(b"m")
            (root / "flat_legacy.mp4").write_bytes(b"legacy")
            (intro_directory / "folder.mp4").mkdir()

            assets = IntroOutroCatalog(root).discover("vertical", "intro")

        self.assertEqual(
            ["alpha.mp4", "Zulu.MP4"],
            [path.name for path in assets],
        )

    def test_catalog_discovers_only_the_requested_position(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            intro = root / "vertical" / "intro"
            outro = root / "vertical" / "outro"
            intro.mkdir(parents=True)
            outro.mkdir(parents=True)
            (intro / "canal_01.mp4").write_bytes(b"intro")
            (outro / "canal_01.mp4").write_bytes(b"outro")

            catalog = IntroOutroCatalog(root)

            self.assertEqual(
                [intro / "canal_01.mp4"],
                list(catalog.discover("vertical", "intro")),
            )
            self.assertEqual(
                [outro / "canal_01.mp4"],
                list(catalog.discover("vertical", "outro")),
            )

    def test_catalog_never_mixes_format_assets(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            vertical_intro = root / "vertical" / "intro"
            vertical_outro = root / "vertical" / "outro"
            horizontal_intro = root / "horizontal" / "intro"
            horizontal_outro = root / "horizontal" / "outro"
            for directory in (
                vertical_intro,
                vertical_outro,
                horizontal_intro,
                horizontal_outro,
            ):
                directory.mkdir(parents=True)
            (vertical_intro / "vertical-intro.mp4").write_bytes(b"i")
            (vertical_outro / "vertical-outro.mp4").write_bytes(b"o")
            (horizontal_intro / "horizontal-intro.mp4").write_bytes(b"y")
            (horizontal_outro / "horizontal-outro.mp4").write_bytes(b"u")
            catalog = IntroOutroCatalog(root)

            self.assertEqual(
                [vertical_intro / "vertical-intro.mp4"],
                list(catalog.discover("vertical", "intro")),
            )
            self.assertEqual(
                [horizontal_intro / "horizontal-intro.mp4"],
                list(catalog.discover("horizontal", "intro")),
            )
            self.assertEqual(
                [vertical_outro / "vertical-outro.mp4"],
                list(catalog.discover("vertical", "outro")),
            )
            self.assertEqual(
                [horizontal_outro / "horizontal-outro.mp4"],
                list(catalog.discover("horizontal", "outro")),
            )

    def test_catalog_accepts_a_future_format_from_structure_only(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            future_intro = root / "test_format" / "intro"
            future_intro.mkdir(parents=True)
            asset = future_intro / "future.mp4"
            asset.write_bytes(b"future")

            assets = IntroOutroCatalog(root).discover("test_format", "intro")

        self.assertEqual([asset], list(assets))

    def test_catalog_rejects_an_invalid_position(self):
        with self.assertRaisesRegex(ValueError, "intro u outro"):
            IntroOutroCatalog().discover("vertical", "apertura")

    def test_menu_fails_fast_when_selected_position_is_empty(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            catalog = IntroOutroCatalog(temporary_directory)
            controller = RunController(
                intro_outro_catalog=catalog
            )

            answers = MenuAnswers("SOLO INTRO")
            with patch(
                "builtins.input",
                side_effect=answers.input,
            ), patch(
                "builtins.print",
                side_effect=answers.print,
            ), self.assertRaisesRegex(
                OperationalError,
                "vertical/intro/",
            ):
                controller.select_intro_outro("vertical")

    def test_menu_fails_fast_for_an_empty_outro_without_using_intro_assets(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            intro_directory = root / "vertical" / "intro"
            intro_directory.mkdir(parents=True)
            (intro_directory / "intro.mp4").write_bytes(b"intro")
            controller = RunController(
                intro_outro_catalog=IntroOutroCatalog(root)
            )

            answers = MenuAnswers("SOLO OUTRO")
            with patch("builtins.input", side_effect=answers.input), patch(
                "builtins.print", side_effect=answers.print
            ), self.assertRaisesRegex(
                OperationalError,
                "vertical/outro/",
            ):
                controller.select_intro_outro("vertical")

    def test_menu_no_keeps_intro_outro_disabled(self):
        catalog = Mock()
        controller = RunController(
            intro_outro_catalog=catalog
        )

        answers = MenuAnswers("NINGUNO")
        with patch(
            "builtins.input",
            side_effect=answers.input,
        ), patch.object(controller, "_print", side_effect=answers.write):
            selection = controller.select_intro_outro("vertical")

        self.assertIsNone(selection)
        catalog.discover.assert_not_called()

    def test_menu_selects_position_specific_assets_for_both_sides(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            intro_directory = root / "vertical" / "intro"
            outro_directory = root / "vertical" / "outro"
            intro_directory.mkdir(parents=True)
            outro_directory.mkdir(parents=True)
            first = intro_directory / "brand opening.mp4"
            second = intro_directory / "second intro.mp4"
            outro = outro_directory / "closing reel.mp4"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            outro.write_bytes(b"outro")
            controller = RunController(
                intro_outro_catalog=IntroOutroCatalog(root)
            )

            answers = MenuAnswers(
                "INTRO + OUTRO",
                "second intro.mp4",
                "closing reel.mp4",
            )
            with patch(
                "builtins.input",
                side_effect=answers.input,
            ), patch.object(controller, "_print", side_effect=answers.write):
                plan = controller.select_intro_outro("vertical")

        self.assertEqual(second, plan.intro.asset_path)
        self.assertEqual("intro", plan.intro.position)
        self.assertEqual(outro, plan.outro.asset_path)
        self.assertEqual("outro", plan.outro.position)

    def test_main_transports_selection_without_environment_fallback(self):
        selection = IntroOutroSelection(
            Path("assets/videos/intro_outro/vertical/intro/custom.mp4"),
            "intro",
        )
        plan = IntroOutroPlan(intro=selection)
        controller_request = ApplicationExecutionRequest(
            project_name="project",
            overwrite_project=False,
            operational_profile_key=OperationalProfileKey(
                "video",
                "vertical",
                "video_vertical",
            ),
            subtitle_profile_key=None,
            route=StandardExecutionRequest(
                pipeline_mode="full",
                visual_pipeline="video",
                script_source="generated",
                voice_config_id="masculina",
                music_category=None,
                overlays_mode="off",
                intro_outro_plan=plan,
            ),
        )

        with patch.dict(
            "os.environ",
            {},
            clear=True,
        ), patch(
            "main.RunController"
        ) as controller_class, patch(
            "main.run_application"
        ) as run_application_mock:
            controller_class.return_value.run.return_value = controller_request
            app_main.main()

        run_application_mock.assert_called_once()
        request = run_application_mock.call_args.kwargs["request"]
        self.assertIs(plan, request.route.intro_outro_plan)
        self.assertEqual({"request"}, set(run_application_mock.call_args.kwargs))

    def test_compatible_asset_uses_stream_copy_and_intro_is_first(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            main_path = root / "main.rendering.mp4"
            asset_path = root / "arbitrary brand.mp4"
            final_path = root / "final.mp4"
            main_path.write_bytes(b"main")
            asset_path.write_bytes(b"asset")
            main_info = self.make_info(duration=4.0)
            asset_info = self.make_info(duration=2.0)
            probe = Mock()
            probe.inspect.side_effect = [main_info, asset_info]
            runner = Mock()
            runner.run.return_value = SimpleNamespace(stderr="")
            validator = Mock()
            composer = IntroOutroComposer(
                probe=probe,
                runner=runner,
                validator=validator,
            )

            result = composer.compose(
                main_path=main_path,
                final_path=final_path,
                selection=IntroOutroSelection(asset_path, "intro"),
                config=self.make_config(),
                expected_main_duration=4.0,
            )

        self.assertFalse(result.asset_was_normalized)
        runner.run.assert_called_once()
        command = runner.run.call_args.args[0]
        self.assertEqual(
            "copy",
            command[command.index("-c") + 1],
        )
        self.assertNotIn("-filter_complex", command)
        self.assertNotIn("-c:v", command)
        self.assertEqual(
            (asset_path, main_path),
            composer.ordered_sources(
                main_path,
                asset_path,
                IntroOutroSelection(asset_path, "intro"),
            ),
        )
        validator.validate.assert_called_once_with(
            output_path=result.output_path,
            expected_duration=6.0,
            max_duration_difference=0.2,
        )

    def test_outro_orders_main_before_asset(self):
        composer = IntroOutroComposer()
        self.assertEqual(
            (Path("main.mp4"), Path("asset.mp4")),
            composer.ordered_sources(
                main_path="main.mp4",
                asset_path="asset.mp4",
                selection=IntroOutroSelection(
                    "asset.mp4",
                    "outro",
                ),
            ),
        )

    def test_concat_list_uses_real_paths_without_hardcoded_assets(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            first = root / "opening sequence.mp4"
            second = root / "main output.mp4"
            list_path = root / "segments.txt"

            IntroOutroComposer().write_concat_list(
                list_path,
                (first, second),
            )
            content = list_path.read_text(encoding="utf-8")

        self.assertIn(first.resolve().as_posix(), content)
        self.assertIn(second.resolve().as_posix(), content)
        self.assertEqual(2, content.count("file '"))

    def test_concat_command_copies_both_streams_without_encoders(self):
        command = IntroOutroComposer().build_concat_command(
            concat_list_path="segments.txt",
            output_path="combined.mp4",
            config=self.make_config(),
        )

        self.assertEqual("concat", command[command.index("-f") + 1])
        self.assertEqual("copy", command[command.index("-c") + 1])
        self.assertNotIn("libx264", command)
        self.assertNotIn("aac", command)
        self.assertNotIn("-filter_complex", command)

    def test_asset_without_audio_is_normalized_with_compatible_silence(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            main_path = root / "main.mp4"
            asset_path = root / "silent.mp4"
            main_path.write_bytes(b"main")
            asset_path.write_bytes(b"asset")
            main_info = self.make_info(duration=4.0)
            silent_info = self.make_info(
                duration=2.0,
                audio_codec=None,
                audio_sample_rate=None,
                audio_channels=None,
            )
            normalized_info = self.make_info(duration=2.0)
            probe = Mock()
            probe.inspect.side_effect = [
                main_info,
                silent_info,
                normalized_info,
            ]
            runner = Mock()
            runner.run.return_value = SimpleNamespace(stderr="")
            validator = Mock()
            composer = IntroOutroComposer(
                probe=probe,
                runner=runner,
                validator=validator,
            )

            result = composer.compose(
                main_path=main_path,
                final_path=root / "final.mp4",
                selection=IntroOutroSelection(asset_path, "outro"),
                config=self.make_config(),
                expected_main_duration=4.0,
            )

        self.assertTrue(result.asset_was_normalized)
        self.assertEqual(2, runner.run.call_count)
        normalize_command = runner.run.call_args_list[0].args[0]
        self.assertTrue(any(
            argument.startswith("anullsrc=")
            for argument in normalize_command
        ))

    def test_mismatched_asset_audio_is_preserved_during_normalization(self):
        composer = IntroOutroComposer()
        command = composer.build_normalize_command(
            source_path="source.mp4",
            output_path="normalized.mp4",
            source_info=self.make_info(
                duration=2.0,
                width=800,
                height=800,
                audio_sample_rate=44100,
            ),
            target_info=self.make_info(duration=4.0),
            config=self.make_config(),
        )
        filter_complex = command[command.index("-filter_complex") + 1]

        self.assertIn("[0:a:0]aresample=48000", filter_complex)
        self.assertFalse(any(
            argument.startswith("anullsrc=")
            for argument in command
        ))
        self.assertIn("force_original_aspect_ratio=decrease", filter_complex)
        self.assertIn("pad=1080:1920", filter_complex)

    def test_probe_detects_mp4_without_audio(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            media_path = Path(temporary_directory) / "silent.mp4"
            media_path.write_bytes(b"mp4")
            payload = {
                "format": {"duration": "2.5"},
                "streams": [{
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1080,
                    "height": 1920,
                    "avg_frame_rate": "30/1",
                    "time_base": "1/15360",
                    "sample_aspect_ratio": "1:1",
                    "pix_fmt": "yuv420p",
                }],
            }

            with patch(
                "app.modules.video.intro_outro.subprocess.run",
                return_value=SimpleNamespace(
                    stdout=json.dumps(payload)
                ),
            ):
                info = IntroOutroMediaProbe().inspect(media_path)

        self.assertFalse(info.has_audio)
        self.assertEqual(2.5, info.duration)

    def test_no_selection_keeps_existing_render_and_promotion_path(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            final_path = root / "final.mp4"
            render_path = root / "final.rendering.mp4"
            context = self._render_context(final_path)
            artifacts = VideoBuildArtifacts(
                filter_complex="[vout]",
                command=["ffmpeg", "main"],
                render_output_path=render_path,
            )
            composer = Mock()
            service = VideoRenderService(
                intro_outro_composer=composer
            )

            def render_main(command):
                render_path.write_bytes(b"main")
                return SimpleNamespace(stderr="")

            with patch.object(
                service,
                "run",
                side_effect=render_main,
            ), patch.object(service, "validate"):
                service.render_final(
                    build_context=context,
                    artifacts=artifacts,
                    diagnostics=Mock(),
                )

            self.assertTrue(final_path.exists())

        composer.compose.assert_not_called()

    def test_failed_intro_outro_never_promotes_partial_output(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            final_path = root / "final.mp4"
            render_path = root / "final.rendering.mp4"
            asset_path = root / "brand.mp4"
            final_path.write_bytes(b"previous-valid")
            asset_path.write_bytes(b"asset")
            context = self._render_context(final_path)
            artifacts = VideoBuildArtifacts(
                filter_complex="[vout]",
                command=["ffmpeg", "main"],
                render_output_path=render_path,
            )
            composer = Mock()
            composer.compose.side_effect = subprocess.CalledProcessError(
                1,
                ["ffmpeg", "concat"],
                stderr="concat failed",
            )
            service = VideoRenderService(
                intro_outro_selection=IntroOutroSelection(
                    asset_path,
                    "intro",
                ),
                intro_outro_composer=composer,
            )

            def render_main(command):
                render_path.write_bytes(b"new-main")
                return SimpleNamespace(stderr="")

            with patch.object(
                service,
                "run",
                side_effect=render_main,
            ), patch.object(service, "validate"), self.assertRaises(
                OperationalError
            ) as caught:
                service.render_final(
                    build_context=context,
                    artifacts=artifacts,
                    diagnostics=Mock(),
                )

            self.assertEqual("FFMPEG", caught.exception.context.family)
            self.assertIsInstance(caught.exception.__cause__, subprocess.CalledProcessError)

            self.assertEqual(
                b"previous-valid",
                final_path.read_bytes(),
            )
            self.assertTrue(render_path.exists())

    def test_successful_intro_outro_is_promoted_atomically(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            final_path = root / "final.mp4"
            render_path = root / "final.rendering.mp4"
            composition_path = root / "final.intro-outro.rendering.mp4"
            asset_path = root / "brand.mp4"
            asset_path.write_bytes(b"asset")
            context = self._render_context(final_path)
            artifacts = VideoBuildArtifacts(
                filter_complex="[vout]",
                command=["ffmpeg", "main"],
                render_output_path=render_path,
            )
            composer = Mock()

            def compose(**kwargs):
                composition_path.write_bytes(b"complete")
                return IntroOutroComposition(
                    output_path=composition_path,
                    command=("ffmpeg", "concat"),
                    stderr="",
                    expected_duration=6.0,
                    asset_was_normalized=False,
                )

            composer.compose.side_effect = compose
            service = VideoRenderService(
                intro_outro_selection=IntroOutroSelection(
                    asset_path,
                    "outro",
                ),
                intro_outro_composer=composer,
            )

            def render_main(command):
                render_path.write_bytes(b"main")
                return SimpleNamespace(stderr="")

            with patch.object(
                service,
                "run",
                side_effect=render_main,
            ), patch.object(service, "validate"):
                service.render_final(
                    build_context=context,
                    artifacts=artifacts,
                    diagnostics=Mock(),
                )

            self.assertEqual(b"complete", final_path.read_bytes())
            self.assertFalse(render_path.exists())
            self.assertFalse(composition_path.exists())

    def _render_context(self, final_path):
        return SimpleNamespace(
            media=SimpleNamespace(output_path=final_path),
            timeline=SimpleNamespace(audio_duration=4.0),
            config=self.make_config(),
        )


if __name__ == "__main__":
    unittest.main()
