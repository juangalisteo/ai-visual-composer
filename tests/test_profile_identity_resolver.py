import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main
import app.shared.profile_identity as profile_identity
from app.controllers.run_controller import RunController
from app.core.execution_request import (
    ApplicationExecutionRequest,
    StandardExecutionRequest,
)
from app.shared.config_manager import ConfigManager
from app.shared.profile_identity import (
    OperationalProfileKey,
    ProfileComponent,
    coerce_profile_format,
)
from app.shared.profile_resolver import ProfileResolver
from app.shared.operational_error import OperationalError
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver
from tests.test_menu_helpers import MenuAnswers


OPERATIONAL_PROFILE_IDS = {
    (ProfileComponent.GUION, "vertical"): "guion_vertical",
    (ProfileComponent.GUION, "horizontal"): "guion_horizontal",
    (ProfileComponent.IMAGEN, "vertical"): "imagen_vertical",
    (ProfileComponent.IMAGEN, "horizontal"): "imagen_horizontal",
    (ProfileComponent.VIDEO, "vertical"): "video_vertical",
    (ProfileComponent.VIDEO, "horizontal"): "video_horizontal",
    (ProfileComponent.STUDIO, "vertical"): "studio_vertical",
    (ProfileComponent.STUDIO, "horizontal"): "studio_horizontal",
}


class ProfileIdentityResolverTest(unittest.TestCase):

    EXPECTED_PATHS = {
        "guion_vertical": Path(
            "config/profiles/guion/vertical/perfil_guion_vertical.json"
        ),
        "guion_horizontal": Path(
            "config/profiles/guion/horizontal/perfil_guion_horizontal.json"
        ),
        "imagen_vertical": Path(
            "config/profiles/imagen/vertical/perfil_imagen_vertical.json"
        ),
        "imagen_horizontal": Path(
            "config/profiles/imagen/horizontal/perfil_imagen_horizontal.json"
        ),
        "video_vertical": Path(
            "config/profiles/video/vertical/perfil_video_vertical.json"
        ),
        "video_horizontal": Path(
            "config/profiles/video/horizontal/perfil_video_horizontal.json"
        ),
        "studio_vertical": Path(
            "config/profiles/studio/vertical/perfil_studio_vertical.json"
        ),
        "studio_horizontal": Path(
            "config/profiles/studio/horizontal/perfil_studio_horizontal.json"
        ),
    }

    def setUp(self):
        self.resolver = ProfileResolver()

    def test_resolves_complete_valid_matrix_exactly(self):
        for component in ProfileComponent:
            for profile_format in ("horizontal", "vertical"):
                profile_key = OperationalProfileKey(
                    component,
                    profile_format,
                    OPERATIONAL_PROFILE_IDS[(component, profile_format)],
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
            ("video", "vertical", "video_horizontal"),
            ("imagen", "vertical", "video_vertical"),
            ("guion", "horizontal", "guion_vertical"),
            ("video", "horizontal", "unknown_profile"),
        )

        for component, profile_format, profile_id in opaque_cases:
            with self.subTest(
                component=component,
                profile_format=profile_format,
                profile_id=profile_id
            ):
                key = OperationalProfileKey(component, profile_format, profile_id)
                self.assertEqual(profile_id, key.profile_id)

    def test_rejects_unknown_component_and_invalid_format(self):
        with self.assertRaisesRegex(
            ValueError,
            "Componente de perfil no soportado"
        ):
            OperationalProfileKey(
                "design",
                "vertical",
                "design_vertical",
            )

        with self.assertRaisesRegex(
            ValueError,
            "Formato de perfil no soportado"
        ):
            OperationalProfileKey(
                "video",
                "formato invalido",
                "video_vertical",
            )

    def test_format_is_a_normalized_technical_id(self):
        self.assertEqual("vertical", coerce_profile_format(" Vertical "))
        self.assertEqual("horizontal", coerce_profile_format("horizontal"))
        self.assertEqual("test_format", coerce_profile_format("test_format"))
        with self.assertRaises(ValueError):
            coerce_profile_format(None)
        with self.assertRaises(ValueError):
            coerce_profile_format("horizontal!")

        key = OperationalProfileKey("guion", " Test_Format ", "test_profile")
        self.assertEqual("test_format", key.format)
        self.assertFalse(hasattr(profile_identity, "ProfileFormat"))

    def test_discover_formats_uses_direct_structure_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            component_root = root / "guion"
            for name in ("horizontal", "vertical", "test_format", "invalid format"):
                (component_root / name).mkdir(parents=True)
            (component_root / "ignored.json").write_text("{}", encoding="utf-8")
            resolver = ProfileResolver(root)

            self.assertEqual(
                ("horizontal", "test_format", "vertical"),
                resolver.discover_formats("guion"),
            )
            (component_root / "test_format").rmdir()
            self.assertEqual(
                ("horizontal", "vertical"),
                resolver.discover_formats("guion"),
            )

    def test_run_controller_offers_discovered_format_without_enum(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "guion/test_format/estandar/subtitulos/arbitrary_name.json"
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    {
                        "component": "guion",
                        "format": "test_format",
                        "family": "estandar",
                    "profile_id": "test_profile",
                    "display_name": "Perfil de prueba",
                    "cue_policy": {"mode": "single_line"},
                    "render_style": {"font": "unisans", "font_size": 14, "bold": False, "primary_colour": "&H00FFFFFF", "outline_colour": "&H80000000", "back_colour": "&H00000000", "border_style": 1, "outline": 0, "shadow": 1, "alignment": 2, "margin_v": 55, "offset": 0.0},
                    }
                ),
                encoding="utf-8",
            )
            (root / "guion/test_format/perfil_guion_test_format.json").write_text(
                json.dumps(
                    {
                        "component": "guion",
                        "format": "test_format",
                        "profile_id": "guion_test_format",
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
        self.assertEqual("test_format", selected["profile_key"].format)
        self.assertIn("Test Format", printed)

    def test_missing_official_file_fails_without_legacy_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            legacy_path = (
                Path(directory)
                / "vertical"
                / "modo_conciencia.json"
            )
            legacy_path.parent.mkdir(parents=True)
            legacy_path.write_text("{}", encoding="utf-8")
            resolver = ProfileResolver(directory)
            profile_key = OperationalProfileKey(
                ProfileComponent.VIDEO,
                "vertical",
                "video_vertical",
            )

            with self.assertRaises(OperationalError) as caught:
                resolver.resolve_operational(profile_key)

        self.assertEqual("PROFILE", caught.exception.context.family)
        self.assertIsInstance(caught.exception.__cause__, FileNotFoundError)

    def test_base_resolution_uses_declared_identity_not_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "guion/vertical/random_test_file.json"
            target.parent.mkdir(parents=True)
            target.write_text(
                json.dumps(
                    {
                        "component": "guion",
                        "format": "vertical",
                        "profile_id": "test_profile",
                    }
                ),
                encoding="utf-8",
            )

            resolved = ProfileResolver(root).resolve_operational(
                OperationalProfileKey("guion", "vertical", "test_profile")
            )

        self.assertEqual(target, resolved)

    def test_base_resolution_requires_one_direct_identity_match(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            direct = root / "guion/vertical"
            nested = direct / "subtitulos"
            direct.mkdir(parents=True)
            nested.mkdir()
            key = OperationalProfileKey("guion", "vertical", "test_profile")

            (direct / "without_id.json").write_text("{}", encoding="utf-8")
            (direct / "other.json").write_text(
                json.dumps(
                    {
                        "component": "guion",
                        "format": "vertical",
                        "profile_id": "other_profile",
                    }
                ),
                encoding="utf-8",
            )
            (nested / "nested_match.json").write_text(
                json.dumps(
                    {
                        "component": "guion",
                        "format": "vertical",
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
                            "format": "vertical",
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
            target = root / "guion/vertical/wrong_context.json"
            target.parent.mkdir(parents=True)
            target.write_text(
                json.dumps(
                    {
                        "component": "video",
                        "format": "vertical",
                        "profile_id": "test_profile",
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(OperationalError) as caught:
                ProfileResolver(root).resolve_operational(
                    OperationalProfileKey("guion", "vertical", "test_profile")
                )

        self.assertEqual("PROFILE", caught.exception.context.family)
        self.assertIsInstance(caught.exception.__cause__, ValueError)

    def _write_format_catalog(self, directory):
        """Technical formats with an orientation, next to the profiles root."""
        catalog = {
            "formats": {
                "test_portrait_format": {
                    "display_name": "Formato técnico alto",
                    "order": 1,
                    "orientation": "portrait",
                },
                "test_landscape_format": {
                    "display_name": "Formato técnico ancho",
                    "order": 2,
                    "orientation": "landscape",
                },
            },
        }
        (directory / "formats.json").write_text(
            json.dumps(catalog),
            encoding="utf-8",
        )
        return directory / "profiles"

    def _write_format_profile(self, root, profile_format, width, height):
        target = root / "guion" / profile_format / "test_profile.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(
                {
                    "component": "guion",
                    "format": profile_format,
                    "profile_id": "test_profile",
                    "video_style": {"width": width, "height": height},
                }
            ),
            encoding="utf-8",
        )
        return OperationalProfileKey("guion", profile_format, "test_profile")

    def test_load_operational_accepts_format_matching_video_style(self):
        for (component, profile_format), profile_id in OPERATIONAL_PROFILE_IDS.items():
            with self.subTest(profile_id=profile_id):
                self.resolver.load_operational(
                    OperationalProfileKey(component, profile_format, profile_id)
                )

        cases = (
            ("test_portrait_format", 1080, 1920),
            ("test_landscape_format", 1920, 1080),
            ("test_portrait_format", 1080, 1080),
            ("test_undeclared_format", 1920, 1080),
            ("test_undeclared_format", 1080, 1920),
        )
        for profile_format, width, height in cases:
            with self.subTest(format=profile_format, size=(width, height)):
                with tempfile.TemporaryDirectory() as directory:
                    root = self._write_format_catalog(Path(directory))
                    key = self._write_format_profile(
                        root, profile_format, width, height
                    )

                    profile = ProfileResolver(root).load_operational(key)

                self.assertEqual(profile_format, profile["format"])

    def test_load_operational_rejects_format_contradicting_video_style(self):
        cases = (
            ("test_portrait_format", 1920, 1080, "más ancho que alto"),
            ("test_landscape_format", 1080, 1920, "más alto que ancho"),
        )
        for profile_format, width, height, orientation in cases:
            with self.subTest(format=profile_format):
                with tempfile.TemporaryDirectory() as directory:
                    root = self._write_format_catalog(Path(directory))
                    key = self._write_format_profile(
                        root, profile_format, width, height
                    )

                    with self.assertRaises(OperationalError) as caught:
                        ProfileResolver(root).load_operational(key)

                context = caught.exception.context
                self.assertEqual("CONFIG", context.family)
                self.assertIn(f"format «{profile_format}»", context.user_message)
                self.assertIn(f"{width}x{height}", context.user_message)
                self.assertIn(orientation, context.user_message)
                self.assertIsInstance(caught.exception.__cause__, ValueError)

    def test_profile_paths_catalog_no_longer_exists(self):
        self.assertFalse(hasattr(ProfileResolver, "_PROFILE_PATHS"))

    def test_missing_official_wan_file_fails_without_legacy_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            legacy_path = (
                Path(directory)
                / "video"
                / "vertical.json"
            )
            legacy_path.parent.mkdir(parents=True)
            legacy_path.write_text("{}", encoding="utf-8")
            resolver = ProfileResolver(directory)
            profile_key = OperationalProfileKey(
                ProfileComponent.VIDEO,
                "vertical",
                "video_vertical",
            )

            with self.assertRaises(OperationalError) as caught:
                resolver.resolve_video_component(profile_key)

        self.assertEqual("CONFIG", caught.exception.context.family)
        self.assertEqual(
            str(Path(directory) / "video" / "vertical"),
            caught.exception.context.resource,
        )

    def test_format_resolution_never_crosses_formats(self):
        for component in ProfileComponent:
            vertical_key = OperationalProfileKey(
                component, "vertical", f"{component.value}_vertical"
            )
            horizontal_key = OperationalProfileKey(
                component, "horizontal", f"{component.value}_horizontal"
            )

            vertical_path = self.resolver.resolve_operational(
                vertical_key
            )
            horizontal_path = self.resolver.resolve_operational(
                horizontal_key
            )

            self.assertNotIn(
                "horizontal",
                vertical_path.parts
            )
            self.assertNotIn(
                "vertical",
                horizontal_path.parts
            )

    def test_design_subtitle_discovery_is_component_scoped_for_both_formats(self):
        for component in ProfileComponent:
            with self.subTest(component=component.value):
                designs = SubtitleProfileResolver().discover_profiles_for_family(
                    component,
                    "vertical",
                    "design",
                )
                self.assertTrue(designs)
                canonical = next(
                    descriptor
                    for descriptor in designs
                    if descriptor.profile_id == "modo_conciencia_palabra_unica"
                )
                key = canonical.key
                display_name = canonical.display_name
                self.assertEqual(component, key.component)
                self.assertEqual("design", key.family)
                self.assertEqual(
                    "modo_conciencia_palabra_unica",
                    key.profile_id,
                )
                self.assertEqual("Modo Conciencia | Palabra única", display_name)
                self.assertEqual(
                    Path("config/profiles") / component.value / "vertical"
                    / "design" / "subtitulos" / "modo_conciencia_palabra_unica.json",
                    SubtitleProfileResolver().resolve(key),
                )
                horizontal_designs = (
                    SubtitleProfileResolver().discover_profiles_for_family(
                        component,
                        "horizontal",
                        "design",
                    )
                )
                self.assertEqual(1, len(horizontal_designs))
                horizontal_key = horizontal_designs[0].key
                self.assertEqual(component, horizontal_key.component)
                self.assertEqual("horizontal", horizontal_key.format)
                self.assertEqual("design", horizontal_key.family)
                self.assertEqual(
                    "modo_conciencia_linea_unica",
                    horizontal_key.profile_id,
                )
                self.assertEqual(
                    "Modo Conciencia | Línea única",
                    horizontal_designs[0].display_name,
                )

    def test_design_subtitle_family_needs_no_operational_profile(self):
        root = Path("config/profiles/video/vertical/design")
        self.assertFalse(any(root.glob("*.json")))
        descriptor = SubtitleProfileResolver().discover_profiles_for_family(
            "video", "vertical", "design",
        )[0]
        self.assertEqual("modo_conciencia_palabra_unica", descriptor.profile_id)

    def test_design_selector_uses_visible_labels_for_all_vertical_components(self):
        cases = {
            "script": ProfileComponent.GUION,
            "image": ProfileComponent.IMAGEN,
            "video": ProfileComponent.VIDEO,
            "studio": ProfileComponent.STUDIO,
        }
        for scope, component in cases.items():
            design = (
                "Modo Conciencia | Podcast"
                if component is ProfileComponent.STUDIO
                else "Modo Conciencia | Palabra única"
            )
            answers = MenuAnswers("Vertical 9:16", "MODO CONCIENCIA", design)
            with self.subTest(scope=scope), patch(
                "builtins.input", side_effect=answers.input
            ), patch(
                "builtins.print", side_effect=answers.print
            ) as print_mock:
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
            self.assertIn("2. ESTILO ESTÁNDAR", printed)
            self.assertNotIn("SYSTEM", printed)

    def test_horizontal_shows_the_discovered_design_and_standard_families(self):
        for scope in ("script", "image", "video", "studio"):
            answers = MenuAnswers(
                "Horizontal 16:9",
                "MODO CONCIENCIA",
                "Modo Conciencia | Línea única",
            )
            with self.subTest(scope=scope), patch(
                "builtins.input", side_effect=answers.input
            ), patch(
                "builtins.print", side_effect=answers.print
            ) as print_mock:
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
            self.assertIn("2. ESTILO ESTÁNDAR", printed)

    def test_image_and_video_keep_distinct_identity_and_physical_files(self):
        image_key = OperationalProfileKey(
            ProfileComponent.IMAGEN,
            "vertical",
            "imagen_vertical",
        )
        video_key = OperationalProfileKey(
            ProfileComponent.VIDEO,
            "vertical",
            "video_vertical",
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
            "vertical",
            "imagen_vertical",
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
                "vertical",
                "imagen_vertical",
            ),
            (
                ProfileComponent.IMAGEN,
                "horizontal",
                "imagen_horizontal",
            ),
            (
                ProfileComponent.VIDEO,
                "vertical",
                "video_vertical",
            ),
            (
                ProfileComponent.VIDEO,
                "horizontal",
                "video_horizontal",
            ),
        )
        for component, profile_format, profile_id in cases:
            with self.subTest(profile_id=profile_id):
                profile_key = OperationalProfileKey(
                    component, profile_format, profile_id,
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
            for profile_format in ("horizontal", "vertical"):
                with self.subTest(
                    component=component.value,
                    profile_format=profile_format
                ):
                    profile_key = OperationalProfileKey(
                        component,
                        profile_format,
                        OPERATIONAL_PROFILE_IDS[(component, profile_format)],
                    )
                    expected_profile = self.resolver.load_operational(
                        profile_key
                    )

                    identity_profile = ConfigManager(
                        operational_profile_key=profile_key
                    ).get_profile_config()

                    self.assertEqual(
                        expected_profile,
                        identity_profile
                    )

    def test_config_manager_loads_design_subtitle_key_as_given(self):
        design_key = SubtitleProfileResolver().discover_profiles_for_family(
            "video", "vertical", "design",
        )[0].key
        self.assertEqual(
            SubtitleProfileResolver().load(design_key),
            ConfigManager().get_subtitle_profile_by_key(design_key),
        )

    def test_official_identity_does_not_require_profile_path_adapter(self):
        for component in ProfileComponent:
            for profile_format in ("horizontal", "vertical"):
                with self.subTest(
                    component=component.value,
                    profile_format=profile_format
                ):
                    profile_key = OperationalProfileKey(
                        component,
                        profile_format,
                        OPERATIONAL_PROFILE_IDS[(component, profile_format)],
                    )
                    profile = ConfigManager(
                        operational_profile_key=profile_key
                    ).get_profile_config()

                    self.assertEqual(
                        self.resolver.load_operational(
                            profile_key
                        ),
                        profile
                    )

    def test_external_profile_path_cannot_override_identity(self):
        profile_key = OperationalProfileKey(
            ProfileComponent.VIDEO,
            "vertical",
            "video_vertical",
        )
        with patch.dict(
            os.environ,
            {
                "MC_PROFILE_PATH": (
                    "ignored-profile.json"
                ),
            },
            clear=True
        ):
            profile = ConfigManager(
                operational_profile_key=profile_key
            ).get_profile_config()

        expected = self.resolver.load_operational(profile_key)
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
            answers = MenuAnswers(
                "Vertical 9:16",
                "MODO CONCIENCIA",
                "Modo Conciencia | Palabra única",
            )
            with self.subTest(scope=scope), patch(
                "builtins.input",
                side_effect=answers.input
            ), patch("builtins.print", side_effect=answers.print):
                selected = RunController().select_profile(
                    scope
                )

            self.assertEqual(
                expected_component,
                selected["profile_key"].component
            )
            self.assertEqual(
                "vertical",
                selected["profile_key"].format
            )

    def test_run_controller_selects_design_only_after_family_and_design_choice(self):
        controller = RunController()
        answers = MenuAnswers(
            "Vertical 9:16",
            "MODO CONCIENCIA",
            "Modo Conciencia | Palabra única",
        )
        with patch("builtins.input", side_effect=answers.input), patch(
            "builtins.print", side_effect=answers.print
        ) as print_mock:
            selected = controller.select_profile("video")

        self.assertIsInstance(selected["profile_key"], OperationalProfileKey)
        self.assertEqual(
            "video_vertical",
            selected["profile_key"].profile_id,
        )
        self.assertEqual(
            "modo_conciencia_palabra_unica",
            selected["subtitle_profile_key"].profile_id,
        )
        printed = "\n".join(
            str(call.args[0])
            for call in print_mock.call_args_list
            if call.args
        )
        self.assertIn("SUBTÍTULOS", printed)
        self.assertIn("1. MODO CONCIENCIA", printed)
        self.assertIn("2. ESTILO ESTÁNDAR", printed)

    def test_run_controller_selects_horizontal_design_when_discovered(self):
        controller = RunController()
        answers = MenuAnswers(
            "Horizontal 16:9",
            "MODO CONCIENCIA",
            "Modo Conciencia | Línea única",
        )
        with patch("builtins.input", side_effect=answers.input), patch(
            "builtins.print", side_effect=answers.print
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
        self.assertIn("2. ESTILO ESTÁNDAR", printed)

    def test_run_controller_transports_selected_profile_key(self):
        controller = RunController()
        profile_key = OperationalProfileKey(
            ProfileComponent.VIDEO,
            "vertical",
            "video_vertical",
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
            request = controller.run()

        self.assertEqual(
            ProfileComponent.VIDEO,
            request.operational_profile_key.component
        )
        self.assertEqual(
            "vertical",
            request.operational_profile_key.format
        )
        self.assertEqual(
            "video_vertical",
            request.operational_profile_key.profile_id
        )
        self.assertNotIn("profile_path", vars(request))
        self.assertNotIn("profile_path", vars(request.route))

    def test_main_transports_only_structured_profile_identity(self):
        controller_request = ApplicationExecutionRequest(
            project_name="profile identity",
            clear_output=False,
            operational_profile_key=OperationalProfileKey(
                ProfileComponent.VIDEO,
                "vertical",
                "video_vertical",
            ),
            subtitle_profile_key=None,
            route=StandardExecutionRequest(
                pipeline_mode="audio",
                visual_pipeline="video",
                script_source="generated",
                voice_config_id="femenina",
                music_category=None,
                overlays_mode="off",
            ),
        )

        with patch.dict(
            os.environ,
            {},
            clear=True
        ), patch(
            "main.RunController"
        ) as controller_mock, patch(
            "main.run_application"
        ) as run_application_mock:
            controller_mock.return_value.run.return_value = controller_request

            self.assertEqual(0, main.main())
            self.assertNotIn("MC_PROFILE_PATH", os.environ)
            self.assertNotIn("MC_PROFILE_FAMILY", os.environ)
            profile_key = OperationalProfileKey(
                ProfileComponent.VIDEO,
                "vertical",
                "video_vertical",
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
            run_application_mock.assert_called_once()
            request = run_application_mock.call_args.kwargs["request"]
            self.assertEqual(profile_key, request.operational_profile_key)
            self.assertEqual({"request"}, set(run_application_mock.call_args.kwargs))

    def test_main_transports_design_subtitle_identity_without_a_profile_path(self):
        subtitle_profile_key = SubtitleProfileKey("imagen", "vertical", "modo_conciencia_palabra_unica", "design",
        )
        controller_request = ApplicationExecutionRequest(
            project_name="design identity",
            clear_output=False,
            operational_profile_key=OperationalProfileKey(
                ProfileComponent.IMAGEN,
                "vertical",
                "imagen_vertical",
            ),
            subtitle_profile_key=subtitle_profile_key,
            route=StandardExecutionRequest(
                pipeline_mode="audio",
                visual_pipeline="image",
                script_source="generated",
                voice_config_id=None,
                music_category=None,
                overlays_mode="off",
            ),
        )
        with patch.dict(os.environ, {}, clear=True), patch(
            "main.RunController"
        ) as controller_mock, patch("main.run_application") as run_application_mock:
            controller_mock.return_value.run.return_value = controller_request

            self.assertEqual(0, main.main())
            self.assertNotIn("MC_PROFILE_FAMILY", os.environ)
            self.assertNotIn("MC_PROFILE_PATH", os.environ)
        run_application_mock.assert_called_once()
        request = run_application_mock.call_args.kwargs["request"]
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
