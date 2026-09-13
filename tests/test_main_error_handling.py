import unittest
import os
from unittest.mock import patch

import main
from app.modules.visual_design import VisualDesignInterpretationError
from app.modules.studio import StudioSubtitleExportInputError
from app.managers.output_manager import OutputResetBlockedError


class MainErrorHandlingTest(unittest.TestCase):

    def test_visual_design_interpretation_error_is_user_visible(self):
        options = {
            "profile_component": "video",
            "profile_platform": "instagram",
            "profile_id": "video_instagram",
            "subtitle_config": "",
            "voice_config": "",
            "music_category": None,
            "overlays_mode": "off",
            "project_name": "error test",
            "visual_pipeline": "video",
            "script_source": "manual_design",
            "design_target": "video",
            "pipeline_mode": "design_video",
            "clear_output": False,
        }

        with patch.dict(
            os.environ,
            {},
            clear=True
        ), patch(
            "main.RunController"
        ) as controller_mock, patch(
            "main.iniciar",
            side_effect=VisualDesignInterpretationError(
                "La interpretacion visual excedio el tiempo maximo."
            )
        ), patch(
            "builtins.print"
        ) as print_mock:
            controller_mock.return_value.run.return_value = options

            result = main.main()

        self.assertEqual(
            1,
            result
        )
        print_mock.assert_called_once_with(
            "ERROR: La interpretacion visual excedio el tiempo maximo."
        )

    def test_studio_export_empty_input_is_user_visible_without_starting_runtime(self):
        with patch("main.RunController") as controller_mock, patch(
            "main.iniciar"
        ) as iniciar_mock, patch("builtins.print") as print_mock:
            controller_mock.return_value.run.side_effect = (
                StudioSubtitleExportInputError(
                    "No se encontro ningun archivo MP4 o MP3 en:\n"
                    "input/studio/exportar_srt/transcribir/\n\n"
                    "Anade un archivo valido e intentalo de nuevo."
                )
            )

            result = main.main()

        self.assertEqual(1, result)
        iniciar_mock.assert_not_called()
        print_mock.assert_called_once_with(
            "ERROR: No se encontro ningun archivo MP4 o MP3 en:\n"
            "input/studio/exportar_srt/transcribir/\n\n"
            "Anade un archivo valido e intentalo de nuevo."
        )

    def test_studio_solo_video_input_error_is_user_visible(self):
        options = {
            "profile_component": "studio",
            "profile_platform": "instagram",
            "profile_id": "studio_instagram",
            "subtitle_config": "single_line",
            "voice_config": "",
            "music_category": None,
            "project_name": "studio silent video",
            "visual_pipeline": "studio",
            "script_source": "",
            "design_target": "",
            "pipeline_mode": "studio",
            "studio_input_mode": "video",
            "clear_output": False,
        }

        with patch.dict(os.environ, {}, clear=True), patch(
            "main.RunController"
        ) as controller_mock, patch(
            "main.iniciar",
            side_effect=ValueError(
                "El video seleccionado no contiene una pista de audio. "
                "SOLO VIDEO necesita audio para generar los subtitulos."
            ),
        ), patch("builtins.print") as print_mock:
            controller_mock.return_value.run.return_value = options

            result = main.main()

        self.assertEqual(1, result)
        print_mock.assert_called_once_with(
            "ERROR: El video seleccionado no contiene una pista de audio. "
            "SOLO VIDEO necesita audio para generar los subtitulos."
        )

    def test_output_reset_blocked_error_stops_pipeline_cleanly(self):
        options = {
            "profile_component": "video",
            "profile_platform": "instagram",
            "profile_id": "video_instagram",
            "subtitle_config": "",
            "voice_config": "",
            "music_category": None,
            "overlays_mode": "off",
            "project_name": "blocked output",
            "visual_pipeline": "video",
            "script_source": "manual_design",
            "design_target": "video",
            "pipeline_mode": "design_video",
            "clear_output": True,
        }

        with patch.dict(os.environ, {}, clear=True), patch(
            "main.RunController"
        ) as controller_mock, patch("main.OutputManager") as output_manager, patch(
            "main.iniciar"
        ) as iniciar_mock, patch("builtins.print") as print_mock:
            controller_mock.return_value.run.return_value = options
            output_manager.return_value.reset.side_effect = (
                OutputResetBlockedError(
                    "No se puede eliminar OUTPUT porque uno de sus archivos "
                    "esta siendo utilizado por otro programa.\n\n"
                    "Cierra el archivo y vuelve a intentarlo."
                )
            )

            result = main.main()

        self.assertEqual(1, result)
        iniciar_mock.assert_not_called()
        print_mock.assert_called_once_with(
            "ERROR: No se puede eliminar OUTPUT porque uno de sus archivos "
            "esta siendo utilizado por otro programa.\n\n"
            "Cierra el archivo y vuelve a intentarlo."
        )

    def test_output_reset_normal_path_continues_to_runtime(self):
        options = {
            "profile_component": "video",
            "profile_platform": "instagram",
            "profile_id": "video_instagram",
            "subtitle_config": "",
            "voice_config": "",
            "music_category": None,
            "overlays_mode": "off",
            "project_name": "reset output",
            "visual_pipeline": "video",
            "script_source": "manual_design",
            "design_target": "video",
            "pipeline_mode": "design_video",
            "clear_output": True,
        }

        with patch.dict(os.environ, {}, clear=True), patch(
            "main.RunController"
        ) as controller_mock, patch("main.OutputManager") as output_manager, patch(
            "main.iniciar"
        ) as iniciar_mock:
            controller_mock.return_value.run.return_value = options

            result = main.main()

        self.assertEqual(0, result)
        output_manager.return_value.reset.assert_called_once_with()
        iniciar_mock.assert_called_once_with(subtitle_style=None)


if __name__ == "__main__":
    unittest.main()
