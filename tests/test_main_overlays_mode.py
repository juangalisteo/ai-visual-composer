import os
import unittest
from unittest.mock import patch

import main


class MainOverlaysModeTest(
    unittest.TestCase
):

    def test_main_propagates_overlay_mode_environment_value(
        self
    ):
        options = {
            "profile_component": "imagen",
            "profile_platform": "youtube",
            "profile_id": "imagen_youtube",
            "subtitle_config": "single_line",
            "voice_config": "masculina",
            "music_category": None,
            "overlays_mode": "smart",
            "project_name": "project",
            "visual_pipeline": "image",
            "script_source": "generated",
            "pipeline_mode": "full",
            "clear_output": False
        }

        with patch.dict(
            os.environ,
            {},
            clear=True
        ), patch(
            "main.RunController"
        ) as controller_class, patch(
            "main.iniciar"
        ) as iniciar_mock, patch(
            "main.OutputManager"
        ) as output_manager_class:
            controller_class.return_value.run.return_value = (
                options
            )

            main.main()

            self.assertEqual(
                "smart",
                os.environ["MC_OVERLAYS_MODE"]
            )

        iniciar_mock.assert_called_once_with(
            subtitle_style="single_line"
        )
        self.assertNotIn(
            "MC_SUBTITLE_CONFIG",
            os.environ
        )
        output_manager_class.assert_not_called()


if __name__ == "__main__":
    unittest.main()
