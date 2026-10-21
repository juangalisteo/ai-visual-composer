import unittest
from pathlib import Path
from unittest.mock import patch

from app.controllers.run_controller import RunController
from app.shared.error_context import ExitKind
from app.shared.operational_error import OperationalError
from app.shared.profile_identity import (
    OperationalProfileKey,
    ProfileComponent,
)
from app.shared.subtitle_profile_identity import SubtitleProfileKey


class RunControllerVisualPipelineTest(unittest.TestCase):

    def test_selects_image_pipeline(self):
        controller = RunController()

        with patch(
            "builtins.input",
            return_value="2"
        ):
            self.assertEqual(
                "image",
                controller.select_visual_pipeline()
            )

    def test_selects_script_pipeline_from_main_menu(self):
        controller = RunController()

        with patch(
            "builtins.input",
            return_value="1"
        ), patch(
            "builtins.print"
        ) as print_mock:
            selected = controller.select_visual_pipeline()

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
            "1. Guion",
            printed
        )
        self.assertIn(
            "2. Imagen",
            printed
        )
        self.assertIn(
            "3. Video",
            printed
        )

    def test_selects_video_pipeline_from_main_menu(self):
        controller = RunController()

        with patch(
            "builtins.input",
            return_value="3"
        ), patch(
            "builtins.print"
        ) as print_mock:
            selected = controller.select_visual_pipeline()

        self.assertEqual(
            "video",
            selected
        )
        printed = "\n".join(
            str(call.args[0])
            for call in print_mock.call_args_list
            if call.args
        )
        self.assertIn(
            "Video",
            printed
        )
        self.assertNotIn(
            "No disponible.",
            printed
        )

    def test_script_destination_video_is_visible_and_selectable(self):
        controller = RunController()

        with patch(
            "builtins.input",
            return_value="2"
        ), patch(
            "builtins.print"
        ) as print_mock:
            selected = controller.select_script_destination()

        self.assertEqual(
            "video",
            selected
        )
        printed = "\n".join(
            str(call.args[0])
            for call in print_mock.call_args_list
            if call.args
        )
        self.assertIn(
            "DESTINO",
            printed
        )
        self.assertIn(
            "1. Imagen",
            printed
        )
        self.assertIn(
            "2. Video",
            printed
        )
        self.assertIn(
            "3. Dise",
            printed
        )
        self.assertNotIn(
            "No disponible.",
            printed
        )

    def test_script_destination_design_is_visible_and_selectable(self):
        controller = RunController()

        with patch(
            "builtins.input",
            return_value="3"
        ), patch(
            "builtins.print"
        ) as print_mock:
            selected = controller.select_script_destination()

        self.assertEqual(
            "design",
            selected
        )
        printed = "\n".join(
            str(call.args[0])
            for call in print_mock.call_args_list
            if call.args
        )
        self.assertIn(
            "DESTINO",
            printed
        )
        self.assertIn(
            "1. Imagen",
            printed
        )
        self.assertIn(
            "2. Video",
            printed
        )
        self.assertIn(
            "3. Dise",
            printed
        )

    def test_design_target_image_is_visible_and_selectable(self):
        controller = RunController()

        with patch(
            "builtins.input",
            return_value="1"
        ), patch(
            "builtins.print"
        ) as print_mock:
            selected = controller.select_design_target()

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
            "DISE",
            printed
        )
        self.assertNotIn("\\nDISE", printed)
        self.assertIn(
            "1. Imagen",
            printed
        )
        self.assertIn(
            "2. Video",
            printed
        )

    def test_design_target_video_is_visible_and_selectable(self):
        controller = RunController()

        with patch(
            "builtins.input",
            return_value="2"
        ), patch(
            "builtins.print"
        ) as print_mock:
            selected = controller.select_design_target()

        self.assertEqual(
            "video",
            selected
        )
        printed = "\n".join(
            str(call.args[0])
            for call in print_mock.call_args_list
            if call.args
        )
        self.assertIn(
            "2. Video",
            printed
        )
        self.assertNotIn(
            "No disponible.",
            printed
        )

    def test_design_target_unavailable_returns_to_its_menu(self):
        controller = RunController()

        with patch.object(
            controller,
            "_select_from_list",
            side_effect=(
                {"name": "Imagen", "pipeline": "image", "available": False},
                {"name": "Video", "pipeline": "video"},
            ),
        ), patch.object(controller, "_print") as print_mock:
            selected = controller.select_design_target()

        self.assertEqual("video", selected)
        printed = "\n".join(
            str(call.args[0])
            for call in print_mock.call_args_list
            if call.args
        )
        self.assertIn("No disponible.", printed)
        self.assertEqual(2, printed.count("DISE"))

    def test_zero_from_menu_raises_controlled_cancellation(self):
        controller = RunController()

        with patch("builtins.input", return_value="0"):
            with self.assertRaises(OperationalError) as caught:
                controller.select_visual_pipeline()

        self.assertEqual("CANCELLATION", caught.exception.context.family)
        self.assertIs(ExitKind.CANCELLATION, caught.exception.context.exit_kind)

    def test_design_profile_selection_uses_target_component_identity(self):
        controller = RunController()
        cases = (
            (
                "design_image",
                ProfileComponent.IMAGEN,
                "instagram",
                ("1",),
            ),
            (
                "design_image",
                ProfileComponent.IMAGEN,
                "youtube",
                ("2",),
            ),
            (
                "design_video",
                ProfileComponent.VIDEO,
                "instagram",
                ("1",),
            ),
            (
                "design_video",
                ProfileComponent.VIDEO,
                "youtube",
                ("2",),
            ),
        )

        for scope, component, platform, selections in cases:
            with self.subTest(scope=scope, platform=platform):
                with patch.object(
                    controller.subtitle_profile_resolver,
                    "discover_families",
                    side_effect=AssertionError(
                        "Diseño no debe descubrir subtítulos."
                    ),
                ), patch("builtins.input", side_effect=selections), patch(
                    "builtins.print"
                ) as print_mock:
                    selected = controller.select_profile(
                        scope
                    )

                profile_key = OperationalProfileKey(
                    component,
                    platform,
                    f"{component.value}_{platform}",
                )
                printed = "\n".join(
                    str(call.args[0])
                    for call in print_mock.call_args_list
                    if call.args
                )
                self.assertEqual(
                    profile_key,
                    selected["profile_key"]
                )
                self.assertEqual(
                    controller.profile_resolver.resolve_operational(
                        profile_key
                    ),
                    selected["path"]
                )
                self.assertNotIn("subtitle_profile_key", selected)
                self.assertNotIn("SUBTÍTULOS", printed)
                self.assertNotIn("FAMILIA", printed)
                self.assertNotIn("PERFIL", printed)

    def test_normal_script_selection_still_discovers_and_transports_subtitles(self):
        controller = RunController()

        with patch("builtins.input", side_effect=("1", "1", "1")), patch(
            "builtins.print"
        ) as print_mock:
            selected = controller.select_profile("script")

        printed = "\n".join(
            str(call.args[0])
            for call in print_mock.call_args_list
            if call.args
        )
        self.assertIn("subtitle_profile_key", selected)
        self.assertIn("SUBTÍTULOS", printed)
        self.assertIn("FAMILIA", printed)
        self.assertIn("PERFIL", printed)

    def test_image_modes_exclude_legacy_script_mode(self):
        controller = RunController()

        with patch(
            "builtins.input",
            return_value="1"
        ), patch(
            "builtins.print"
        ) as print_mock:
            selected = controller.select_pipeline_mode()

        self.assertEqual(
            "full",
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
            "2. Solo audio",
            printed
        )
        self.assertIn(
            "3. Audio + subtítulos",
            printed
        )
        self.assertIn(
            "4. Audio + subtítulos + storyboard",
            printed
        )
        self.assertNotIn(
            "Solo guion",
            printed
        )
        self.assertNotIn(
            "Proyecto completo sin subtítulos",
            printed,
        )

    def test_video_profile_selection_uses_main_visual_profiles(self):
        controller = RunController()

        with patch(
            "builtins.input",
            return_value="1"
        ), patch(
            "builtins.print"
        ) as print_mock:
            selected = controller.select_profile(
                "video"
            )

        printed = "\n".join(
            str(call.args[0])
            for call in print_mock.call_args_list
            if call.args
        )
        self.assertIn(
            selected["profile_key"].platform,
            ("instagram", "youtube"),
        )
        self.assertEqual(
            Path(
                "config/profiles/video/instagram/"
                "perfil_video_instagram.json"
            ),
            selected["path"]
        )
        self.assertIn(
            "PLATAFORMA",
            printed
        )

    def test_existing_modes_keep_internal_identifiers(self):
        cases = (
            ("1", "full"),
            ("2", "audio"),
            ("3", "subtitles"),
            ("4", "storyboard"),
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

    def test_script_modes_include_secondary_full_without_subtitles(self):
        controller = RunController()

        with patch(
            "builtins.input",
            return_value="5",
        ), patch(
            "builtins.print"
        ) as print_mock:
            selected = controller.select_pipeline_mode(
                include_full_without_subtitles=True,
            )

        printed = "\n".join(
            str(call.args[0])
            for call in print_mock.call_args_list
            if call.args
        )
        self.assertEqual("full_without_subtitles", selected)
        self.assertIn("1. Proyecto completo", printed)
        self.assertIn("2. Solo audio", printed)
        self.assertIn("3. Audio + subtítulos", printed)
        self.assertIn("4. Audio + subtítulos + storyboard", printed)
        self.assertIn(
            "5. Proyecto completo sin subtítulos",
            printed,
        )

    def test_script_entry_selects_image_destination_and_reuses_image_flow(self):
        controller = RunController()
        profile_key = OperationalProfileKey(
            ProfileComponent.GUION,
            "instagram",
            "guion_instagram",
        )
        subtitle_key = SubtitleProfileKey(
            ProfileComponent.GUION,
            "instagram",
            "dummy_subtitle_profile",
            "test_family",
        )

        with patch.object(
            controller,
            "select_visual_pipeline",
            return_value="script"
        ), patch.object(
            controller,
            "select_script_destination",
            return_value="image"
        ), patch.object(
            controller,
            "select_pipeline_mode",
            return_value="full"
        ) as mode_mock, patch.object(
            controller,
            "select_profile",
            return_value={
                "path": (
                    "config/profiles/guion/instagram/estandar/"
                    "perfil_guion_instagram.json"
                ),
                "profile_key": profile_key,
                "subtitle_profile_key": subtitle_key,
            }
        ) as profile_mock, patch.object(
            controller,
            "select_voice_config",
            return_value="masculina"
        ) as voice_mock, patch.object(
            controller,
            "select_music_category",
            return_value="random"
        ) as music_mock, patch.object(
            controller,
            "select_overlays_mode",
            return_value="smart"
        ) as overlays_mock, patch.object(
            controller,
            "select_intro_outro",
            return_value=None
        ) as intro_outro_mock, patch.object(
            controller,
            "ask_project_name",
            return_value="script image project"
        ) as project_mock, patch.object(
            controller,
            "ask_clear_output",
            return_value=False
        ) as clear_mock:
            options = controller.run()

        self.assertEqual(
            "image",
            options["visual_pipeline"]
        )
        self.assertEqual(
            "manual",
            options["script_source"]
        )
        self.assertEqual(
            "full",
            options["pipeline_mode"]
        )
        self.assertEqual(
            "script image project",
            options["project_name"]
        )
        mode_mock.assert_called_once_with(
            include_full_without_subtitles=True,
        )
        profile_mock.assert_called_once_with(
            "script"
        )
        project_mock.assert_called_once()
        clear_mock.assert_called_once()
        self.assertIs(subtitle_key, options["subtitle_profile_key"])
        voice_mock.assert_called_once()
        music_mock.assert_called_once()
        overlays_mock.assert_called_once()
        intro_outro_mock.assert_called_once()

    def test_run_includes_visual_pipeline_without_changing_existing_options(self):
        controller = RunController()
        profile_key = OperationalProfileKey(
            ProfileComponent.IMAGEN,
            "youtube",
            "imagen_youtube",
        )
        subtitle_key = SubtitleProfileKey(
            ProfileComponent.IMAGEN,
            "youtube",
            "dummy_subtitle_profile",
            "test_family",
        )

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
                "path": (
                    "config/profiles/imagen/youtube/estandar/"
                    "perfil_imagen_youtube.json"
                ),
                "profile_key": profile_key,
                "subtitle_profile_key": subtitle_key,
            }
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
            "select_intro_outro",
            return_value=None
        ) as intro_outro_mock, patch.object(
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
            "generated",
            options["script_source"]
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
        self.assertEqual(
            "",
            options["design_target"]
        )
        intro_outro_mock.assert_called_once()

    def test_script_entry_selects_video_destination_and_reuses_video_flow(self):
        controller = RunController()
        profile_key = OperationalProfileKey(
            ProfileComponent.GUION,
            "instagram",
            "guion_instagram",
        )
        subtitle_key = SubtitleProfileKey(
            ProfileComponent.GUION,
            "instagram",
            "dummy_subtitle_profile",
            "test_family",
        )

        with patch.object(
            controller,
            "select_visual_pipeline",
            return_value="script"
        ), patch.object(
            controller,
            "select_script_destination",
            return_value="video"
        ), patch.object(
            controller,
            "select_pipeline_mode",
            return_value="full"
        ) as mode_mock, patch.object(
            controller,
            "select_profile",
            return_value={
                "path": (
                    "config/profiles/guion/instagram/estandar/"
                    "perfil_guion_instagram.json"
                ),
                "profile_key": profile_key,
                "subtitle_profile_key": subtitle_key,
            }
        ) as profile_mock, patch.object(
            controller,
            "select_voice_config",
            return_value="masculina"
        ) as voice_mock, patch.object(
            controller,
            "select_music_category",
            return_value="random"
        ) as music_mock, patch.object(
            controller,
            "select_overlays_mode",
            return_value="smart"
        ) as overlays_mock, patch.object(
            controller,
            "select_intro_outro",
            return_value=None
        ) as intro_outro_mock, patch.object(
            controller,
            "ask_project_name",
            return_value="script video project"
        ) as project_mock, patch.object(
            controller,
            "ask_clear_output",
            return_value=False
        ) as clear_mock:
            options = controller.run()

        self.assertEqual(
            "video",
            options["visual_pipeline"]
        )
        self.assertEqual(
            "manual",
            options["script_source"]
        )
        self.assertEqual(
            "full",
            options["pipeline_mode"]
        )
        self.assertEqual(
            "",
            options["design_target"]
        )
        self.assertEqual(
            "script video project",
            options["project_name"]
        )
        mode_mock.assert_called_once_with(
            include_full_without_subtitles=True,
        )
        profile_mock.assert_called_once_with(
            "script"
        )
        project_mock.assert_called_once()
        clear_mock.assert_called_once()
        self.assertIs(subtitle_key, options["subtitle_profile_key"])
        voice_mock.assert_called_once()
        music_mock.assert_called_once()
        overlays_mock.assert_called_once()
        intro_outro_mock.assert_called_once()

    def test_video_entry_reuses_complete_image_user_flow(
        self
    ):
        controller = RunController()
        profile_key = OperationalProfileKey(
            ProfileComponent.VIDEO,
            "instagram",
            "video_instagram",
        )
        subtitle_key = SubtitleProfileKey(
            ProfileComponent.VIDEO,
            "instagram",
            "dummy_subtitle_profile",
            "test_family",
        )

        with patch.object(
            controller,
            "select_visual_pipeline",
            return_value="video"
        ), patch.object(
            controller,
            "select_pipeline_mode",
            return_value="full"
        ) as mode_mock, patch.object(
            controller,
            "select_profile",
            return_value={
                "path": (
                    "config/profiles/video/instagram/"
                    "perfil_video_instagram.json"
                ),
                "profile_key": profile_key,
                "subtitle_profile_key": subtitle_key,
            }
        ) as profile_mock, patch.object(
            controller,
            "select_voice_config",
            return_value="femenina"
        ) as voice_mock, patch.object(
            controller,
            "select_music_category",
            return_value="random"
        ) as music_mock, patch.object(
            controller,
            "select_overlays_mode",
            return_value="smart"
        ) as overlays_mock, patch.object(
            controller,
            "select_intro_outro",
            return_value=None
        ) as intro_outro_mock, patch.object(
            controller,
            "ask_project_name",
            return_value="video runtime"
        ), patch.object(
            controller,
            "ask_clear_output",
            return_value=False
        ):
            options = controller.run()

        mode_mock.assert_called_once()
        profile_mock.assert_called_once_with(
            "video"
        )
        self.assertIs(subtitle_key, options["subtitle_profile_key"])
        voice_mock.assert_called_once()
        music_mock.assert_called_once()
        overlays_mock.assert_called_once()
        intro_outro_mock.assert_called_once()
        self.assertEqual(
            "video",
            options["visual_pipeline"]
        )
        self.assertEqual(
            "full",
            options["pipeline_mode"]
        )
        self.assertNotIn("subtitle_config", options)
        self.assertEqual(
            "femenina",
            options["voice_config"]
        )
        self.assertEqual(
            "random",
            options["music_category"]
        )
        self.assertEqual(
            "smart",
            options["overlays_mode"]
        )

    def test_script_design_image_only_requests_design_image_inputs(self):
        controller = RunController()
        profile_key = OperationalProfileKey(
            ProfileComponent.IMAGEN,
            "instagram",
            "imagen_instagram",
        )

        with patch.object(
            controller,
            "select_visual_pipeline",
            return_value="script"
        ), patch.object(
            controller,
            "select_script_destination",
            return_value="design"
        ), patch.object(
            controller,
            "select_design_target",
            return_value="image"
        ) as design_target_mock, patch.object(
            controller,
            "select_pipeline_mode"
        ) as mode_mock, patch.object(
            controller,
            "select_profile",
            return_value={
                "path": controller.profile_resolver.resolve_operational(
                    profile_key
                ),
                "profile_key": profile_key,
            }
        ) as profile_mock, patch.object(
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
            "select_intro_outro"
        ) as intro_outro_mock, patch.object(
            controller,
            "ask_project_name",
            return_value="design image"
        ) as project_mock, patch.object(
            controller,
            "ask_clear_output",
            return_value=False
        ) as clear_mock:
            options = controller.run()

        design_target_mock.assert_called_once()
        mode_mock.assert_not_called()
        profile_mock.assert_called_once_with(
            "design_image"
        )
        voice_mock.assert_not_called()
        music_mock.assert_not_called()
        overlays_mock.assert_not_called()
        intro_outro_mock.assert_not_called()
        project_mock.assert_called_once()
        clear_mock.assert_called_once()
        self.assertEqual(
            "image",
            options["visual_pipeline"]
        )
        self.assertEqual(
            "manual_design",
            options["script_source"]
        )
        self.assertEqual(
            "image",
            options["design_target"]
        )
        self.assertEqual(
            "design_image",
            options["pipeline_mode"]
        )
        self.assertNotIn("subtitle_config", options)
        self.assertIsNone(options["subtitle_profile_key"])
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
        self.assertEqual(
            "imagen",
            options["profile_component"]
        )
        self.assertEqual(
            "instagram",
            options["profile_platform"]
        )
        self.assertEqual(
            "imagen_instagram",
            options["profile_id"]
        )

    def test_script_design_video_only_requests_design_video_inputs(self):
        controller = RunController()
        profile_key = OperationalProfileKey(
            ProfileComponent.VIDEO,
            "instagram",
            "video_instagram",
        )

        with patch.object(
            controller,
            "select_visual_pipeline",
            return_value="script"
        ), patch.object(
            controller,
            "select_script_destination",
            return_value="design"
        ), patch.object(
            controller,
            "select_design_target",
            return_value="video"
        ) as design_target_mock, patch.object(
            controller,
            "select_pipeline_mode"
        ) as mode_mock, patch.object(
            controller,
            "select_profile",
            return_value={
                "path": controller.profile_resolver.resolve_operational(
                    profile_key
                ),
                "profile_key": profile_key,
            }
        ) as profile_mock, patch.object(
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
            "select_intro_outro"
        ) as intro_outro_mock, patch.object(
            controller,
            "ask_project_name",
            return_value="design video"
        ) as project_mock, patch.object(
            controller,
            "ask_clear_output",
            return_value=False
        ) as clear_mock:
            options = controller.run()

        design_target_mock.assert_called_once()
        mode_mock.assert_not_called()
        profile_mock.assert_called_once_with(
            "design_video"
        )
        voice_mock.assert_not_called()
        music_mock.assert_not_called()
        overlays_mock.assert_not_called()
        intro_outro_mock.assert_not_called()
        project_mock.assert_called_once()
        clear_mock.assert_called_once()
        self.assertEqual(
            "video",
            options["visual_pipeline"]
        )
        self.assertEqual(
            "manual_design",
            options["script_source"]
        )
        self.assertEqual(
            "video",
            options["design_target"]
        )
        self.assertEqual(
            "design_video",
            options["pipeline_mode"]
        )
        self.assertNotIn("subtitle_config", options)
        self.assertIsNone(options["subtitle_profile_key"])
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
        self.assertEqual(
            "video",
            options["profile_component"]
        )
        self.assertEqual(
            "instagram",
            options["profile_platform"]
        )
        self.assertEqual(
            "video_instagram",
            options["profile_id"]
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
                "path": (
                    "config/profiles/imagen/youtube/estandar/"
                    "perfil_imagen_youtube.json"
                )
            }
        ), patch.object(
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
            "select_intro_outro"
        ) as intro_outro_mock, patch.object(
            controller,
            "ask_project_name",
            return_value="audio project"
        ), patch.object(
            controller,
            "ask_clear_output",
            return_value=False
        ):
            options = controller.run()

        voice_mock.assert_called_once()
        music_mock.assert_called_once()
        overlays_mock.assert_not_called()
        intro_outro_mock.assert_not_called()
        self.assertNotIn("subtitle_config", options)
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
            return_value="1"
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
            "1. Aleatoria",
            printed
        )
        self.assertIn(
            "2. Sin música",
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
            return_value="2"
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
                profile_key = OperationalProfileKey(
                    ProfileComponent.IMAGEN,
                    "youtube",
                    "imagen_youtube",
                )
                subtitle_key = SubtitleProfileKey(
                    ProfileComponent.IMAGEN,
                    "youtube",
                    "dummy_subtitle_profile",
                    "test_family",
                )

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
                            "config/profiles/imagen/youtube/estandar/"
                            "perfil_imagen_youtube.json"
                        ),
                        "profile_key": profile_key,
                        "subtitle_profile_key": subtitle_key,
                    }
                ), patch.object(
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
                    "select_intro_outro",
                    return_value=None
                ) as intro_outro_mock, patch.object(
                    controller,
                    "ask_project_name",
                    return_value="project"
                ), patch.object(
                    controller,
                    "ask_clear_output",
                    return_value=False
                ):
                    options = controller.run()

                self.assertIs(subtitle_key, options["subtitle_profile_key"])
                music_mock.assert_called_once()
                if pipeline_mode in {
                    "full",
                }:
                    overlays_mock.assert_called_once()
                    intro_outro_mock.assert_called_once()
                    self.assertEqual(
                        "smart",
                        options["overlays_mode"]
                    )
                else:
                    overlays_mock.assert_not_called()
                    intro_outro_mock.assert_not_called()
                    self.assertEqual(
                        "off",
                        options["overlays_mode"]
                    )
                self.assertNotIn("subtitle_config", options)

    def test_full_without_subtitles_skips_subtitle_selection(self):
        controller = RunController()
        profile_key = OperationalProfileKey(
            ProfileComponent.IMAGEN,
            "youtube",
            "imagen_youtube",
        )

        with patch.object(
            controller,
            "select_visual_pipeline",
            return_value="image",
        ), patch.object(
            controller,
            "select_pipeline_mode",
            return_value="full_without_subtitles",
        ), patch.object(
            controller,
            "select_profile",
            return_value={
                "path": (
                    "config/profiles/imagen/youtube/estandar/"
                    "perfil_imagen_youtube.json"
                ),
                "profile_key": profile_key,
            },
        ), patch.object(
            controller,
            "select_voice_config",
            return_value="masculina",
        ), patch.object(
            controller,
            "select_music_category",
            return_value=None,
        ), patch.object(
            controller,
            "select_overlays_mode",
            return_value="smart",
        ), patch.object(
            controller,
            "select_intro_outro",
            return_value=None,
        ), patch.object(
            controller,
            "ask_project_name",
            return_value="project",
        ), patch.object(
            controller,
            "ask_clear_output",
            return_value=False,
        ):
            options = controller.run()

        self.assertNotIn("subtitle_config", options)

    def test_overlay_menu_returns_on_when_enabled(
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
            "on",
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
                            "config/profiles/imagen/youtube/estandar/"
                            "perfil_imagen_youtube.json"
                        )
                    }
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
                    "select_intro_outro"
                ) as intro_outro_mock, patch.object(
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
                intro_outro_mock.assert_not_called()
                self.assertEqual(
                    "off",
                    options["overlays_mode"]
                )


if __name__ == "__main__":
    unittest.main()
