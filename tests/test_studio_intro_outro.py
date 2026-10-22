import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.controllers.run_controller import RunController
from app.core.start import ejecutar_studio_intro_outro, iniciar
from app.modules.studio import (
    StudioInputMode,
    StudioIntroOutroInputError,
    StudioIntroOutroInputService,
    StudioIntroOutroPlan,
)
from app.modules.video.intro_outro import IntroOutroPlan, IntroOutroSelection
from app.shared.profile_identity import OperationalProfileKey
from app.shared.profile_resolver import OperationalProfileDescriptor


class StudioIntroOutroTest(unittest.TestCase):

    def _file(self, directory, name):
        path = Path(directory) / name
        path.write_bytes(b"video")
        return path

    def test_input_requires_exactly_one_mp4(self):
        with tempfile.TemporaryDirectory() as directory:
            service = StudioIntroOutroInputService(directory)
            with self.assertRaisesRegex(StudioIntroOutroInputError, "ningun archivo MP4"):
                service.discover_source()
            source = self._file(directory, "source.mp4")
            self.assertEqual(source, service.discover_source())
            self._file(directory, "other.MP4")
            with self.assertRaisesRegex(StudioIntroOutroInputError, "exactamente un archivo MP4"):
                service.discover_source()

    def test_menu_maps_intro_outro_to_the_third_mode(self):
        controller = RunController()
        expected = (
            StudioInputMode.VIDEO.value,
            StudioInputMode.SRT_VIDEO.value,
            StudioInputMode.INTRO_OUTRO.value,
            StudioInputMode.MONTAJE_VIDEOS.value,
            StudioInputMode.VIDEO_AUDIO_SRT.value,
            StudioInputMode.EXPORTAR_SRT.value,
        )
        for selection, mode in enumerate(expected, 1):
            with self.subTest(selection=selection), patch("builtins.input", return_value=str(selection)), patch("app.controllers.interaction.terminal.ProgressLogger.info") as logger:
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
                "studio", "instagram", "studio_instagram"
            )
            controller._require_intro_outro_assets = Mock(
                side_effect=lambda _, position: (intro,)
                if position == "intro"
                else (outro,)
            )
            controller._select_intro_outro_asset = Mock(side_effect=lambda assets, position: intro if position == "INTRO" else outro)
            for answers, want_intro, want_outro in ((["1"], True, False), (["2"], False, True), (["3"], True, True)):
                with self.subTest(answers=answers), patch("builtins.input", side_effect=answers):
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
                OperationalProfileKey("studio", "instagram", "studio_instagram"),
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
                "studio", "instagram", "studio_instagram"
            )
            selection_order = []
            controller.select_studio_input_mode = Mock(
                return_value=StudioInputMode.INTRO_OUTRO.value,
            )
            controller._select_studio_operational_profile = Mock(
                side_effect=lambda: selection_order.append("platform")
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

            options = controller._run_studio()

        self.assertEqual(StudioInputMode.INTRO_OUTRO.value, options["studio_input_mode"])
        self.assertIs(plan, options["studio_intro_outro_plan"])
        self.assertNotIn("subtitle_config", options)
        self.assertNotIn("subtitle_profile_key", options)
        self.assertEqual(profile_key.platform, options["profile_platform"])
        self.assertNotIn("SUBTÍTULOS", "\n".join(messages))
        subtitle_resolver.assert_not_called()
        controller.select_studio_intro_outro_plan.assert_called_once_with(
            profile_key,
        )
        self.assertEqual(["platform", "intro_outro"], selection_order)

    def test_operational_profile_discovery_does_not_use_subtitle_profiles(self):
        profile_key = OperationalProfileKey(
            "studio",
            "test_platform",
            "test_profile",
        )
        profile_resolver = Mock()
        profile_resolver.discover_platforms.return_value = ("test_platform",)
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
        controller._select_from_list = Mock(return_value="test_platform")

        selected_key, selected_profile = controller._select_studio_operational_profile()

        self.assertEqual(profile_key, selected_key)
        self.assertIs(loaded_profile, selected_profile)
        subtitle_resolver.assert_not_called()
        profile_resolver.discover_operational_profiles.assert_called_once_with(
            "studio",
            "test_platform",
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
                "studio", "instagram", "studio_instagram"
            )
            config = Mock()
            config.get_operational_profile_key.return_value = OperationalProfileKey(
                "studio", "instagram", "studio_instagram"
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

            result = ejecutar_studio_intro_outro(
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
                "studio", "instagram", "studio_instagram"
            ),
            profile=profile,
            output_path=output_path,
            intro_outro_selection=plan.intro_outro_plan,
        )

    def test_start_dispatches_plan_without_standard_studio_pipeline(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self._file(directory, "source.mp4")
            plan = StudioIntroOutroPlan(source, IntroOutroPlan(intro=IntroOutroSelection(source, "intro")))
            with patch.dict(os.environ, {"MC_PIPELINE_MODE": "studio"}, clear=True), patch("app.core.start.ejecutar_studio_intro_outro", return_value="result") as execute, patch("app.core.start.ejecutar_studio") as normal:
                self.assertEqual("result", iniciar(studio_intro_outro_plan=plan))
            execute.assert_called_once_with(plan)
            normal.assert_not_called()


if __name__ == "__main__":
    unittest.main()
