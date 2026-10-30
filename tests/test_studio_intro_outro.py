import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.controllers.run_controller import RunController
from app.core.execution_request import (
    ApplicationExecutionRequest,
    StudioExecutionRequest,
)
from app.core.start import run_application
from app.modules.studio.execution_coordinator import StudioExecutionCoordinator
from app.modules.studio import (
    StudioInputMode,
    StudioIntroOutroInputError,
    StudioIntroOutroInputService,
    StudioIntroOutroPlan,
)
from app.modules.video.intro_outro import IntroOutroPlan, IntroOutroSelection
from app.shared.profile_identity import OperationalProfileKey
from app.shared.profile_resolver import OperationalProfileDescriptor
from tests.test_menu_helpers import MenuAnswers


class StudioIntroOutroTest(unittest.TestCase):

    def _file(self, directory, name):
        path = Path(directory) / name
        path.write_bytes(b"video")
        return path

    def test_input_requires_exactly_one_mp4(self):
        with tempfile.TemporaryDirectory() as directory:
            service = StudioIntroOutroInputService(directory)
            with self.assertRaisesRegex(StudioIntroOutroInputError, "ningún archivo MP4"):
                service.discover_source()
            source = self._file(directory, "source.mp4")
            self.assertEqual(source, service.discover_source())
            self._file(directory, "other.MP4")
            with self.assertRaisesRegex(StudioIntroOutroInputError, "exactamente un archivo MP4"):
                service.discover_source()

    def test_menu_maps_intro_outro_to_the_third_mode(self):
        controller = RunController()
        expected = (
            ("SOLO VIDEO", StudioInputMode.VIDEO.value),
            ("SRT + VIDEO", StudioInputMode.SRT_VIDEO.value),
            ("INTRO / OUTRO", StudioInputMode.INTRO_OUTRO.value),
            ("MONTAJE VÍDEOS", StudioInputMode.MONTAJE_VIDEOS.value),
            ("VIDEO + AUDIO | SRT", StudioInputMode.VIDEO_AUDIO_SRT.value),
            ("EXPORTAR SRT ➜  VIDEO", StudioInputMode.EXPORTAR_SRT.value),
        )
        for selection, mode in expected:
            answers = MenuAnswers(selection)
            with self.subTest(selection=selection), patch("builtins.input", side_effect=answers.input), patch("app.controllers.interaction.terminal.ProgressLogger.info", side_effect=answers.print) as logger:
                self.assertEqual(mode, controller.select_studio_input_mode())
                self.assertIn("3. INTRO / OUTRO", "\n".join(call.args[0] for call in logger.call_args_list))

    def test_required_submenu_builds_common_intro_outro_plans(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._file(root, "source.mp4")
            assets = root / "assets"
            assets.mkdir()
            intro = self._file(assets, "intro.mp4")
            outro = self._file(assets, "outro.mp4")
            service = StudioIntroOutroInputService(root)
            controller = RunController(
                studio_intro_outro_input_service=service,
            )
            profile_key = OperationalProfileKey(
                "studio", "vertical", "studio_vertical"
            )
            controller._require_intro_outro_assets = Mock(
                side_effect=lambda _, position: (intro,)
                if position == "intro"
                else (outro,)
            )
            controller._select_intro_outro_asset = Mock(side_effect=lambda assets, position: intro if position == "INTRO" else outro)
            for label, want_intro, want_outro in (("SOLO INTRO", True, False), ("SOLO OUTRO", False, True), ("INTRO + OUTRO", True, True)):
                answers = MenuAnswers(label)
                with self.subTest(label=label), patch("builtins.input", side_effect=answers.input), patch("builtins.print", side_effect=answers.print):
                    plan = controller.select_studio_intro_outro_plan(profile_key)
                self.assertEqual(source, plan.source_path)
                self.assertEqual(want_intro, plan.intro_outro_plan.intro is not None)
                self.assertEqual(want_outro, plan.intro_outro_plan.outro is not None)

    def test_source_selector_lists_multiple_videos_without_subtitle_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = self._file(root, "first.mp4")
            second = self._file(root, "second.mp4")
            assets = root / "assets"
            assets.mkdir()
            intro = self._file(assets, "intro.mp4")
            controller = RunController(
                studio_intro_outro_input_service=StudioIntroOutroInputService(root),
            )
            controller._require_intro_outro_assets = Mock(return_value=(intro,))
            controller._select_intro_outro_asset = Mock(return_value=intro)
            messages = []
            controller._print = messages.append
            controller._select_from_list = Mock(side_effect=(second, "intro"))

            plan = controller.select_studio_intro_outro_plan(
                OperationalProfileKey("studio", "vertical", "studio_vertical"),
            )

        self.assertEqual(second, plan.source_path)
        self.assertIn("\nVIDEO\n", messages)
        self.assertIn("1. first.mp4", messages)
        self.assertIn("2. second.mp4", messages)
        self.assertNotIn("SUBTÍTULOS", "\n".join(messages))

    def test_run_intro_outro_uses_only_an_operational_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self._file(directory, "source.mp4")
            plan = StudioIntroOutroPlan(
                source,
                IntroOutroPlan(intro=IntroOutroSelection(source, "intro")),
            )
            subtitle_resolver = Mock()
            controller = RunController(
                subtitle_profile_resolver=subtitle_resolver,
            )
            profile_key = OperationalProfileKey(
                "studio", "vertical", "studio_vertical"
            )
            selection_order = []
            controller.select_studio_input_mode = Mock(
                return_value=StudioInputMode.INTRO_OUTRO.value,
            )
            controller._select_studio_operational_profile = Mock(
                side_effect=lambda: selection_order.append("format")
                or (profile_key, Mock()),
            )
            controller.select_studio_intro_outro_plan = Mock(
                side_effect=lambda key: selection_order.append("intro_outro")
                or plan,
            )
            controller.ask_project_name = Mock(return_value="demo")
            controller.ask_clear_output = Mock(return_value=False)
            messages = []
            controller._print = messages.append

            request = controller._run_studio()

        self.assertIs(StudioInputMode.INTRO_OUTRO, request.route.input_mode)
        self.assertIs(plan, request.route.plan)
        self.assertNotIn("subtitle_config", vars(request))
        self.assertNotIn("subtitle_config", vars(request.route))
        self.assertIsNone(request.subtitle_profile_key)
        self.assertEqual(profile_key.format, request.operational_profile_key.format)
        self.assertNotIn("SUBTÍTULOS", "\n".join(messages))
        subtitle_resolver.assert_not_called()
        controller.select_studio_intro_outro_plan.assert_called_once_with(
            profile_key,
        )
        self.assertEqual(["format", "intro_outro"], selection_order)

    def test_operational_profile_discovery_does_not_use_subtitle_profiles(self):
        profile_key = OperationalProfileKey(
            "studio",
            "test_format",
            "test_profile",
        )
        profile_resolver = Mock()
        profile_resolver.discover_formats.return_value = ("test_format",)
        profile_resolver.discover_operational_profiles.return_value = (
            OperationalProfileDescriptor(
                key=profile_key,
                path=Path("test_profile.json"),
                display_name="Test profile",
            ),
        )
        profile_resolver.load_operational.return_value = {
            "profile_id": "test_profile"
        }
        subtitle_resolver = Mock()
        loader = Mock()
        loaded_profile = Mock()
        loader.load.return_value = loaded_profile
        controller = RunController(
            profile_resolver=profile_resolver,
            subtitle_profile_resolver=subtitle_resolver,
            studio_profile_loader=loader,
        )
        controller._print = Mock()
        controller._select_from_list = Mock(return_value="test_format")

        selected_key, selected_profile = controller._select_studio_operational_profile()

        self.assertEqual(profile_key, selected_key)
        self.assertIs(loaded_profile, selected_profile)
        subtitle_resolver.assert_not_called()
        profile_resolver.discover_operational_profiles.assert_called_once_with(
            "studio",
            "test_format",
        )

    def test_intro_outro_execution_passes_no_subtitle_to_renderer(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self._file(directory, "source.mp4")
            original_bytes = source.read_bytes()
            plan = StudioIntroOutroPlan(
                source,
                IntroOutroPlan(outro=IntroOutroSelection(source, "outro")),
            )
            profile_key = OperationalProfileKey(
                "studio", "vertical", "studio_vertical"
            )
            config = Mock()
            config.get_operational_profile_key.return_value = OperationalProfileKey(
                "studio", "vertical", "studio_vertical"
            )
            config.get_profile_config.return_value = {"profile_id": profile_key.profile_id}
            profile = Mock()
            profile_loader = Mock()
            profile_loader.load.return_value = profile
            output_path = Path(directory) / "final.mp4"
            resolver = Mock()
            resolver.resolve.return_value = output_path
            renderer = Mock()
            renderer.render.return_value = "rendered"

            result = StudioExecutionCoordinator().run_intro_outro(
                plan,
                config_manager=config,
                profile_loader=profile_loader,
                output_path_resolver=resolver,
                render_service=renderer,
            )

            self.assertEqual(original_bytes, source.read_bytes())

        self.assertEqual("rendered", result)
        config.get_subtitle_profile_by_key.assert_not_called()
        renderer.render.assert_called_once_with(
            video_path=source,
            subtitle_path=None,
            profile_key=OperationalProfileKey(
                "studio", "vertical", "studio_vertical"
            ),
            profile=profile,
            output_path=output_path,
            intro_outro_selection=plan.intro_outro_plan,
        )

    def test_start_dispatches_plan_without_standard_studio_pipeline(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self._file(directory, "source.mp4")
            plan = StudioIntroOutroPlan(source, IntroOutroPlan(intro=IntroOutroSelection(source, "intro")))
            request = ApplicationExecutionRequest(
                project_name="demo",
                clear_output=False,
                operational_profile_key=OperationalProfileKey(
                    "studio", "vertical", "studio_vertical"
                ),
                subtitle_profile_key=None,
                route=StudioExecutionRequest(
                    input_mode=StudioInputMode.INTRO_OUTRO,
                    plan=plan,
                ),
            )
            with patch("app.core.start.ProjectManager") as projects, patch.object(StudioExecutionCoordinator, "run_intro_outro", return_value="result") as execute, patch.object(StudioExecutionCoordinator, "run_standard") as normal:
                self.assertEqual("result", run_application(request=request))
            self.assertEqual((plan,), execute.call_args.args)
            self.assertIs(projects.return_value, execute.call_args.kwargs["project"])
            self.assertEqual(
                request.operational_profile_key,
                execute.call_args.kwargs["config_manager"].get_operational_profile_key(),
            )
            projects.assert_called_once_with(project_name="demo")
            normal.assert_not_called()


if __name__ == "__main__":
    unittest.main()
