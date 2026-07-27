import unittest
from unittest.mock import patch

from app.controllers.run_controller import RunController


class RunControllerVisualPipelineTest(unittest.TestCase):

    def test_selects_image_pipeline(self):
        controller = RunController()

        with patch(
            "builtins.input",
            return_value="1"
        ):
            self.assertEqual(
                "image",
                controller.select_visual_pipeline()
            )

    def test_video_pipeline_is_visible_but_not_available(self):
        controller = RunController()

        with patch(
            "builtins.input",
            side_effect=(
                "2",
                "1",
            )
        ), patch(
            "builtins.print"
        ) as print_mock:
            selected = controller.select_visual_pipeline()

        self.assertEqual(
            "image",
            selected
        )
        printed = "\n".join(
            str(call.args[0])
            for call in print_mock.call_args_list
            if call.args
        )
        self.assertIn(
            "Video Pipeline (Próximamente)",
            printed
        )
        self.assertIn(
            "próximamente",
            printed
        )

    def test_run_includes_visual_pipeline_without_changing_existing_options(self):
        controller = RunController()

        with patch.object(
            controller,
            "select_visual_pipeline",
            return_value="image"
        ), patch.object(
            controller,
            "select_pipeline_mode",
            return_value="full"
        ), patch.object(
            controller,
            "select_profile",
            return_value={
                "path": "config/profiles/youtube/modo_conciencia.json"
            }
        ), patch.object(
            controller,
            "select_subtitle_config",
            return_value="single_line"
        ), patch.object(
            controller,
            "select_voice_config",
            return_value="masculina"
        ), patch.object(
            controller,
            "select_music_category",
            return_value=None
        ), patch.object(
            controller,
            "ask_project_name",
            return_value="project"
        ), patch.object(
            controller,
            "ask_clear_output",
            return_value=False
        ):
            options = controller.run()

        self.assertEqual(
            "image",
            options["visual_pipeline"]
        )
        self.assertEqual(
            "full",
            options["pipeline_mode"]
        )
        self.assertEqual(
            "project",
            options["project_name"]
        )


if __name__ == "__main__":
    unittest.main()
