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
            "Vídeo",
            printed
        )
        self.assertIn(
            "No disponible.",
            printed
        )

    def test_script_mode_is_second_option(self):
        controller = RunController()

        with patch(
            "builtins.input",
            return_value="2"
        ), patch(
            "builtins.print"
        ) as print_mock:
            selected = controller.select_pipeline_mode()

        self.assertEqual(
            "script",
            selected
        )
        printed = "\n".join(
            str(call.args[0])
            for call in print_mock.call_args_list
            if call.args
        )
        self.assertIn(
            "1. Proyecto completo",
            printed
        )
        self.assertIn(
            "2. Solo guion",
            printed
        )
        self.assertIn(
            "3. Solo audio",
            printed
        )
        self.assertIn(
            "4. Audio + subtítulos",
            printed
        )
        self.assertIn(
            "5. Audio + subtítulos + storyboard",
            printed
        )

    def test_existing_modes_keep_internal_identifiers(self):
        cases = (
            ("1", "full"),
            ("3", "audio"),
            ("4", "subtitles"),
            ("5", "storyboard"),
        )

        for option, expected_mode in cases:
            with self.subTest(
                option=option
            ):
                controller = RunController()

                with patch(
                    "builtins.input",
                    return_value=option
                ):
                    self.assertEqual(
                        expected_mode,
                        controller.select_pipeline_mode()
                    )

    def test_script_mode_skips_unused_configuration_prompts(self):
        controller = RunController()

        with patch.object(
            controller,
            "select_visual_pipeline",
            return_value="image"
        ), patch.object(
            controller,
            "select_pipeline_mode",
            return_value="script"
        ), patch.object(
            controller,
            "select_profile",
            return_value={
                "path": "config/profiles/youtube/modo_conciencia.json"
            }
        ) as profile_mock, patch.object(
            controller,
            "select_subtitle_config"
        ) as subtitle_mock, patch.object(
            controller,
            "select_voice_config"
        ) as voice_mock, patch.object(
            controller,
            "select_music_category"
        ) as music_mock, patch.object(
            controller,
            "select_overlays_mode"
        ) as overlays_mock, patch.object(
            controller,
            "ask_project_name",
            return_value="project"
        ) as project_mock, patch.object(
            controller,
            "ask_clear_output",
            return_value=False
        ) as clear_mock:
            options = controller.run()

        self.assertEqual(
            "script",
            options["pipeline_mode"]
        )
        self.assertEqual(
            "config/profiles/youtube/modo_conciencia.json",
            options["profile_path"]
        )
        self.assertEqual(
            "project",
            options["project_name"]
        )
        self.assertFalse(
            options["clear_output"]
        )
        profile_mock.assert_called_once()
        project_mock.assert_called_once()
        clear_mock.assert_called_once()
        subtitle_mock.assert_not_called()
        voice_mock.assert_not_called()
        music_mock.assert_not_called()
        overlays_mock.assert_not_called()
        self.assertEqual(
            "",
            options["subtitle_config"]
        )
        self.assertEqual(
            "",
            options["voice_config"]
        )
        self.assertIsNone(
            options["music_category"]
        )
        self.assertEqual(
            "off",
            options["overlays_mode"]
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
            "select_overlays_mode",
            return_value="smart"
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
        self.assertEqual(
            "smart",
            options["overlays_mode"]
        )

    def test_audio_mode_skips_subtitles_but_keeps_voice_and_music(self):
        controller = RunController()

        with patch.object(
            controller,
            "select_visual_pipeline",
            return_value="image"
        ), patch.object(
            controller,
            "select_pipeline_mode",
            return_value="audio"
        ), patch.object(
            controller,
            "select_profile",
            return_value={
                "path": "config/profiles/youtube/modo_conciencia.json"
            }
        ), patch.object(
            controller,
            "select_subtitle_config"
        ) as subtitle_mock, patch.object(
            controller,
            "select_voice_config",
            return_value="femenina"
        ) as voice_mock, patch.object(
            controller,
            "select_music_category",
            return_value="calm"
        ) as music_mock, patch.object(
            controller,
            "select_overlays_mode"
        ) as overlays_mock, patch.object(
            controller,
            "ask_project_name",
            return_value="audio project"
        ), patch.object(
            controller,
            "ask_clear_output",
            return_value=False
        ):
            options = controller.run()

        subtitle_mock.assert_not_called()
        voice_mock.assert_called_once()
        music_mock.assert_called_once()
        overlays_mock.assert_not_called()
        self.assertEqual(
            "",
            options["subtitle_config"]
        )
        self.assertEqual(
            "femenina",
            options["voice_config"]
        )
        self.assertEqual(
            "calm",
            options["music_category"]
        )
        self.assertEqual(
            "off",
            options["overlays_mode"]
        )

    def test_music_menu_only_exposes_disabled_or_random_selection(self):
        controller = RunController()

        with patch(
            "builtins.input",
            return_value="2"
        ), patch(
            "builtins.print"
        ) as print_mock:
            selected = controller.select_music_category()

        printed = "\n".join(
            str(call.args[0])
            for call in print_mock.call_args_list
            if call.args
        )
        self.assertEqual(
            "random",
            selected
        )
        self.assertIn(
            "1. Sin música",
            printed
        )
        self.assertIn(
            "2. Aleatoria",
            printed
        )
        self.assertNotIn(
            "action",
            printed
        )
        self.assertNotIn(
            "ambient",
            printed
        )
        self.assertNotIn(
            "cinematic",
            printed
        )

    def test_music_menu_without_music_returns_none(self):
        controller = RunController()

        with patch(
            "builtins.input",
            return_value="1"
        ):
            self.assertIsNone(
                controller.select_music_category()
            )

    def test_subtitle_config_is_requested_only_for_modes_that_use_subtitles(self):
        cases = (
            "full",
            "subtitles",
            "storyboard",
        )

        for pipeline_mode in cases:
            with self.subTest(
                pipeline_mode=pipeline_mode
            ):
                controller = RunController()

                with patch.object(
                    controller,
                    "select_visual_pipeline",
                    return_value="image"
                ), patch.object(
                    controller,
                    "select_pipeline_mode",
                    return_value=pipeline_mode
                ), patch.object(
                    controller,
                    "select_profile",
                    return_value={
                        "path": (
                            "config/profiles/youtube/"
                            "modo_conciencia.json"
                        )
                    }
                ), patch.object(
                    controller,
                    "select_subtitle_config",
                    return_value="single_line"
                ) as subtitle_mock, patch.object(
                    controller,
                    "select_voice_config",
                    return_value="masculina"
                ), patch.object(
                    controller,
                    "select_music_category",
                    return_value=None
                ) as music_mock, patch.object(
                    controller,
                    "select_overlays_mode",
                    return_value="smart"
                ) as overlays_mock, patch.object(
                    controller,
                    "ask_project_name",
                    return_value="project"
                ), patch.object(
                    controller,
                    "ask_clear_output",
                    return_value=False
                ):
                    options = controller.run()

                subtitle_mock.assert_called_once()
                music_mock.assert_called_once()
                if pipeline_mode == "full":
                    overlays_mock.assert_called_once()
                    self.assertEqual(
                        "smart",
                        options["overlays_mode"]
                    )
                else:
                    overlays_mock.assert_not_called()
                    self.assertEqual(
                        "off",
                        options["overlays_mode"]
                    )
                self.assertEqual(
                    "single_line",
                    options["subtitle_config"]
                )

    def test_overlay_menu_returns_smart_when_enabled(
        self
    ):
        controller = RunController()

        with patch(
            "builtins.input",
            return_value="1"
        ), patch(
            "builtins.print"
        ) as print_mock:
            selected = controller.select_overlays_mode()

        printed = "\n".join(
            str(call.args[0])
            for call in print_mock.call_args_list
            if call.args
        )
        self.assertEqual(
            "smart",
            selected
        )
        self.assertIn(
            "OVERLAYS",
            printed
        )
        self.assertIn(
            "1. Sí",
            printed
        )
        self.assertIn(
            "2. No",
            printed
        )

    def test_overlay_menu_returns_off_when_disabled(
        self
    ):
        controller = RunController()

        with patch(
            "builtins.input",
            return_value="2"
        ):
            self.assertEqual(
                "off",
                controller.select_overlays_mode()
            )

    def test_overlay_prompt_is_requested_only_for_full_mode(
        self
    ):
        cases = (
            "script",
            "audio",
            "subtitles",
            "storyboard",
        )

        for pipeline_mode in cases:
            with self.subTest(
                pipeline_mode=pipeline_mode
            ):
                controller = RunController()

                with patch.object(
                    controller,
                    "select_visual_pipeline",
                    return_value="image"
                ), patch.object(
                    controller,
                    "select_pipeline_mode",
                    return_value=pipeline_mode
                ), patch.object(
                    controller,
                    "select_profile",
                    return_value={
                        "path": (
                            "config/profiles/youtube/"
                            "modo_conciencia.json"
                        )
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
                    "select_overlays_mode"
                ) as overlays_mock, patch.object(
                    controller,
                    "ask_project_name",
                    return_value="project"
                ), patch.object(
                    controller,
                    "ask_clear_output",
                    return_value=False
                ):
                    options = controller.run()

                overlays_mock.assert_not_called()
                self.assertEqual(
                    "off",
                    options["overlays_mode"]
                )


if __name__ == "__main__":
    unittest.main()
