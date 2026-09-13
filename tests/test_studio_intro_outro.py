import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.controllers.run_controller import RunController
from app.core.start import iniciar
from app.modules.studio import (
    StudioInputMode,
    StudioIntroOutroInputError,
    StudioIntroOutroInputService,
    StudioIntroOutroPlan,
)
from app.modules.video.intro_outro import IntroOutroPlan, IntroOutroSelection


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
            with self.subTest(selection=selection), patch("builtins.input", return_value=str(selection)), patch("app.controllers.run_controller.ProgressLogger.info") as logger:
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
            controller._require_intro_outro_assets = Mock(side_effect=lambda position: (intro,) if position == "intro" else (outro,))
            controller._select_intro_outro_asset = Mock(side_effect=lambda assets, position: intro if position == "INTRO" else outro)
            for answers, want_intro, want_outro in ((["1"], True, False), (["2"], False, True), (["3"], True, True)):
                with self.subTest(answers=answers), patch("builtins.input", side_effect=answers):
                    plan = controller.select_studio_intro_outro_plan()
                self.assertEqual(source, plan.source_path)
                self.assertEqual(want_intro, plan.intro_outro_plan.intro is not None)
                self.assertEqual(want_outro, plan.intro_outro_plan.outro is not None)

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
