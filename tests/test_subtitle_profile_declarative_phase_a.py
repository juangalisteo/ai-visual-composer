import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app.controllers.run_controller import RunController
from app.modules.studio import StudioInputMode
from app.shared.config_manager import ConfigManager
from app.shared.operational_error import OperationalError
from app.shared.profile_identity import ProfileComponent
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


class SubtitleProfileDeclarativePhaseATest(unittest.TestCase):

    def test_vertical_standard_catalog_uses_the_final_visible_names(self):
        resolver = SubtitleProfileResolver()
        expected_names = [
            "Doble línea",
            "Dos palabras",
            "Línea única",
            "Palabra única",
            "Tres palabras",
        ]

        for component in ProfileComponent:
            with self.subTest(component=component.value):
                descriptors = resolver.discover_profiles_for_family(
                    component,
                    "vertical",
                    "estandar",
                )
                by_id = {
                    descriptor.profile_id: descriptor
                    for descriptor in descriptors
                }

                self.assertEqual(
                    expected_names,
                    [descriptor.display_name for descriptor in descriptors],
                )
                self.assertEqual(
                    "word_by_word",
                    by_id[
                        f"subtitulo_{component.value}_vertical_"
                        "palabra_por_palabra"
                    ].mode,
                )
                self.assertEqual(
                    "three_two_words",
                    by_id[
                        f"subtitulo_{component.value}_vertical_dos_tres"
                    ].mode,
                )

    def test_vertical_standard_two_line_profiles_are_discovered_and_resolved(self):
        resolver = SubtitleProfileResolver()

        for component in ProfileComponent:
            with self.subTest(component=component.value):
                profile_id = (
                    f"subtitulo_{component.value}_vertical_doble_linea"
                )
                key = SubtitleProfileKey(
                    component=component,
                    platform="vertical",
                    family="estandar",
                    profile_id=profile_id,
                )
                descriptors = resolver.discover_profiles_for_family(
                    component,
                    "vertical",
                    "estandar",
                )
                descriptor = next(
                    item for item in descriptors if item.key == key
                )
                resolved = resolver.load(key)

                self.assertEqual("Doble línea", descriptor.display_name)
                self.assertEqual("two_lines", descriptor.mode)
                self.assertEqual(2, resolved.cue_policy["max_lines"])
                self.assertEqual(
                    0.75,
                    resolved.cue_policy["balance_ratio_threshold"],
                )
                self.assertEqual(key, resolved.key)

    def test_vertical_standard_two_word_profiles_are_discovered_and_resolved(self):
        resolver = SubtitleProfileResolver()

        for component in ProfileComponent:
            with self.subTest(component=component.value):
                profile_id = (
                    f"subtitulo_{component.value}_vertical_dos_palabras"
                )
                key = SubtitleProfileKey(
                    component=component,
                    platform="vertical",
                    family="estandar",
                    profile_id=profile_id,
                )
                descriptors = resolver.discover_profiles_for_family(
                    component,
                    "vertical",
                    "estandar",
                )
                descriptor = next(
                    item for item in descriptors if item.key == key
                )
                resolved = resolver.load(key)

                self.assertEqual("Dos palabras", descriptor.display_name)
                self.assertEqual("three_two_words", descriptor.mode)
                self.assertEqual(2, resolved.cue_policy["fixed_chunk_size"])
                self.assertEqual(key, resolved.key)

    def test_vertical_standard_two_three_profiles_use_the_default_rhythm(self):
        resolver = SubtitleProfileResolver()

        for component in ProfileComponent:
            with self.subTest(component=component.value):
                profile_id = (
                    f"subtitulo_{component.value}_vertical_dos_tres"
                )
                key = SubtitleProfileKey(
                    component=component,
                    platform="vertical",
                    family="estandar",
                    profile_id=profile_id,
                )
                descriptors = resolver.discover_profiles_for_family(
                    component,
                    "vertical",
                    "estandar",
                )
                descriptor = next(
                    item for item in descriptors if item.key == key
                )
                resolved = resolver.load(key)

                self.assertEqual("Tres palabras", descriptor.display_name)
                self.assertEqual("three_two_words", descriptor.mode)
                self.assertNotIn("fixed_chunk_size", resolved.cue_policy)
                self.assertEqual(key, resolved.key)

    def test_all_standard_profiles_are_discovered_and_resolved_by_profile_id(self):
        resolver = SubtitleProfileResolver()

        for component in ProfileComponent:
            for platform in ("horizontal", "vertical"):
                with self.subTest(
                    component=component.value,
                    platform=platform,
                ):
                    descriptors = resolver.discover_profiles_for_family(
                        component, platform, "estandar",
                    )

                    word_by_word_name = (
                        "Palabra única"
                        if platform == "vertical"
                        else "Palabra por palabra"
                    )
                    self.assertTrue(
                        {"Línea única", word_by_word_name}.issubset(
                            {descriptor.display_name for descriptor in descriptors}
                        )
                    )
                    self.assertEqual(
                        len(descriptors),
                        len({descriptor.profile_id for descriptor in descriptors}),
                    )

                    for descriptor in descriptors:
                        resolved = resolver.load(descriptor.key)
                        self.assertEqual(descriptor.profile_id, resolved.key.profile_id)
                        self.assertEqual(descriptor.display_name, resolved.display_name)

    def test_copy_paste_profile_with_same_style_is_discovered_selected_and_resolved(self):
        source = Path(
            "config/profiles/studio/vertical/estandar/subtitulos/"
            "subtitulo_studio_vertical_linea_unica.json"
        )

        with tempfile.TemporaryDirectory() as directory:
            config_root = Path(directory) / "config"
            profiles_root = config_root / "profiles"
            target_directory = profiles_root / "studio/vertical/estandar/subtitulos"
            target_directory.mkdir(parents=True)
            copied = target_directory / source.name
            shutil.copyfile(source, copied)

            custom_id = "subtitulo_studio_vertical_linea_unica_personalizado"
            custom = json.loads(copied.read_text(encoding="utf-8"))
            custom["profile_id"] = custom_id
            custom["display_name"] = "Mi subtítulo personalizado"
            custom_path = target_directory / f"{custom_id}.json"
            custom_path.write_text(
                json.dumps(custom, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            resolver = SubtitleProfileResolver(profiles_root)
            descriptors = resolver.discover_profiles_for_family(
                "studio", "vertical", "estandar",
            )
            by_id = {descriptor.profile_id: descriptor for descriptor in descriptors}

            self.assertEqual(2, len(descriptors))
            self.assertEqual("three_two_words", by_id[custom_id].mode)
            self.assertEqual(
                "Mi subtítulo personalizado",
                by_id[custom_id].display_name,
            )
            self.assertEqual(
                "three_two_words",
                by_id["subtitulo_studio_vertical_linea_unica"].mode,
            )

            controller = RunController(subtitle_profile_resolver=resolver)
            messages = []
            controller._print = messages.append
            controller._select_from_list = Mock(
                side_effect=("estandar", by_id[custom_id]),
            )
            selected, original = controller._select_studio_subtitle_profile(
                StudioInputMode.SRT_VIDEO.value,
                platform="vertical",
            )

            self.assertEqual(by_id[custom_id].key, selected)
            self.assertTrue(original)
            self.assertIn("2. Mi subtítulo personalizado", messages)
            self.assertNotIn(custom_id, messages)
            self.assertNotIn("ORIGINAL", "\n".join(messages))

            resolved = ConfigManager(
                subtitle_profile_resolver=resolver,
            ).get_subtitle_profile_by_key(by_id[custom_id].key)

            self.assertEqual(custom_path, resolved.path)
            self.assertEqual(custom_id, resolved.key.profile_id)
            self.assertEqual("three_two_words", resolved.cue_policy["mode"])
            self.assertEqual("Mi subtítulo personalizado", resolved.display_name)

    def test_new_standard_profile_requires_display_name(self):
        source = Path(
            "config/profiles/studio/vertical/estandar/subtitulos/"
            "subtitulo_studio_vertical_linea_unica.json"
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "profiles"
            target = root / "studio/vertical/estandar/subtitulos"
            target.mkdir(parents=True)
            data = json.loads(source.read_text(encoding="utf-8"))
            data["profile_id"] = "subtitulo_studio_vertical_linea_unica_sin_nombre"
            data.pop("display_name")
            (target / f"{data['profile_id']}.json").write_text(
                json.dumps(data, ensure_ascii=False),
                encoding="utf-8",
            )

            with self.assertRaises(OperationalError) as captured:
                SubtitleProfileResolver(root).discover_profiles_for_family(
                    "studio", "vertical", "estandar",
                )
            self.assertEqual("VALIDATION", captured.exception.context.family)
            self.assertIsInstance(captured.exception.__cause__, ValueError)

    def test_original_remains_outside_the_declarative_catalog(self):
        resolver = SubtitleProfileResolver()
        descriptors = resolver.discover_profiles_for_family(
            "studio", "horizontal", "design",
        )
        profile_ids = {descriptor.profile_id for descriptor in descriptors}

        self.assertNotIn("original", profile_ids)
        descriptor = next(
            item for item in descriptors
            if item.profile_id == "modo_conciencia_youtube"
        )

        controller = RunController(subtitle_profile_resolver=resolver)
        controller._print = Mock()
        controller._select_from_list = Mock(side_effect=("design", descriptor))
        selected, original = controller._select_studio_subtitle_profile(
            StudioInputMode.SRT_VIDEO.value,
            platform="horizontal",
        )

        self.assertEqual(descriptor.key, selected)
        self.assertTrue(original)

    def test_design_remains_automatic_and_self_contained(self):
        resolver = SubtitleProfileResolver()
        descriptor = next(
            item for item in resolver.discover_profiles_for_family(
                "studio", "vertical", "design",
            )
            if item.profile_id == "modo_conciencia_reels"
        )

        self.assertEqual("word_by_word", descriptor.mode)
        self.assertEqual("Modo Conciencia | Reels", descriptor.display_name)
        self.assertEqual(
            "word_by_word",
            resolver.load(
                SubtitleProfileKey(
                    "studio", "vertical", "modo_conciencia_reels", "design",
                )
            ).cue_policy["mode"],
        )
