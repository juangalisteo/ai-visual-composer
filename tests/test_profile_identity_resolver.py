import json
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
    ProfileFamily,
    ProfileKey,
    ProfilePlatform,
)
from app.shared.profile_resolver import ProfileResolver


class ProfileIdentityResolverTest(unittest.TestCase):

    EXPECTED_PATHS = {
        "guion_instagram": Path(
            "config/profiles/guion/instagram/"
            "perfil_guion_instagram.json"
        ),
        "guion_youtube": Path(
            "config/profiles/guion/youtube/"
            "perfil_guion_youtube.json"
        ),
        "imagen_instagram": Path(
            "config/profiles/imagen/instagram/"
            "perfil_imagen_instagram.json"
        ),
        "imagen_youtube": Path(
            "config/profiles/imagen/youtube/"
            "perfil_imagen_youtube.json"
        ),
        "video_instagram": Path(
            "config/profiles/video/instagram/"
            "perfil_video_instagram.json"
        ),
        "video_youtube": Path(
            "config/profiles/video/youtube/"
            "perfil_video_youtube.json"
        ),
        "studio_instagram": Path(
            "config/profiles/studio/instagram/"
            "perfil_studio_instagram.json"
        ),
        "studio_youtube": Path(
            "config/profiles/studio/youtube/"
            "perfil_studio_youtube.json"
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

    def test_design_profile_key_requires_a_concrete_canonical_identity(self):
        key = ProfileKey.for_component(
            "video",
            "instagram",
            family=ProfileFamily.DESIGN,
            profile_id="video_instagram_design_modo_conciencia_studio_1",
        )

        self.assertEqual(ProfileFamily.DESIGN, key.family)
        self.assertEqual(
            "video_instagram_design_modo_conciencia_studio_1",
            key.profile_id,
        )
        with self.assertRaisesRegex(ValueError, "profile_id concreto"):
            ProfileKey.for_component("video", "instagram", "design")
        with self.assertRaisesRegex(ValueError, "profile_id incompatible"):
            ProfileKey(
                "video",
                "instagram",
                "video_instagram_design_",
                "design",
            )

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

    def test_missing_official_file_fails_without_legacy_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            legacy_path = (
                Path(directory)
                / "instagram"
                / "modo_conciencia.json"
            )
            legacy_path.parent.mkdir(parents=True)
            legacy_path.write_text("{}", encoding="utf-8")
            resolver = ProfileResolver(directory)
            profile_key = ProfileKey.for_component(
                ProfileComponent.VIDEO,
                ProfilePlatform.INSTAGRAM
            )

            with self.assertRaisesRegex(
                FileNotFoundError,
                "No existe el perfil esperado"
            ):
                resolver.resolve(profile_key)

    def test_missing_official_wan_file_fails_without_legacy_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            legacy_path = (
                Path(directory)
                / "video"
                / "instagram.json"
            )
            legacy_path.parent.mkdir(parents=True)
            legacy_path.write_text("{}", encoding="utf-8")
            resolver = ProfileResolver(directory)
            profile_key = ProfileKey.for_component(
                ProfileComponent.VIDEO,
                ProfilePlatform.INSTAGRAM
            )

            with self.assertRaisesRegex(
                FileNotFoundError,
                "No existe el perfil esperado"
            ):
                resolver.resolve_video_component(profile_key)

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

    def test_design_discovery_is_component_scoped_and_youtube_is_system_only(self):
        for component in ProfileComponent:
            with self.subTest(component=component.value):
                designs = self.resolver.discover(
                    component,
                    ProfilePlatform.INSTAGRAM,
                    ProfileFamily.DESIGN,
                )
                self.assertEqual(1, len(designs))
                key, display_name = designs[0]
                self.assertEqual(component, key.component)
                self.assertEqual(ProfileFamily.DESIGN, key.family)
                self.assertEqual(
                    f"{component.value}_instagram_design_modo_conciencia_studio_1",
                    key.profile_id,
                )
                self.assertEqual("Modo Conciencia - Studio #1", display_name)
                self.assertEqual(
                    Path("config/profiles")
                    / component.value
                    / "instagram"
                    / "design"
                    / "modo_conciencia_studio_1.json",
                    self.resolver.resolve(key),
                )
                self.assertEqual(
                    (),
                    self.resolver.discover(
                        component,
                        ProfilePlatform.YOUTUBE,
                        ProfileFamily.DESIGN,
                    ),
                )

    def test_design_discovery_ignores_a_file_whose_name_disagrees_with_its_identity(self):
        source = Path(
            "config/profiles/video/instagram/design/"
            "modo_conciencia_studio_1.json"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "video/instagram/design/not_the_profile_id.json"
            target.parent.mkdir(parents=True)
            target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

            self.assertEqual(
                (),
                ProfileResolver(root).discover(
                    "video", "instagram", ProfileFamily.DESIGN
                ),
            )

    def test_design_without_declared_subtitle_style_is_not_a_menu_option(self):
        source = Path(
            "config/profiles/video/instagram/design/"
            "modo_conciencia_studio_1.json"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "video/instagram/design/modo_conciencia_studio_1.json"
            target.parent.mkdir(parents=True)
            data = json.loads(source.read_text(encoding="utf-8"))
            del data["subtitle_config"]
            target.write_text(json.dumps(data), encoding="utf-8")

            self.assertEqual(
                (),
                ProfileResolver(root).discover(
                    "video", "instagram", ProfileFamily.DESIGN
                ),
            )

    def test_design_selector_uses_visible_labels_for_all_instagram_components(self):
        cases = {
            "script": ProfileComponent.GUION,
            "image": ProfileComponent.IMAGEN,
            "video": ProfileComponent.VIDEO,
            "studio": ProfileComponent.STUDIO,
        }
        for scope, component in cases.items():
            with self.subTest(scope=scope), patch(
                "builtins.input", side_effect=("1", "2", "1")
            ), patch("builtins.print") as print_mock:
                selected = RunController().select_profile(scope)

            printed = "\n".join(
                str(call.args[0])
                for call in print_mock.call_args_list
                if call.args
            )
            self.assertEqual(ProfileFamily.DESIGN, selected["profile_key"].family)
            self.assertEqual(component, selected["profile_key"].component)
            self.assertIn("ESTILO DE SUBT", printed)
            self.assertIn("1. EST", printed)
            self.assertIn("2. DISE", printed)
            self.assertIn("Modo Conciencia - Studio #1", printed)
            self.assertNotIn("FAMILIA", printed)
            self.assertNotIn("SYSTEM", printed)
            self.assertNotIn("DESIGN", printed)

    def test_youtube_shows_only_the_discovered_standard_family(self):
        for scope in ("script", "image", "video", "studio"):
            with self.subTest(scope=scope), patch(
                "builtins.input", side_effect=("2", "1")
            ), patch("builtins.print") as print_mock:
                selected = RunController().select_profile(scope)

            printed = "\n".join(
                str(call.args[0])
                for call in print_mock.call_args_list
                if call.args
            )
            self.assertEqual(ProfileFamily.SYSTEM, selected["profile_key"].family)
            self.assertIn("ESTILO DE SUBT", printed)
            self.assertIn("1. EST", printed)
            self.assertNotIn("DISE", printed)

    def test_image_and_video_keep_distinct_identity_and_physical_files(self):
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
        self.assertNotEqual(
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

    def test_design_uses_target_component_identity_without_becoming_component(self):
        self.assertNotIn(
            "design",
            tuple(
                item.value
                for item in ProfileComponent
            )
        )
        cases = (
            (
                ProfileComponent.IMAGEN,
                ProfilePlatform.INSTAGRAM,
                "imagen_instagram",
            ),
            (
                ProfileComponent.IMAGEN,
                ProfilePlatform.YOUTUBE,
                "imagen_youtube",
            ),
            (
                ProfileComponent.VIDEO,
                ProfilePlatform.INSTAGRAM,
                "video_instagram",
            ),
            (
                ProfileComponent.VIDEO,
                ProfilePlatform.YOUTUBE,
                "video_youtube",
            ),
        )
        for component, platform, profile_id in cases:
            with self.subTest(profile_id=profile_id):
                profile_key = ProfileKey.for_component(
                    component,
                    platform
                )
                self.assertEqual(
                    profile_id,
                    profile_key.profile_id
                )
                self.assertNotIn(
                    "diseno",
                    self.resolver.resolve(
                        profile_key
                    ).parts
                )

        self.assertFalse(
            hasattr(
                self.resolver,
                "resolve_design"
            )
        )

    def test_config_manager_identity_matches_component_profile_files(self):
        for component in ProfileComponent:
            for platform in ProfilePlatform:
                with self.subTest(
                    component=component.value,
                    platform=platform.value
                ):
                    profile_key = ProfileKey.for_component(
                        component,
                        platform
                    )
                    expected_profile = self.resolver.load(
                        profile_key
                    )

                    with patch.dict(
                        os.environ,
                        {
                            "MC_PROFILE_COMPONENT": component.value,
                            "MC_PROFILE_PLATFORM": platform.value,
                            "MC_PROFILE_ID": profile_key.profile_id,
                        },
                        clear=True
                    ):
                        identity_profile = (
                            ConfigManager().get_profile_config()
                        )

                    self.assertEqual(
                        expected_profile,
                        identity_profile
                    )

    def test_config_manager_defaults_missing_family_to_system_and_loads_design(self):
        with patch.dict(
            os.environ,
            {
                "MC_PROFILE_COMPONENT": "video",
                "MC_PROFILE_PLATFORM": "instagram",
                "MC_PROFILE_ID": "video_instagram",
            },
            clear=True,
        ):
            self.assertEqual(
                ProfileFamily.SYSTEM,
                ConfigManager().get_profile_key().family,
            )

        design_key = ProfileKey.for_component(
            "video",
            "instagram",
            family="design",
            profile_id="video_instagram_design_modo_conciencia_studio_1",
        )
        with patch.dict(
            os.environ,
            {
                "MC_PROFILE_COMPONENT": "video",
                "MC_PROFILE_PLATFORM": "instagram",
                "MC_PROFILE_ID": design_key.profile_id,
                "MC_PROFILE_FAMILY": "design",
            },
            clear=True,
        ):
            self.assertEqual(
                self.resolver.load(design_key),
                ConfigManager().get_profile_config(),
            )

    def test_official_identity_does_not_require_profile_path_adapter(self):
        for component in ProfileComponent:
            for platform in ProfilePlatform:
                with self.subTest(
                    component=component.value,
                    platform=platform.value
                ):
                    profile_key = ProfileKey.for_component(
                        component,
                        platform
                    )
                    with patch.dict(
                        os.environ,
                        {
                            "MC_PROFILE_COMPONENT": component.value,
                            "MC_PROFILE_PLATFORM": platform.value,
                            "MC_PROFILE_ID": profile_key.profile_id,
                        },
                        clear=True
                    ):
                        profile = ConfigManager().get_profile_config()

                    self.assertEqual(
                        self.resolver.load(
                            profile_key
                        ),
                        profile
                    )

    def test_config_manager_rejects_partial_identity(self):
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

    def test_external_profile_path_cannot_override_identity(self):
        with patch.dict(
            os.environ,
            {
                "MC_PROFILE_PATH": (
                    "ignored-profile.json"
                ),
                "MC_PROFILE_COMPONENT": "video",
                "MC_PROFILE_PLATFORM": "instagram",
                "MC_PROFILE_ID": "video_instagram",
            },
            clear=True
        ):
            profile = ConfigManager().get_profile_config()

        expected = self.resolver.load(
            ProfileKey.for_component(
                ProfileComponent.VIDEO,
                ProfilePlatform.INSTAGRAM
            )
        )
        self.assertEqual(expected, profile)

    def test_missing_identity_fails_without_app_fallback(self):
        with patch.dict(
            os.environ,
            {},
            clear=True
        ):
            manager = ConfigManager()
            with patch.object(
                manager,
                "get_app_config",
                side_effect=AssertionError(
                    "app.json must not resolve profiles"
                )
            ), self.assertRaisesRegex(
                ValueError,
                "Falta identidad estructurada de perfil"
            ):
                manager.get_profile_config()

    def test_external_profile_path_without_identity_does_not_resolve(self):
        with patch.dict(
            os.environ,
            {
                "MC_PROFILE_PATH": (
                    "ignored-profile.json"
                )
            },
            clear=True
        ):
            with self.assertRaisesRegex(
                ValueError,
                "Falta identidad estructurada de perfil"
            ):
                ConfigManager().get_profile_config()

    def test_app_json_no_longer_declares_profile_selection(self):
        app = ConfigManager().get_app_config()

        self.assertNotIn("platform", app)
        self.assertNotIn("profile", app)
        self.assertEqual(
            "MODO CONCIENCIA | IA",
            app["project_name"]
        )
        self.assertEqual("es", app["language"])

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

    def test_run_controller_selects_design_only_after_family_and_design_choice(self):
        controller = RunController()
        with patch("builtins.input", side_effect=("1", "2", "1")), patch(
            "builtins.print"
        ) as print_mock:
            selected = controller.select_profile("video")

        self.assertEqual(ProfileFamily.DESIGN, selected["profile_key"].family)
        self.assertEqual(
            "video_instagram_design_modo_conciencia_studio_1",
            selected["profile_key"].profile_id,
        )
        printed = "\n".join(
            str(call.args[0])
            for call in print_mock.call_args_list
            if call.args
        )
        self.assertIn("ESTILO DE SUBT", printed)
        self.assertIn("1. EST", printed)
        self.assertIn("2. DISE", printed)
        self.assertIn("Modo Conciencia - Studio #1", printed)

    def test_run_controller_keeps_youtube_system_automatic_when_design_is_absent(self):
        controller = RunController()
        with patch("builtins.input", side_effect=("2", "1")), patch(
            "builtins.print"
        ) as print_mock:
            selected = controller.select_profile("studio")

        self.assertEqual(ProfileFamily.SYSTEM, selected["profile_key"].family)
        printed = "\n".join(
            str(call.args[0])
            for call in print_mock.call_args_list
            if call.args
        )
        self.assertIn("ESTILO DE SUBT", printed)
        self.assertIn("1. EST", printed)
        self.assertNotIn("DISE", printed)

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
        self.assertNotIn("profile_path", options)

    def test_main_transports_only_structured_profile_identity(self):
        options = {
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
        ) as iniciar_mock:
            controller_mock.return_value.run.return_value = options

            self.assertEqual(0, main.main())
            self.assertNotIn("MC_PROFILE_PATH", os.environ)
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
            self.assertEqual("system", os.environ["MC_PROFILE_FAMILY"])
            profile_key = ProfileKey.for_component(
                ProfileComponent.VIDEO,
                ProfilePlatform.INSTAGRAM
            )
            self.assertEqual(
                self.resolver.load(profile_key),
                ConfigManager().get_profile_config()
            )
            self.assertNotIn(
                "MC_SUBTITLE_CONFIG",
                os.environ
            )
            iniciar_mock.assert_called_once_with(
                subtitle_style="word_by_word"
            )

    def test_main_transports_design_family_without_a_profile_path(self):
        options = {
            "profile_component": "imagen",
            "profile_platform": "instagram",
            "profile_id": "imagen_instagram_design_modo_conciencia_studio_1",
            "profile_family": "design",
            "subtitle_config": None,
            "voice_config": "",
            "music_category": None,
            "overlays_mode": "off",
            "project_name": "design identity",
            "visual_pipeline": "image",
            "script_source": "generated",
            "design_target": "",
            "pipeline_mode": "audio",
            "clear_output": False,
        }
        with patch.dict(os.environ, {}, clear=True), patch(
            "main.RunController"
        ) as controller_mock, patch("main.iniciar") as iniciar_mock:
            controller_mock.return_value.run.return_value = options

            self.assertEqual(0, main.main())
            self.assertEqual("design", os.environ["MC_PROFILE_FAMILY"])
            self.assertEqual(
                "imagen_instagram_design_modo_conciencia_studio_1",
                os.environ["MC_PROFILE_ID"],
            )
            self.assertNotIn("MC_PROFILE_PATH", os.environ)
        iniciar_mock.assert_called_once_with(subtitle_style=None)

    def test_productive_runtime_has_no_profile_path_environment_contract(self):
        paths = (
            Path("main.py"),
            *Path("app").rglob("*.py"),
            *Path("certification").rglob("*.py"),
        )

        for path in paths:
            with self.subTest(path=path):
                self.assertNotIn(
                    "MC_PROFILE_PATH",
                    path.read_text(encoding="utf-8")
                )


if __name__ == "__main__":
    unittest.main()
