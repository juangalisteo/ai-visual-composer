import os
import unittest
from unittest.mock import patch

import main


class MainOverlaysModeTest(
    unittest.TestCase
):

    def test_main_transports_overlay_mode_only_in_typed_request(
        self
    ):
        options = {
            "profile_component": "imagen",
            "profile_platform": "youtube",
            "profile_id": "imagen_youtube",
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

        iniciar_mock.assert_called_once()
        request = iniciar_mock.call_args.kwargs["request"]
        self.assertEqual("smart", request.route.overlays_mode)
        self.assertEqual("imagen_youtube", request.operational_profile_key.profile_id)
        self.assertEqual({"request"}, set(iniciar_mock.call_args.kwargs))
        self.assertNotIn(
            "MC_SUBTITLE_CONFIG",
            os.environ
        )
        for direct_key in (
            "MC_PIPELINE_MODE",
            "MC_VISUAL_PIPELINE",
            "MC_SCRIPT_SOURCE",
            "MC_MUSIC_CATEGORY",
            "MC_DESIGN_TARGET",
            "MC_PROFILE_COMPONENT",
            "MC_PROFILE_PLATFORM",
            "MC_PROFILE_ID",
            "MC_PROJECT_NAME",
            "MC_VOICE_CONFIG",
            "MC_OVERLAYS_MODE",
        ):
            self.assertNotIn(direct_key, os.environ)
        output_manager_class.assert_not_called()


if __name__ == "__main__":
    unittest.main()
