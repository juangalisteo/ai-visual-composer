import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from app.controllers.run_controller import RunController
from app.shared.config_manager import ConfigManager
from app.shared.profile_identity import (
    ProfileComponent,
    ProfileKey,
    ProfilePlatform,
)


class ScriptComponentProfilesTest(
    unittest.TestCase
):

    def test_script_profiles_are_independent_component_files(self):
        script_profiles = (
            Path(
                "config/profiles/guion/instagram/"
                "perfil_guion_instagram.json"
            ),
            Path(
                "config/profiles/guion/youtube/"
                "perfil_guion_youtube.json"
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
        instagram = json.loads(
            Path(
                "config/profiles/guion/instagram/"
                "perfil_guion_instagram.json"
            ).read_text(
                encoding="utf-8"
            )
        )
        youtube = json.loads(
            Path(
                "config/profiles/guion/youtube/"
                "perfil_guion_youtube.json"
            ).read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(
            "vertical",
            instagram["format"]
        )
        self.assertEqual(
            "1080x1920",
            instagram["resolution"]
        )
        self.assertEqual(
            "horizontal",
            youtube["format"]
        )
        self.assertEqual(
            "1920x1080",
            youtube["resolution"]
        )

    def test_script_profile_selection_uses_script_profile_directory(self):
        controller = RunController()

        with patch(
            "builtins.input",
            return_value="1"
        ), patch(
            "builtins.print"
        ) as print_mock:
            selected = controller.select_profile(
                "script"
            )

        self.assertEqual(
            Path(
                "config/profiles/guion/instagram/"
                "perfil_guion_instagram.json"
            ),
            selected["path"]
        )
        printed = "\n".join(
            str(call.args[0])
            for call in print_mock.call_args_list
            if call.args
        )
        self.assertIn(
            "1. Instagram",
            printed
        )
        self.assertIn(
            "2. YouTube",
            printed
        )
        self.assertNotIn(
            "Modo Conciencia",
            printed
        )

    def test_image_profile_selection_excludes_script_profiles(self):
        controller = RunController()

        with patch(
            "builtins.input",
            return_value="1"
        ), patch(
            "builtins.print"
        ) as print_mock:
            selected = controller.select_profile(
                "image"
            )

        self.assertEqual(
            Path(
                "config/profiles/imagen/instagram/"
                "perfil_imagen_instagram.json"
            ),
            selected["path"]
        )
        printed = "\n".join(
            str(call.args[0])
            for call in print_mock.call_args_list
            if call.args
        )
        self.assertIn(
            "Instagram",
            printed
        )
        self.assertNotIn(
            "Guion",
            printed
        )

    def test_config_manager_loads_selected_script_profile_identity(self):
        profile_key = ProfileKey.for_component(
            ProfileComponent.GUION,
            ProfilePlatform.YOUTUBE
        )
        with patch.dict(
            os.environ,
            {
                "MC_PROFILE_COMPONENT": "guion",
                "MC_PROFILE_PLATFORM": "youtube",
                "MC_PROFILE_ID": profile_key.profile_id,
            },
            clear=True
        ):
            profile = ConfigManager().get_profile_config()

        self.assertEqual(
            "youtube",
            profile["platform"]
        )
        self.assertEqual(
            "horizontal",
            profile["format"]
        )


if __name__ == "__main__":
    unittest.main()
