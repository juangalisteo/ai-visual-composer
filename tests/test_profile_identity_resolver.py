import os
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

import main
from app.controllers.run_controller import RunController
from app.shared.config_manager import ConfigManager
from app.shared.profile_identity import (
    ProfileComponent,
    ProfileKey,
    ProfilePlatform,
)
from app.shared.profile_resolver import ProfileResolver


class ProfileIdentityResolverTest(unittest.TestCase):

    EXPECTED_PATHS = {
        "guion_instagram": Path(
            "config/profiles/guion/instagram.json"
        ),
        "guion_youtube": Path(
            "config/profiles/guion/youtube.json"
        ),
        "imagen_instagram": Path(
            "config/profiles/instagram/modo_conciencia.json"
        ),
        "imagen_youtube": Path(
            "config/profiles/youtube/modo_conciencia.json"
        ),
        "video_instagram": Path(
            "config/profiles/instagram/modo_conciencia.json"
        ),
        "video_youtube": Path(
            "config/profiles/youtube/modo_conciencia.json"
        ),
    }

    def setUp(self):
        self.resolver = ProfileResolver()

    def test_profile_key_is_immutable_and_canonical(self):
        profile_key = ProfileKey.for_component(
            "video",
            "instagram"
        )

        self.assertEqual(
            ProfileComponent.VIDEO,
            profile_key.component
        )
        self.assertEqual(
            ProfilePlatform.INSTAGRAM,
            profile_key.platform
        )
        self.assertEqual(
            "video_instagram",
            profile_key.profile_id
        )
        with self.assertRaises(FrozenInstanceError):
            profile_key.profile_id = "video_youtube"

    def test_resolves_complete_valid_matrix_exactly(self):
        for component in ProfileComponent:
            for platform in ProfilePlatform:
                profile_key = ProfileKey.for_component(
                    component,
                    platform
                )
                with self.subTest(profile_id=profile_key.profile_id):
                    self.assertEqual(
                        self.EXPECTED_PATHS[
                            profile_key.profile_id
                        ],
                        self.resolver.resolve(
                            profile_key
                        )
                    )

    def test_rejects_incompatible_component_platform_and_profile_ids(self):
        invalid_cases = (
            ("video", "instagram", "video_youtube"),
            ("imagen", "instagram", "video_instagram"),
            ("guion", "youtube", "guion_instagram"),
            ("video", "youtube", "unknown_profile"),
        )

        for component, platform, profile_id in invalid_cases:
            with self.subTest(
                component=component,
                platform=platform,
                profile_id=profile_id
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "profile_id incompatible"
                ):
                    ProfileKey(
                        component,
                        platform,
                        profile_id
                    )

    def test_rejects_unknown_component_and_platform(self):
        with self.assertRaisesRegex(
            ValueError,
            "Componente de perfil no soportado"
        ):
            ProfileKey(
                "design",
                "instagram",
                "design_instagram"
            )

        with self.assertRaisesRegex(
            ValueError,
            "Plataforma de perfil no soportado"
        ):
            ProfileKey(
                "video",
                "tiktok",
                "video_tiktok"
            )

    def test_missing_legacy_file_fails_without_cross_platform_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            resolver = ProfileResolver(directory)
            profile_key = ProfileKey.for_component(
                ProfileComponent.VIDEO,
                ProfilePlatform.INSTAGRAM
            )

            with self.assertRaisesRegex(
                FileNotFoundError,
                "No existe el perfil legacy esperado"
            ):
                resolver.resolve(profile_key)

    def test_platform_resolution_never_crosses_platforms(self):
        for component in ProfileComponent:
            instagram_key = ProfileKey.for_component(
                component,
                ProfilePlatform.INSTAGRAM
            )
            youtube_key = ProfileKey.for_component(
                component,
                ProfilePlatform.YOUTUBE
            )

            instagram_path = self.resolver.resolve(
                instagram_key
            )
            youtube_path = self.resolver.resolve(
                youtube_key
            )

            self.assertNotIn(
                "youtube",
                instagram_path.parts
            )
            self.assertNotIn(
                "instagram",
                youtube_path.parts
            )

    def test_image_and_video_keep_distinct_identity_on_shared_legacy_file(self):
        image_key = ProfileKey.for_component(
            ProfileComponent.IMAGEN,
            ProfilePlatform.INSTAGRAM
        )
        video_key = ProfileKey.for_component(
            ProfileComponent.VIDEO,
            ProfilePlatform.INSTAGRAM
        )

        self.assertNotEqual(
            image_key,
            video_key
        )
        self.assertNotEqual(
            image_key.profile_id,
            video_key.profile_id
        )
        self.assertEqual(
            self.resolver.resolve(image_key),
            self.resolver.resolve(video_key)
        )

    def test_wan_resolution_requires_video_identity(self):
        image_key = ProfileKey.for_component(
            ProfileComponent.IMAGEN,
            ProfilePlatform.INSTAGRAM
        )
        with self.assertRaisesRegex(
            ValueError,
            "solo pertenece al componente video"
        ):
            self.resolver.resolve_video_component(
                image_key
            )

    def test_design_stays_a_legacy_route_not_a_component(self):
        self.assertNotIn(
            "design",
            tuple(
                item.value
                for item in ProfileComponent
            )
        )
        self.assertEqual(
            Path(
                "config/profiles/diseno/imagen/instagram.json"
            ),
            self.resolver.resolve_design(
                ProfileComponent.IMAGEN,
                ProfilePlatform.INSTAGRAM
            )
        )
        self.assertEqual(
            Path(
                "config/profiles/diseno/video/youtube.json"
            ),
            self.resolver.resolve_design(
                ProfileComponent.VIDEO,
                ProfilePlatform.YOUTUBE
            )
        )
        with self.assertRaisesRegex(
            ValueError,
            "solo admite los destinos imagen y video"
        ):
            self.resolver.resolve_design(
                ProfileComponent.GUION,
                ProfilePlatform.INSTAGRAM
            )

    def test_config_manager_accepts_identity_and_legacy_adapter(self):
        profile_key = ProfileKey.for_component(
            ProfileComponent.IMAGEN,
            ProfilePlatform.YOUTUBE
        )
        profile_path = self.resolver.resolve(
            profile_key
        )

        with patch.dict(
            os.environ,
            {
                "MC_PROFILE_PATH": str(profile_path),
                "MC_PROFILE_COMPONENT": "",
                "MC_PROFILE_PLATFORM": "",
                "MC_PROFILE_ID": "",
            },
            clear=True
        ):
            legacy_profile = ConfigManager().get_profile_config()

        with patch.dict(
            os.environ,
            {
                "MC_PROFILE_PATH": str(profile_path),
                "MC_PROFILE_COMPONENT": "imagen",
                "MC_PROFILE_PLATFORM": "youtube",
                "MC_PROFILE_ID": "imagen_youtube",
            },
            clear=True
        ):
            identity_profile = ConfigManager().get_profile_config()

        self.assertEqual(
            legacy_profile,
            identity_profile
        )

    def test_config_manager_rejects_partial_or_conflicting_identity(self):
        with patch.dict(
            os.environ,
            {
                "MC_PROFILE_COMPONENT": "video",
                "MC_PROFILE_PLATFORM": "",
                "MC_PROFILE_ID": "",
            },
            clear=True
        ):
            with self.assertRaisesRegex(
                ValueError,
                "requiere component, platform y profile_id"
            ):
                ConfigManager().get_profile_config()

        with patch.dict(
            os.environ,
            {
                "MC_PROFILE_PATH": (
                    "config/profiles/youtube/modo_conciencia.json"
                ),
                "MC_PROFILE_COMPONENT": "video",
                "MC_PROFILE_PLATFORM": "instagram",
                "MC_PROFILE_ID": "video_instagram",
            },
            clear=True
        ):
            with self.assertRaisesRegex(
                ValueError,
                "MC_PROFILE_PATH no coincide"
            ):
                ConfigManager().get_profile_config()

    def test_app_json_fallback_remains_available(self):
        with patch.dict(
            os.environ,
            {},
            clear=True
        ):
            profile = ConfigManager().get_profile_config()

        self.assertEqual("youtube", profile["platform"])
        self.assertEqual("horizontal", profile["format"])

    def test_run_controller_returns_structured_identity_for_main_routes(self):
        expected_components = {
            "script": ProfileComponent.GUION,
            "image": ProfileComponent.IMAGEN,
            "video": ProfileComponent.VIDEO,
        }

        for scope, expected_component in expected_components.items():
            with self.subTest(scope=scope), patch(
                "builtins.input",
                return_value="1"
            ):
                selected = RunController().select_profile(
                    scope
                )

            self.assertEqual(
                expected_component,
                selected["profile_key"].component
            )
            self.assertEqual(
                ProfilePlatform.INSTAGRAM,
                selected["profile_key"].platform
            )

    def test_run_controller_transports_selected_profile_key(self):
        controller = RunController()
        profile_key = ProfileKey.for_component(
            ProfileComponent.VIDEO,
            ProfilePlatform.INSTAGRAM
        )

        with patch.object(
            controller,
            "select_visual_pipeline",
            return_value="video"
        ), patch.object(
            controller,
            "select_pipeline_mode",
            return_value="audio"
        ), patch.object(
            controller,
            "select_profile",
            return_value={
                "path": self.resolver.resolve(profile_key),
                "profile_key": profile_key,
            }
        ), patch.object(
            controller,
            "select_voice_config",
            return_value="femenina"
        ), patch.object(
            controller,
            "select_music_category",
            return_value=None
        ), patch.object(
            controller,
            "ask_project_name",
            return_value="profile identity"
        ), patch.object(
            controller,
            "ask_clear_output",
            return_value=False
        ):
            options = controller.run()

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
        self.assertEqual(
            str(self.resolver.resolve(profile_key)),
            options["profile_path"]
        )

    def test_main_transports_profile_identity_without_removing_path_adapter(self):
        options = {
            "profile_path": (
                "config/profiles/instagram/modo_conciencia.json"
            ),
            "profile_component": "video",
            "profile_platform": "instagram",
            "profile_id": "video_instagram",
            "subtitle_config": "word_by_word",
            "voice_config": "femenina",
            "music_category": None,
            "overlays_mode": "off",
            "project_name": "profile identity",
            "visual_pipeline": "video",
            "script_source": "generated",
            "design_target": "",
            "pipeline_mode": "audio",
            "clear_output": False,
        }

        with patch.dict(
            os.environ,
            {},
            clear=True
        ), patch(
            "main.RunController"
        ) as controller_mock, patch(
            "main.iniciar"
        ):
            controller_mock.return_value.run.return_value = options

            self.assertEqual(0, main.main())
            self.assertEqual(
                options["profile_path"],
                os.environ["MC_PROFILE_PATH"]
            )
            self.assertEqual(
                "video",
                os.environ["MC_PROFILE_COMPONENT"]
            )
            self.assertEqual(
                "instagram",
                os.environ["MC_PROFILE_PLATFORM"]
            )
            self.assertEqual(
                "video_instagram",
                os.environ["MC_PROFILE_ID"]
            )


if __name__ == "__main__":
    unittest.main()
