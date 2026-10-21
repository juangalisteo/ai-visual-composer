import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main
import app.shared.profile_identity as profile_identity
from app.controllers.run_controller import RunController
from app.shared.config_manager import ConfigManager
from app.shared.profile_identity import (
    OperationalProfileKey,
    ProfileComponent,
    coerce_profile_platform,
)
from app.shared.profile_resolver import ProfileResolver
from app.shared.operational_error import OperationalError
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


OPERATIONAL_PROFILE_IDS = {
    (ProfileComponent.GUION, "instagram"): "guion_instagram",
    (ProfileComponent.GUION, "youtube"): "guion_youtube",
    (ProfileComponent.IMAGEN, "instagram"): "imagen_instagram",
    (ProfileComponent.IMAGEN, "youtube"): "imagen_youtube",
    (ProfileComponent.VIDEO, "instagram"): "video_instagram",
    (ProfileComponent.VIDEO, "youtube"): "video_youtube",
    (ProfileComponent.STUDIO, "instagram"): "studio_instagram",
    (ProfileComponent.STUDIO, "youtube"): "studio_youtube",
}


class ProfileIdentityResolverTest(unittest.TestCase):

    EXPECTED_PATHS = {
        "guion_instagram": Path(
            "config/profiles/guion/instagram/perfil_guion_instagram.json"
        ),
        "guion_youtube": Path(
            "config/profiles/guion/youtube/perfil_guion_youtube.json"
        ),
        "imagen_instagram": Path(
            "config/profiles/imagen/instagram/perfil_imagen_instagram.json"
        ),
        "imagen_youtube": Path(
            "config/profiles/imagen/youtube/perfil_imagen_youtube.json"
        ),
        "video_instagram": Path(
            "config/profiles/video/instagram/perfil_video_instagram.json"
        ),
        "video_youtube": Path(
            "config/profiles/video/youtube/perfil_video_youtube.json"
        ),
        "studio_instagram": Path(
            "config/profiles/studio/instagram/perfil_studio_instagram.json"
        ),
        "studio_youtube": Path(
            "config/profiles/studio/youtube/perfil_studio_youtube.json"
        ),
    }

    def setUp(self):
        self.resolver = ProfileResolver()

    def test_resolves_complete_valid_matrix_exactly(self):
        for component in ProfileComponent:
            for platform in ("instagram", "youtube"):
                profile_key = OperationalProfileKey(
                    component,
                    platform,
                    OPERATIONAL_PROFILE_IDS[(component, platform)],
                )
                with self.subTest(profile_id=profile_key.profile_id):
                    self.assertEqual(
                        self.EXPECTED_PATHS[
                            profile_key.profile_id
                        ],
                        self.resolver.resolve_operational(
                            profile_key
                        )
                    )

    def test_accepts_opaque_profile_ids_across_contexts(self):
        opaque_cases = (
            ("video", "instagram", "video_youtube"),
            ("imagen", "instagram", "video_instagram"),
            ("guion", "youtube", "guion_instagram"),
            ("video", "youtube", "unknown_profile"),
        )

        for component, platform, profile_id in opaque_cases:
            with self.subTest(
                component=component,
                platform=platform,
                profile_id=profile_id
            ):
                key = OperationalProfileKey(component, platform, profile_id)
                self.assertEqual(profile_id, key.profile_id)

    def test_rejects_unknown_component_and_invalid_platform(self):
        with self.assertRaisesRegex(
            ValueError,
            "Componente de perfil no soportado"
        ):
            OperationalProfileKey(
                "design",
                "instagram",
                "design_instagram",
            )

        with self.assertRaisesRegex(
            ValueError,
            "Plataforma de perfil no soportado"
        ):
            OperationalProfileKey(
                "video",
                "Instagram Reels",
                "video_instagram",
            )

    def test_platform_is_a_normalized_technical_id(self):
        self.assertEqual("instagram", coerce_profile_platform(" Instagram "))
        self.assertEqual("youtube", coerce_profile_platform("youtube"))
        self.assertEqual("test_platform", coerce_profile_platform("test_platform"))
        with self.assertRaises(ValueError):
            coerce_profile_platform(None)
        with self.assertRaises(ValueError):
            coerce_profile_platform("youtube!")

        key = OperationalProfileKey("guion", " Test_Platform ", "test_profile")
        self.assertEqual("test_platform", key.platform)
        self.assertFalse(hasattr(profile_identity, "ProfilePlatform"))

    def test_discover_platforms_uses_direct_structure_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            component_root = root / "guion"
            for name in ("youtube", "instagram", "test_platform", "invalid platform"):
                (component_root / name).mkdir(parents=True)
            (component_root / "ignored.json").write_text("{}", encoding="utf-8")
            resolver = ProfileResolver(root)

            self.assertEqual(
                ("instagram", "test_platform", "youtube"),
                resolver.discover_platforms("guion"),
            )
            (component_root / "test_platform").rmdir()
            self.assertEqual(
                ("instagram", "youtube"),
                resolver.discover_platforms("guion"),
            )

    def test_run_controller_offers_discovered_platform_without_enum(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "guion/test_platform/estandar/subtitulos/arbitrary_name.json"
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    {
                        "component": "guion",
                        "platform": "test_platform",
                        "family": "estandar",
                    "profile_id": "test_profile",
                    "display_name": "Perfil de prueba",
                    "cue_policy": {"mode": "single_line"},
                    "render_style": {"font": "unisans", "font_size": 14, "bold": False, "primary_colour": "&H00FFFFFF", "outline_colour": "&H80000000", "back_colour": "&H00000000", "border_style": 1, "outline": 0, "shadow": 1, "alignment": 2, "margin_v": 55, "offset": 0.0},
                    }
                ),
                encoding="utf-8",
            )
            (root / "guion/test_platform/perfil_guion_test_platform.json").write_text(
                json.dumps(
                    {
                        "component": "guion",
                        "platform": "test_platform",
                        "profile_id": "guion_test_platform",
                        "display_name": "Perfil técnico",
                    }
                ),
                encoding="utf-8",
            )
            controller = RunController(
                profile_resolver=ProfileResolver(root),
                subtitle_profile_resolver=SubtitleProfileResolver(root),
            )
            with patch("builtins.input", side_effect=("1", "1", "1")), patch(
                "builtins.print"
            ) as print_mock:
                selected = controller.select_profile("script")

        printed = "\n".join(
            str(call.args[0]) for call in print_mock.call_args_list if call.args
        )
        self.assertEqual("test_platform", selected["profile_key"].platform)
        self.assertIn("Test Platform", printed)

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
            profile_key = OperationalProfileKey(
                ProfileComponent.VIDEO,
                "instagram",
                "video_instagram",
            )

            with self.assertRaises(OperationalError) as caught:
                resolver.resolve_operational(profile_key)

        self.assertEqual("PROFILE", caught.exception.context.family)
        self.assertIsInstance(caught.exception.__cause__, FileNotFoundError)

    def test_base_resolution_uses_declared_identity_not_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "guion/instagram/random_test_file.json"
            target.parent.mkdir(parents=True)
            target.write_text(
                json.dumps(
                    {
                        "component": "guion",
                        "platform": "instagram",
                        "profile_id": "test_profile",
                    }
                ),
                encoding="utf-8",
            )

            resolved = ProfileResolver(root).resolve_operational(
                OperationalProfileKey("guion", "instagram", "test_profile")
            )

        self.assertEqual(target, resolved)

    def test_base_resolution_requires_one_direct_identity_match(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            direct = root / "guion/instagram"
            nested = direct / "subtitulos"
            direct.mkdir(parents=True)
            nested.mkdir()
            key = OperationalProfileKey("guion", "instagram", "test_profile")

            (direct / "without_id.json").write_text("{}", encoding="utf-8")
            (direct / "other.json").write_text(
                json.dumps(
                    {
                        "component": "guion",
                        "platform": "instagram",
                        "profile_id": "other_profile",
                    }
                ),
                encoding="utf-8",
            )
            (nested / "nested_match.json").write_text(
                json.dumps(
                    {
                        "component": "guion",
                        "platform": "instagram",
                        "profile_id": "test_profile",
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(OperationalError) as caught:
                ProfileResolver(root).resolve_operational(key)

            self.assertEqual("PROFILE", caught.exception.context.family)
            self.assertIsInstance(caught.exception.__cause__, FileNotFoundError)

            for name in ("first.json", "second.json"):
                (direct / name).write_text(
                    json.dumps(
                        {
                            "component": "guion",
                            "platform": "instagram",
                            "profile_id": "test_profile",
                        }
                    ),
                    encoding="utf-8",
                )

            with self.assertRaises(OperationalError) as caught:
                ProfileResolver(root).resolve_operational(key)

            self.assertEqual("AMBIGUITY", caught.exception.context.family)
            self.assertIsInstance(caught.exception.__cause__, ValueError)

    def test_base_resolution_rejects_matching_id_with_wrong_context(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "guion/instagram/wrong_context.json"
            target.parent.mkdir(parents=True)
            target.write_text(
                json.dumps(
                    {
                        "component": "video",
                        "platform": "instagram",
                        "profile_id": "test_profile",
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(OperationalError) as caught:
                ProfileResolver(root).resolve_operational(
                    OperationalProfileKey("guion", "instagram", "test_profile")
                )

        self.assertEqual("PROFILE", caught.exception.context.family)
        self.assertIsInstance(caught.exception.__cause__, ValueError)

    def test_profile_paths_catalog_no_longer_exists(self):
        self.assertFalse(hasattr(ProfileResolver, "_PROFILE_PATHS"))

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
            profile_key = OperationalProfileKey(
                ProfileComponent.VIDEO,
                "instagram",
                "video_instagram",
            )

            with self.assertRaises(OperationalError) as caught:
                resolver.resolve_video_component(profile_key)

        self.assertEqual("CONFIG", caught.exception.context.family)
        self.assertEqual(
            str(Path(directory) / "video" / "instagram"),
            caught.exception.context.resource,
        )

    def test_platform_resolution_never_crosses_platforms(self):
        for component in ProfileComponent:
            instagram_key = OperationalProfileKey(
                component, "instagram", f"{component.value}_instagram"
            )
            youtube_key = OperationalProfileKey(
                component, "youtube", f"{component.value}_youtube"
            )

            instagram_path = self.resolver.resolve_operational(
                instagram_key
            )
            youtube_path = self.resolver.resolve_operational(
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

    def test_design_subtitle_discovery_is_component_scoped_for_both_platforms(self):
        for component in ProfileComponent:
            with self.subTest(component=component.value):
                designs = SubtitleProfileResolver().discover_profiles_for_family(
                    component,
                    "instagram",
                    "design",
                )
                self.assertTrue(designs)
                canonical = next(
                    descriptor
                    for descriptor in designs
                    if descriptor.profile_id == "modo_conciencia_reels"
                )
                key = canonical.key
                display_name = canonical.display_name
                self.assertEqual(component, key.component)
                self.assertEqual("design", key.family)
                self.assertEqual(
                    "modo_conciencia_reels",
                    key.profile_id,
                )
                self.assertEqual("Modo Conciencia | Reels", display_name)
                self.assertEqual(
                    Path("config/profiles") / component.value / "instagram"
                    / "design" / "subtitulos" / "modo_conciencia_reels.json",
                    SubtitleProfileResolver().resolve(key),
                )
                youtube_designs = (
                    SubtitleProfileResolver().discover_profiles_for_family(
                        component,
                        "youtube",
                        "design",
                    )
                )
                self.assertEqual(1, len(youtube_designs))
                youtube_key = youtube_designs[0].key
                self.assertEqual(component, youtube_key.component)
                self.assertEqual("youtube", youtube_key.platform)
                self.assertEqual("design", youtube_key.family)
                self.assertEqual(
                    "modo_conciencia_youtube",
                    youtube_key.profile_id,
                )
                self.assertEqual(
                    "Modo Conciencia | YouTube",
                    youtube_designs[0].display_name,
                )

    def test_design_subtitle_family_needs_no_operational_profile(self):
        root = Path("config/profiles/video/instagram/design")
        self.assertFalse(any(root.glob("*.json")))
        descriptor = SubtitleProfileResolver().discover_profiles_for_family(
            "video", "instagram", "design",
        )[0]
        self.assertEqual("modo_conciencia_reels", descriptor.profile_id)

    def test_design_selector_uses_visible_labels_for_all_instagram_components(self):
        cases = {
            "script": ProfileComponent.GUION,
            "image": ProfileComponent.IMAGEN,
            "video": ProfileComponent.VIDEO,
            "studio": ProfileComponent.STUDIO,
        }
        for scope, component in cases.items():
            with self.subTest(scope=scope), patch(
                "builtins.input", side_effect=("1", "1", "1")
            ), patch("builtins.print") as print_mock:
                selected = RunController().select_profile(scope)

            printed = "\n".join(
                str(call.args[0])
                for call in print_mock.call_args_list
                if call.args
            )
            self.assertIsInstance(selected["profile_key"], OperationalProfileKey)
            self.assertEqual(component, selected["profile_key"].component)
            self.assertEqual("design", selected["subtitle_profile_key"].family)
            self.assertIn("SUBTÍTULOS", printed)
            self.assertIn("FAMILIA", printed)
            self.assertIn("1. MODO CONCIENCIA", printed)
            self.assertIn("2. FORMATO ESTÁNDAR", printed)
            self.assertNotIn("SYSTEM", printed)

    def test_youtube_shows_the_discovered_design_and_standard_families(self):
        for scope in ("script", "image", "video", "studio"):
            with self.subTest(scope=scope), patch(
                "builtins.input", side_effect=("2", "1", "1")
            ), patch("builtins.print") as print_mock:
                selected = RunController().select_profile(scope)

            printed = "\n".join(
                str(call.args[0])
                for call in print_mock.call_args_list
                if call.args
            )
            self.assertIsInstance(selected["profile_key"], OperationalProfileKey)
            self.assertEqual("design", selected["subtitle_profile_key"].family)
            self.assertIn("SUBTÍTULOS", printed)
            self.assertIn("1. MODO CONCIENCIA", printed)
            self.assertIn("2. FORMATO ESTÁNDAR", printed)

    def test_image_and_video_keep_distinct_identity_and_physical_files(self):
        image_key = OperationalProfileKey(
            ProfileComponent.IMAGEN,
            "instagram",
            "imagen_instagram",
        )
        video_key = OperationalProfileKey(
            ProfileComponent.VIDEO,
            "instagram",
            "video_instagram",
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
            self.resolver.resolve_operational(image_key),
            self.resolver.resolve_operational(video_key)
        )

    def test_wan_resolution_requires_video_identity(self):
        image_key = OperationalProfileKey(
            ProfileComponent.IMAGEN,
            "instagram",
            "imagen_instagram",
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
                "instagram",
                "imagen_instagram",
            ),
            (
                ProfileComponent.IMAGEN,
                "youtube",
                "imagen_youtube",
            ),
            (
                ProfileComponent.VIDEO,
                "instagram",
                "video_instagram",
            ),
            (
                ProfileComponent.VIDEO,
                "youtube",
                "video_youtube",
            ),
        )
        for component, platform, profile_id in cases:
            with self.subTest(profile_id=profile_id):
                profile_key = OperationalProfileKey(
                    component, platform, profile_id,
                )
                self.assertEqual(
                    profile_id,
                    profile_key.profile_id
                )
                self.assertNotIn(
                    "diseno",
                    self.resolver.resolve_operational(
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
            for platform in ("instagram", "youtube"):
                with self.subTest(
                    component=component.value,
                    platform=platform
                ):
                    profile_key = OperationalProfileKey(
                        component,
                        platform,
                        OPERATIONAL_PROFILE_IDS[(component, platform)],
                    )
                    expected_profile = self.resolver.load_operational(
                        profile_key
                    )

                    with patch.dict(
                        os.environ,
                        {
                            "MC_PROFILE_COMPONENT": component.value,
                            "MC_PROFILE_PLATFORM": platform,
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

    def test_config_manager_loads_design_key_regardless_of_family_environment(self):
        design_key = SubtitleProfileResolver().discover_profiles_for_family(
            "video", "instagram", "design",
        )[0].key
        with patch.dict(
            os.environ,
            {
                "MC_PROFILE_COMPONENT": "video",
                "MC_PROFILE_PLATFORM": "instagram",
                "MC_PROFILE_ID": "video_instagram",
                "MC_PROFILE_FAMILY": "estandar",
            },
            clear=True,
        ):
            self.assertEqual(
                SubtitleProfileResolver().load(design_key),
                ConfigManager().get_subtitle_profile_by_key(design_key),
            )

    def test_official_identity_does_not_require_profile_path_adapter(self):
        for component in ProfileComponent:
            for platform in ("instagram", "youtube"):
                with self.subTest(
                    component=component.value,
                    platform=platform
                ):
                    profile_key = OperationalProfileKey(
                        component,
                        platform,
                        OPERATIONAL_PROFILE_IDS[(component, platform)],
                    )
                    with patch.dict(
                        os.environ,
                        {
                            "MC_PROFILE_COMPONENT": component.value,
                            "MC_PROFILE_PLATFORM": platform,
                            "MC_PROFILE_ID": profile_key.profile_id,
                        },
                        clear=True
                    ):
                        profile = ConfigManager().get_profile_config()

                    self.assertEqual(
                        self.resolver.load_operational(
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
            with self.assertRaises(OperationalError) as caught:
                ConfigManager().get_profile_config()

        self.assertEqual("CONFIG", caught.exception.context.family)

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

        expected = self.resolver.load_operational(
            OperationalProfileKey(
                ProfileComponent.VIDEO,
                "instagram",
                "video_instagram",
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
                "load_json",
                side_effect=AssertionError(
                    "application config must not resolve profiles"
                )
            ), patch.object(
                manager.profile_resolver,
                "load_operational",
                side_effect=AssertionError(
                    "missing identity must not resolve a profile"
                )
            ), self.assertRaises(OperationalError) as caught:
                manager.get_profile_config()

        self.assertEqual("CONFIG", caught.exception.context.family)

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
            with self.assertRaises(OperationalError) as caught:
                ConfigManager().get_profile_config()

        self.assertEqual("CONFIG", caught.exception.context.family)

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
                "instagram",
                selected["profile_key"].platform
            )

    def test_run_controller_selects_design_only_after_family_and_design_choice(self):
        controller = RunController()
        with patch("builtins.input", side_effect=("1", "1", "1")), patch(
            "builtins.print"
        ) as print_mock:
            selected = controller.select_profile("video")

        self.assertIsInstance(selected["profile_key"], OperationalProfileKey)
        self.assertEqual(
            "video_instagram",
            selected["profile_key"].profile_id,
        )
        self.assertEqual(
            "modo_conciencia_reels",
            selected["subtitle_profile_key"].profile_id,
        )
        printed = "\n".join(
            str(call.args[0])
            for call in print_mock.call_args_list
            if call.args
        )
        self.assertIn("SUBTÍTULOS", printed)
        self.assertIn("1. MODO CONCIENCIA", printed)
        self.assertIn("2. FORMATO ESTÁNDAR", printed)

    def test_run_controller_selects_youtube_design_when_discovered(self):
        controller = RunController()
        with patch("builtins.input", side_effect=("2", "1", "1")), patch(
            "builtins.print"
        ) as print_mock:
            selected = controller.select_profile("studio")

        self.assertIsInstance(selected["profile_key"], OperationalProfileKey)
        printed = "\n".join(
            str(call.args[0])
            for call in print_mock.call_args_list
            if call.args
        )
        self.assertIn("SUBTÍTULOS", printed)
        self.assertEqual("design", selected["subtitle_profile_key"].family)
        self.assertIn("1. MODO CONCIENCIA", printed)
        self.assertIn("2. FORMATO ESTÁNDAR", printed)

    def test_run_controller_transports_selected_profile_key(self):
        controller = RunController()
        profile_key = OperationalProfileKey(
            ProfileComponent.VIDEO,
            "instagram",
            "video_instagram",
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
                "path": self.resolver.resolve_operational(profile_key),
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
            self.assertNotIn("MC_PROFILE_COMPONENT", os.environ)
            self.assertNotIn("MC_PROFILE_PLATFORM", os.environ)
            self.assertNotIn("MC_PROFILE_ID", os.environ)
            self.assertNotIn("MC_PROFILE_FAMILY", os.environ)
            profile_key = OperationalProfileKey(
                ProfileComponent.VIDEO,
                "instagram",
                "video_instagram",
            )
            self.assertEqual(
                self.resolver.load_operational(profile_key),
                ConfigManager(
                    operational_profile_key=profile_key,
                ).get_profile_config()
            )
            self.assertNotIn(
                "MC_SUBTITLE_CONFIG",
                os.environ
            )
            iniciar_mock.assert_called_once()
            request = iniciar_mock.call_args.kwargs["request"]
            self.assertEqual(profile_key, request.operational_profile_key)
            self.assertEqual({"request"}, set(iniciar_mock.call_args.kwargs))

    def test_main_transports_design_subtitle_identity_without_a_profile_path(self):
        subtitle_profile_key = SubtitleProfileKey("imagen", "instagram", "modo_conciencia_reels", "design",
        )
        options = {
            "profile_component": "imagen",
            "profile_platform": "instagram",
            "profile_id": "imagen_instagram",
            "profile_family": "system",
            "subtitle_profile_key": subtitle_profile_key,
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
            self.assertNotIn("MC_PROFILE_FAMILY", os.environ)
            self.assertNotIn("MC_PROFILE_COMPONENT", os.environ)
            self.assertNotIn("MC_PROFILE_PLATFORM", os.environ)
            self.assertNotIn("MC_PROFILE_ID", os.environ)
            self.assertNotIn("MC_PROFILE_PATH", os.environ)
        iniciar_mock.assert_called_once()
        request = iniciar_mock.call_args.kwargs["request"]
        self.assertIs(subtitle_profile_key, request.subtitle_profile_key)

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
