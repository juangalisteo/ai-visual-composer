import os
import unittest
from unittest.mock import patch

import main
from app.core.execution_request import (
    ApplicationExecutionRequest,
    StandardExecutionRequest,
)
from app.shared.profile_identity import OperationalProfileKey


class MainOverlaysModeTest(
    unittest.TestCase
):

    def test_main_transports_overlay_mode_only_in_typed_request(
        self
    ):
        controller_request = ApplicationExecutionRequest(
            project_name="project",
            clear_output=False,
            operational_profile_key=OperationalProfileKey(
                "imagen",
                "horizontal",
                "imagen_horizontal",
            ),
            subtitle_profile_key=None,
            route=StandardExecutionRequest(
                pipeline_mode="full",
                visual_pipeline="image",
                script_source="generated",
                voice_config_id="masculina",
                music_category=None,
                overlays_mode="smart",
            ),
        )

        with patch.dict(
            os.environ,
            {},
            clear=True
        ), patch(
            "main.RunController"
        ) as controller_class, patch(
            "main.run_application"
        ) as run_application_mock, patch(
            "main.OutputManager"
        ) as output_manager_class:
            controller_class.return_value.run.return_value = (
                controller_request
            )

            main.main()

        run_application_mock.assert_called_once()
        request = run_application_mock.call_args.kwargs["request"]
        self.assertEqual("smart", request.route.overlays_mode)
        self.assertEqual("imagen_horizontal", request.operational_profile_key.profile_id)
        self.assertEqual({"request"}, set(run_application_mock.call_args.kwargs))
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
