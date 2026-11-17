import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from app.controllers.run_controller import RunController
from app.shared.config_manager import ConfigManager
from app.shared.profile_identity import (
    OperationalProfileKey,
    ProfileComponent,
)

from tests.test_menu_helpers import MenuAnswers


class ScriptComponentProfilesTest(
    unittest.TestCase
):

    def test_script_profiles_are_independent_component_files(self):
        script_profiles = (
            Path(
                "config/profiles/guion/vertical/"
                "perfil_guion_vertical.json"
            ),
            Path(
                "config/profiles/guion/horizontal/"
                "perfil_guion_horizontal.json"
            ),
        )

        for script_profile in script_profiles:
            with self.subTest(
                script_profile=script_profile
            ):
                self.assertTrue(
                    script_profile.is_file()
                )
                self.assertFalse(
                    script_profile.is_symlink()
                )

        self.assertFalse(os.path.samefile(*script_profiles))

    def test_script_profiles_preserve_source_orientation(self):
        vertical = json.loads(
            Path(
                "config/profiles/guion/vertical/"
                "perfil_guion_vertical.json"
            ).read_text(
                encoding="utf-8"
            )
        )
        horizontal = json.loads(
            Path(
                "config/profiles/guion/horizontal/"
                "perfil_guion_horizontal.json"
            ).read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(
            "vertical",
            vertical["format"]
        )
        self.assertEqual(
            (1080, 1920),
            (
                vertical["video_style"]["width"],
                vertical["video_style"]["height"],
            ),
        )
        self.assertEqual(
            "horizontal",
            horizontal["format"]
        )
        self.assertEqual(
            (1920, 1080),
            (
                horizontal["video_style"]["width"],
                horizontal["video_style"]["height"],
            ),
        )
        self.assertNotIn("resolution", vertical)
        self.assertNotIn("resolution", horizontal)

    def test_script_profile_selection_uses_script_profile_directory(self):
        controller = RunController()

        answers = MenuAnswers("Vertical 9:16", "ESTILO ESTÁNDAR", "Doble línea")
        with patch(
            "builtins.input",
            side_effect=answers.input
        ), patch(
            "builtins.print",
            side_effect=answers.print
        ) as print_mock:
            selected = controller.select_profile(
                "script"
            )

        self.assertEqual(
            Path(
                "config/profiles/guion/vertical/"
                "perfil_guion_vertical.json"
            ),
            selected["path"]
        )
        printed = "\n".join(
            str(call.args[0])
            for call in print_mock.call_args_list
            if call.args
        )
        self.assertIn(
            "1. Vertical 9:16",
            printed
        )
        self.assertIn(
            "2. Horizontal 16:9",
            printed
        )
        self.assertNotIn(
            "Modo Conciencia",
            printed
        )

    def test_image_profile_selection_excludes_script_profiles(self):
        controller = RunController()

        answers = MenuAnswers(
            "Vertical 9:16",
            "MODO CONCIENCIA",
            "Modo Conciencia | Palabra única",
        )
        with patch(
            "builtins.input",
            side_effect=answers.input
        ), patch(
            "builtins.print",
            side_effect=answers.print
        ) as print_mock:
            selected = controller.select_profile(
                "image"
            )

        self.assertEqual(
            Path(
                "config/profiles/imagen/vertical/"
                "perfil_imagen_vertical.json"
            ),
            selected["path"]
        )
        printed = "\n".join(
            str(call.args[0])
            for call in print_mock.call_args_list
            if call.args
        )
        self.assertIn(
            "Vertical",
            printed
        )
        self.assertNotIn(
            "Guion",
            printed
        )

    def test_config_manager_loads_selected_script_profile_identity(self):
        profile_key = OperationalProfileKey(
            ProfileComponent.GUION,
            "horizontal",
            "guion_horizontal",
        )
        profile = ConfigManager(
            operational_profile_key=profile_key
        ).get_profile_config()

        self.assertEqual(
            "horizontal",
            profile["format"]
        )
        self.assertEqual(
            "horizontal",
            profile["format"]
        )


if __name__ == "__main__":
    unittest.main()
