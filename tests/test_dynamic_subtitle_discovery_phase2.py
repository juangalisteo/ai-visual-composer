import json
import inspect
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.controllers.run_controller import RunController
from app.shared.profile_identity import (
    ProfileComponent,
    ProfileKey,
    coerce_profile_family,
)
from app.shared.profile_resolver import ProfileResolver
from app.shared.operational_error import OperationalError
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


class DynamicSubtitleDiscoveryPhase2Test(unittest.TestCase):

    def _assert_operational_error(
        self,
        callback,
        family,
        cause_type,
    ):
        with self.assertRaises(OperationalError) as captured:
            callback()
        self.assertEqual(family, captured.exception.context.family)
        self.assertIsInstance(captured.exception.__cause__, cause_type)

    def test_profile_resolver_has_no_design_structural_branch(self):
        source = inspect.getsource(ProfileResolver)

        self.assertNotIn("ProfileFamily.DESIGN", source)
        self.assertNotIn("_design_path", source)
        self.assertNotIn("_validate_design_identity", source)
        self.assertNotIn("startswith(\"subtitulo_\")", source)

    def test_operational_profiles_do_not_embed_subtitle_contracts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self._write_profile(root)
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertNotIn("subtitle_config", data)
            self.assertNotIn("subtitle_profile", data)

    def test_dynamic_family_normalization_rejects_non_text_and_path_values(self):
        family = coerce_profile_family("  TEST_FAMILY  ")

        self.assertEqual("test_family", family)
        self.assertEqual(family, "test_family")
        self.assertEqual(hash(family), hash("test_family"))
        self.assertEqual("estandar", coerce_profile_family("estandar"))
        self.assertEqual("design", coerce_profile_family("design"))
        for invalid in (None, 1, "", "..", "test_family/otro", "test_family\\otro"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                coerce_profile_family(invalid)
        with self.assertRaises(ValueError):
            ProfileKey(
                "guion",
                "instagram",
                "perfil_../escape",
                "test_family",
            )
        with self.assertRaises(ValueError):
            ProfileKey(
                component="guion",
                platform="instagram",
                profile_id="guion_instagram_1_prueba",
                family=1,
            )

    def test_family_strings_are_normalized_and_system_is_reserved(self):
        for value in ("design", "DESIGN", " design "):
            with self.subTest(value=value):
                self.assertEqual("design", coerce_profile_family(value))

        for value in ("system", "SYSTEM", " system "):
            with self.subTest(value=value), self.assertRaises(ValueError):
                coerce_profile_family(value)
        self.assertEqual("test_family", coerce_profile_family("test_family"))
        with self.assertRaises(ValueError):
            SubtitleProfileKey(
                component="guion",
                platform="instagram",
                profile_id="subtitulo_../escape",
                family="test_family",
            )

    @staticmethod
    def _write_profile(
        root,
        component="guion",
        platform="instagram",
        family_name="test_family",
        profile_id="perfil_prueba",
    ):
        family = root / component / platform / family_name
        family.mkdir(parents=True)
        path = family / "perfil.json"
        path.write_text(
            json.dumps(
                {
                    "component": component,
                    "platform": platform,
                    "family": family_name,
                    "profile_id": profile_id,
                    "display_name": "Perfil de prueba",
                }
            ),
            encoding="utf-8",
        )
        return path

    @staticmethod
    def _write_subtitle_profile(
        root,
        component="guion",
        platform="instagram",
        profile_id="subtitulo_prueba",
        filename="subtitulo.json",
        changes=None,
    ):
        source = Path(
            "config/profiles/guion/instagram/estandar/subtitulos/"
            "subtitulo_guion_instagram_linea_unica.json"
        )
        payload = json.loads(source.read_text(encoding="utf-8"))
        payload.update(
            {
                "component": component,
                "platform": platform,
                "family": "test_family",
                "profile_id": profile_id,
            }
        )
        if changes:
            payload.update(changes)
        path = (
            root
            / component
            / platform
            / "test_family"
            / "subtitulos"
            / filename
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_subtitle_directory_accepts_an_opaque_profile_id(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self._write_subtitle_profile(
                root,
                profile_id="perfil_prueba",
                filename="archivo_opaco.json",
            )
            profile_key = ProfileKey(
                "guion", "instagram", "perfil_operacional", "test_family"
            )
            resolver = SubtitleProfileResolver(root)

            descriptors = resolver.discover_profiles(profile_key)
            resolved = resolver.load_selection(profile_key, "perfil_prueba")

        self.assertEqual(("perfil_prueba",), tuple(item.profile_id for item in descriptors))
        self.assertEqual(path, resolved.path)

    def test_subtitle_directory_rejects_invalid_json_by_contract_not_heuristic(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_subtitle_profile(
                root,
                profile_id="perfil_prueba",
                changes={"cue_policy": None},
            )
            profile_key = ProfileKey(
                "guion", "instagram", "perfil_operacional", "test_family"
            )

            self._assert_operational_error(
                lambda: SubtitleProfileResolver(root).discover_profiles(profile_key),
                "VALIDATION",
                TypeError,
            )

    def test_subtitle_directory_requires_cue_policy_and_render_style(self):
        profile_key = ProfileKey(
            "guion", "instagram", "perfil_operacional", "test_family"
        )
        for missing in ("cue_policy", "render_style"):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self._write_subtitle_profile(
                    root,
                    profile_id="perfil_prueba",
                    changes={missing: None},
                )
                self._assert_operational_error(
                    lambda: SubtitleProfileResolver(root).discover_profiles(profile_key),
                    "VALIDATION",
                    TypeError,
                )

    def test_operational_profile_with_subtitle_prefix_keeps_operational_domain(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self._write_profile(root)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["profile_id"] = "subtitulo_prueba"
            path.write_text(json.dumps(payload), encoding="utf-8")

            discovered = ProfileResolver(root).discover(
                "guion", "instagram", "test_family"
            )

        self.assertEqual("subtitulo_prueba", discovered[0][0].profile_id)

    def test_resolvers_use_structure_not_document_heuristics(self):
        subtitle_source = inspect.getsource(SubtitleProfileResolver)
        profile_source = inspect.getsource(ProfileResolver)

        self.assertNotIn("startswith(\"subtitulo_\")", subtitle_source)
        self.assertNotIn("startswith('subtitulo_')", subtitle_source)
        self.assertNotIn("document_type", subtitle_source)
        self.assertNotIn("document_type", profile_source)

    def test_new_family_is_discovered_without_python_registration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_profile(root)

            discovered = ProfileResolver(root).discover(
                "guion", "instagram", "test_family"
            )

        self.assertEqual(1, len(discovered))
        key, display_name = discovered[0]
        self.assertEqual("test_family", key.family)
        self.assertEqual("perfil_prueba", key.profile_id)
        self.assertEqual("Perfil de prueba", display_name)

    def test_display_name_does_not_change_dynamic_identity_or_resolution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self._write_profile(root)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["display_name"] = "Otro nombre visible"
            path.write_text(json.dumps(data), encoding="utf-8")
            key = ProfileKey(
                "guion", "instagram", "perfil_prueba", "test_family"
            )

            resolved = ProfileResolver(root).resolve(key)

        self.assertEqual(path, resolved)

    def test_copy_paste_platform_family_and_profile_need_no_python_registry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = Path(
                "config/profiles/guion/instagram/estandar/subtitulos/"
                "subtitulo_guion_instagram_linea_unica.json"
            )
            payload = json.loads(source.read_text(encoding="utf-8"))
            payload.update(
                {
                    "component": "guion",
                    "platform": "test_platform",
                    "family": "minimalista",
                    "profile_id": "nuevo_perfil",
                    "display_name": "Minimal Clean",
                }
            )
            profile_path = (
                root / "guion" / "test_platform" / "minimalista"
                / "subtitulos" / "archivo_copiado.json"
            )
            profile_path.parent.mkdir(parents=True)
            profile_path.write_text(json.dumps(payload), encoding="utf-8")

            resolver = SubtitleProfileResolver(root)
            self.assertEqual(("test_platform",), resolver.discover_platforms("guion"))
            self.assertEqual(
                ("minimalista",),
                resolver.discover_families("guion", "test_platform"),
            )
            descriptors = resolver.discover_profiles_for_family(
                "guion", "test_platform", "minimalista",
            )

            self.assertEqual(1, len(descriptors))
            self.assertEqual("nuevo_perfil", descriptors[0].profile_id)
            self.assertEqual("Minimal Clean", descriptors[0].display_name)
            self.assertEqual(profile_path, resolver.load(descriptors[0].key).path)

    def test_second_dynamic_family_uses_the_same_generic_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_profile(root, family_name="other_test_family")

            discovered = ProfileResolver(root).discover(
                "guion", "instagram", "other_test_family"
            )

        self.assertEqual("other_test_family", discovered[0][0].family)
        self.assertEqual("perfil_prueba", discovered[0][0].profile_id)

    def test_catalog_discovers_physical_estandar_and_design_families(self):
        families = tuple(
            family
            for family in SubtitleProfileResolver().discover_families("studio", "instagram")
        )

        self.assertIn("estandar", families)
        self.assertIn("design", families)

    def test_catalog_discovers_physical_estandar_and_dynamic_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            platform_root = root / "guion" / "instagram"
            platform_root.mkdir(parents=True)
            (platform_root / "estandar" / "perfil_guion_instagram.json").parent.mkdir()
            (platform_root / "estandar" / "perfil_guion_instagram.json").write_text(
                json.dumps(
                    {
                        "component": "guion",
                        "platform": "instagram",
                        "family": "estandar",
                        "profile_id": "guion_instagram",
                        "display_name": "Sistema oficial",
                    }
                ),
                encoding="utf-8",
            )
            self._write_profile(root)

            families = ProfileResolver(root).discover_families(
                "guion", "instagram"
            )

        self.assertEqual(
            ("estandar", "test_family"),
            tuple(family for family in families),
        )

    @staticmethod
    def _write_estandar_profile(root, payload):
        path = root / "guion" / "instagram" / "estandar" / "perfil_guion_instagram.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")
        return path

    def test_catalog_omits_an_absent_estandar_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            families = ProfileResolver(Path(directory)).discover_families(
                "guion", "instagram"
            )

        self.assertEqual((), families)

    def test_catalog_propagates_malformed_estandar_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_estandar_profile(root, "{")

            self._assert_operational_error(
                lambda: ProfileResolver(root).discover_families("guion", "instagram"),
                "CONFIG",
                json.JSONDecodeError,
            )

    def test_catalog_propagates_non_object_estandar_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_estandar_profile(root, json.dumps([]))

            self._assert_operational_error(
                lambda: ProfileResolver(root).discover_families("guion", "instagram"),
                "CONFIG",
                TypeError,
            )

    def test_catalog_includes_a_valid_estandar_profile_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_estandar_profile(
                root,
                json.dumps(
                    {
                        "component": "guion",
                        "platform": "instagram",
                        "family": "estandar",
                        "profile_id": "guion_instagram",
                        "display_name": "Sistema",
                    }
                ),
            )

            families = ProfileResolver(root).discover_families(
                "guion", "instagram"
            )

        self.assertEqual(("estandar",), families)

    @staticmethod
    def _write_design_profile(root, payload=None):
        payload = payload or {
            "component": "guion",
            "platform": "instagram",
            "family": "design",
            "profile_id": "guion_instagram_design_valido",
            "display_name": "Diseño válido",
            "subtitle_config": "single_line",
            "subtitle_profile": {"style": "single_line"},
        }
        path = root / "guion" / "instagram" / "design" / "valido.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_valid_design_profile_is_discovered(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_design_profile(root)

            discovered = ProfileResolver(root).discover(
                "guion", "instagram", "design"
            )

        self.assertEqual(1, len(discovered))
        self.assertEqual("guion_instagram_design_valido", discovered[0][0].profile_id)

    def test_malformed_operational_design_json_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "guion" / "instagram" / "design" / "roto.json"
            path.parent.mkdir(parents=True)
            path.write_text("{", encoding="utf-8")

            self._assert_operational_error(
                lambda: ProfileResolver(root).discover("guion", "instagram", "design"),
                "CONFIG",
                json.JSONDecodeError,
            )

    def test_design_profile_with_invalid_identity_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_design_profile(
                root,
                {
                    "component": "guion",
                    "platform": "youtube",
                    "family": "design",
                    "profile_id": "guion_instagram_design_valido",
                    "display_name": "Diseño inválido",
                    "subtitle_config": "single_line",
                    "subtitle_profile": {"style": "single_line"},
                },
            )

            self._assert_operational_error(
                lambda: ProfileResolver(root).discover("guion", "instagram", "design"),
                "PROFILE",
                ValueError,
            )

    def test_design_subtitle_domain_json_is_not_scanned_as_a_subtitle_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "guion" / "instagram" / "design" / "subtitulo.json"
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    {"profile_id": "subtitulo_guion_instagram_design_linea_unica"}
                ),
                encoding="utf-8",
            )

            self._assert_operational_error(
                lambda: ProfileResolver(root).discover("guion", "instagram", "design"),
                "PROFILE",
                ValueError,
            )

    def test_duplicate_profile_id_in_dynamic_family_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            family = root / "guion" / "instagram" / "test_family"
            family.mkdir(parents=True)
            payload = {
                "component": "guion",
                "platform": "instagram",
                "family": "test_family",
                "profile_id": "perfil_prueba",
                "display_name": "Duplicado",
            }
            for name in ("uno.json", "dos.json"):
                (family / name).write_text(json.dumps(payload), encoding="utf-8")

            self._assert_operational_error(
                lambda: ProfileResolver(root).discover("guion", "instagram", "test_family"),
                "AMBIGUITY",
                ValueError,
            )

    def test_catalog_rejects_an_invalid_dynamic_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self._write_profile(root)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["platform"] = "youtube"
            path.write_text(json.dumps(payload), encoding="utf-8")

            self._assert_operational_error(
                lambda: ProfileResolver(root).discover_families("guion", "instagram"),
                "PROFILE",
                ValueError,
            )

    def test_catalog_adds_and_removes_dynamic_family_from_valid_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self._write_profile(root)
            resolver = ProfileResolver(root)

            self.assertEqual(
                ("test_family",),
                tuple(family for family in resolver.discover_families("guion", "instagram")),
            )

            path.unlink()
            path.parent.rmdir()

            self.assertEqual(
                (),
                resolver.discover_families("guion", "instagram"),
            )

    def test_selector_shows_dynamic_family_and_returns_technical_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_profile(root)
            self._write_profile(
                root,
                family_name="estandar",
                profile_id="guion_instagram",
            )
            self._write_subtitle_profile(root)
            controller = RunController(
                profile_resolver=ProfileResolver(root),
                subtitle_profile_resolver=SubtitleProfileResolver(root),
            )

            with patch("builtins.input", side_effect=("1", "1", "1", "1")), patch(
                "builtins.print"
            ) as print_mock:
                selected = controller.select_profile("script")
            resolved_subtitle = controller.subtitle_profile_resolver.load(
                selected["subtitle_profile_key"]
            )

        printed = "\n".join(
            str(call.args[0]) for call in print_mock.call_args_list if call.args
        )
        self.assertIn("TEST FAMILY", printed)
        self.assertNotIn("\\nTEST FAMILY", printed)
        self.assertEqual("estandar", selected["profile_key"].family)
        self.assertEqual("test_family", selected["subtitle_profile_key"].family)
        self.assertEqual("guion_instagram", selected["profile_key"].profile_id)
        self.assertEqual(
            root / "guion" / "instagram" / "estandar" / "perfil.json",
            selected["path"],
        )
        subtitle_key = resolved_subtitle.key
        self.assertEqual("test_family", subtitle_key.family)
        self.assertEqual(
            "subtitulo_prueba",
            subtitle_key.profile_id,
        )
        self.assertEqual(
            subtitle_key.profile_id,
            resolved_subtitle.key.profile_id,
        )

    def test_family_labels_are_generic_presentation(self):
        controller = RunController()

        self.assertEqual("FUTURE FAMILY", controller._family_label("future_family"))

    def test_dynamic_family_has_no_estandar_fallback_or_cross_context_resolution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_profile(root)
            resolver = ProfileResolver(root)
            missing = ProfileKey(
                "guion",
                "instagram",
                "ausente",
                "test_family",
            )
            cross_platform = ProfileKey(
                "guion",
                "youtube",
                "perfil_prueba",
                "test_family",
            )
            cross_component = ProfileKey(
                "imagen",
                "instagram",
                "perfil_prueba",
                "test_family",
            )
            absent_family = ProfileKey(
                "guion",
                "instagram",
                "perfil_prueba",
                "inexistente",
            )

            for key in (missing, cross_platform, cross_component, absent_family):
                with self.subTest(profile_id=key.profile_id):
                    self._assert_operational_error(
                        lambda key=key: resolver.resolve(key),
                        "PROFILE",
                        FileNotFoundError,
                    )

    def test_dynamic_resolve_rejects_mismatched_internal_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self._write_profile(root)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["family"] = "otra"
            path.write_text(json.dumps(payload), encoding="utf-8")
            key = ProfileKey(
                "guion",
                "instagram",
                "perfil_prueba",
                "test_family",
            )

            self._assert_operational_error(
                lambda: ProfileResolver(root).resolve(key),
                "PROFILE",
                ValueError,
            )

    def test_dynamic_resolve_returns_the_single_matching_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self._write_profile(root)
            key = ProfileKey(
                "guion",
                "instagram",
                "perfil_prueba",
                "test_family",
            )

            resolved = ProfileResolver(root).resolve(key)

        self.assertEqual(path, resolved)

    def test_dynamic_resolve_rejects_duplicate_profile_id(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self._write_profile(root)
            duplicate = path.with_name("perfil_test_family_duplicado.json")
            duplicate.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            key = ProfileKey(
                "guion",
                "instagram",
                "perfil_prueba",
                "test_family",
            )

            self._assert_operational_error(
                lambda: ProfileResolver(root).resolve(key),
                "AMBIGUITY",
                ValueError,
            )

    def test_dynamic_resolve_propagates_corrupt_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_profile(root)
            corrupt = root / "guion" / "instagram" / "test_family" / "roto.json"
            corrupt.write_text("{", encoding="utf-8")
            key = ProfileKey(
                "guion",
                "instagram",
                "perfil_prueba",
                "test_family",
            )

            self._assert_operational_error(
                lambda: ProfileResolver(root).resolve(key),
                "CONFIG",
                json.JSONDecodeError,
            )

    def test_dynamic_subtitle_key_cannot_cross_to_another_family(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_profile(root)
            self._write_subtitle_profile(root)
            profile_key = ProfileKey(
                "guion",
                "instagram",
                "perfil_prueba",
                "test_family",
            )
            other_family_key = SubtitleProfileKey(
                component="guion",
                platform="instagram",
                profile_id="subtitulo_guion_instagram_otra_linea_unica",
                family="otra",
                parent_profile_id=profile_key.profile_id,
            )

            self._assert_operational_error(
                lambda: SubtitleProfileResolver(root).load_selection(
                    profile_key, other_family_key
                ),
                "PROFILE",
                FileNotFoundError,
            )

    def test_autonomous_design_selection_is_capability_driven(self):
        subtitle_resolver = SubtitleProfileResolver()
        design_selection = subtitle_resolver.discover_profiles_for_family(
            "guion", "instagram", "design",
        )[0].key

        self.assertEqual(
            design_selection,
            subtitle_resolver.load_selection(
                ProfileKey.for_component("guion", "instagram"),
                design_selection,
            ).key,
        )
        self.assertEqual(
            design_selection,
            subtitle_resolver.load_selection(
                ProfileKey.for_component("guion", "instagram"),
                design_selection,
            ).key,
        )

    def test_generic_resolution_checks_the_profiles_root_boundary_for_design(self):
        resolver = SubtitleProfileResolver()
        design_key = resolver.discover_profiles_for_family(
            "guion", "instagram", "design",
        )[0].key

        with patch.object(
            resolver,
            "_ensure_within_profiles_root",
            side_effect=ValueError("La ruta de subtitulos queda fuera de config/profiles."),
        ):
            with self.assertRaisesRegex(ValueError, "fuera de config/profiles"):
                resolver.resolve(design_key)

    def test_select_profile_routes_all_supported_scopes_to_active_selector(self):
        controller = RunController()
        expected = {
            "script": ("guion", True),
            "design_image": ("imagen", False),
            "design_video": ("video", False),
            "image": ("imagen", True),
            "video": ("video", True),
            "studio": ("studio", True),
        }

        with patch.object(
            controller,
            "_select_profile_identity",
            side_effect=lambda component, **_: {"component": component.value},
        ) as selector:
            for scope, (component, select_subtitles) in expected.items():
                with self.subTest(scope=scope):
                    self.assertEqual(
                        {"component": component}, controller.select_profile(scope)
                    )

        self.assertEqual(6, selector.call_count)
        self.assertEqual(
            [
                ((ProfileComponent(component),), {"select_subtitles": select_subtitles})
                for component, select_subtitles in expected.values()
            ],
            [(call.args, call.kwargs) for call in selector.call_args_list],
        )
        with self.assertRaisesRegex(ValueError, "Ámbito de perfil no soportado"):
            controller.select_profile("unsupported")
