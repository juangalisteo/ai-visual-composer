import unittest
import os
from unittest.mock import patch

import main
from app.modules.visual_design import VisualDesignInterpretationError


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


if __name__ == "__main__":
    unittest.main()
