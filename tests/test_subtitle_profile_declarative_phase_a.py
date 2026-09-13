import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.controllers.run_controller import RunController
from app.modules.studio import StudioInputMode
from app.shared.config_manager import ConfigManager
from app.shared.profile_identity import ProfileComponent, ProfileKey, ProfilePlatform
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


class SubtitleProfileDeclarativePhaseATest(unittest.TestCase):

    def test_all_standard_profiles_are_discovered_and_resolved_by_profile_id(self):
        resolver = SubtitleProfileResolver()

        for component in ProfileComponent:
            for platform in ProfilePlatform:
                with self.subTest(
                    component=component.value,
                    platform=platform.value,
                ):
                    profile_key = ProfileKey.for_component(component, platform)
                    descriptors = resolver.discover_profiles(profile_key)

                    self.assertTrue(
                        {"Línea única", "Palabra por palabra"}.issubset(
                            {descriptor.display_name for descriptor in descriptors}
                        )
                    )
                    self.assertEqual(
                        len(descriptors),
                        len({descriptor.profile_id for descriptor in descriptors}),
                    )

                    for descriptor in descriptors:
                        resolved = resolver.load_selection(
                            profile_key,
                            descriptor.profile_id,
                        )
                        self.assertEqual(descriptor.profile_id, resolved.key.profile_id)
                        self.assertEqual(descriptor.display_name, resolved.display_name)

                    controller = RunController(
                        subtitle_profile_resolver=resolver,
                    )
                    messages = []
                    controller._print = messages.append
                    controller._select_from_list = Mock(
                        return_value=descriptors[0].profile_id,
                    )
                    self.assertEqual(
                        descriptors[0].profile_id,
                        controller.select_subtitle_config(profile_key),
                    )
                    self.assertIn(
                        f"1. {descriptors[0].display_name}",
                        messages,
                    )

    def test_copy_paste_profile_with_same_style_is_discovered_selected_and_resolved(self):
        profile_key = ProfileKey.for_component("studio", "instagram")
        source = Path(
            "config/profiles/studio/instagram/estandar/"
            "subtitulo_studio_instagram_linea_unica.json"
        )

        with tempfile.TemporaryDirectory() as directory:
            config_root = Path(directory) / "config"
            profiles_root = config_root / "profiles"
            target_directory = profiles_root / "studio/instagram/estandar"
            target_directory.mkdir(parents=True)
            copied = target_directory / source.name
            shutil.copyfile(source, copied)

            custom_id = "subtitulo_studio_instagram_linea_unica_personalizado"
            custom = json.loads(copied.read_text(encoding="utf-8"))
            custom["profile_id"] = custom_id
            custom["display_name"] = "Mi subtítulo personalizado"
            custom_path = target_directory / f"{custom_id}.json"
            custom_path.write_text(
                json.dumps(custom, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            resolver = SubtitleProfileResolver(profiles_root)
            descriptors = resolver.discover_profiles(profile_key)
            by_id = {descriptor.profile_id: descriptor for descriptor in descriptors}

            self.assertEqual(2, len(descriptors))
            self.assertEqual("single_line", by_id[custom_id].style)
            self.assertEqual(
                "Mi subtítulo personalizado",
                by_id[custom_id].display_name,
            )
            self.assertEqual(
                "single_line",
                by_id["subtitulo_studio_instagram_linea_unica"].style,
            )
            with self.assertRaisesRegex(ValueError, "style es ambigua"):
                resolver.load_selection(profile_key, "single_line")

            controller = RunController(subtitle_profile_resolver=resolver)
            catalog_messages = []
            controller._print = catalog_messages.append
            controller._select_from_list = Mock(return_value=custom_id)
            self.assertEqual(
                custom_id,
                controller.select_studio_subtitle_config(profile_key),
            )
            self.assertIn("2. Mi subtítulo personalizado", catalog_messages)

            messages = []
            controller._print = messages.append
            controller._select_from_list = Mock(return_value=custom_id)
            selected, original = controller.select_studio_subtitle_options(
                profile_key,
                StudioInputMode.SRT_VIDEO.value,
            )

            self.assertEqual(custom_id, selected)
            self.assertFalse(original)
            self.assertEqual("1. ORIGINAL", messages[1])
            self.assertIn("3. Mi subtítulo personalizado", messages)
            self.assertNotIn(custom_id, messages)

            environment = {
                "MC_PROFILE_COMPONENT": "studio",
                "MC_PROFILE_PLATFORM": "instagram",
                "MC_PROFILE_ID": profile_key.profile_id,
                "MC_PROFILE_FAMILY": "system",
            }
            with patch.dict(os.environ, environment, clear=True):
                resolved = ConfigManager(
                    subtitle_profile_resolver=resolver,
                ).get_subtitle_profile(custom_id)

            self.assertEqual(custom_path, resolved.path)
            self.assertEqual(custom_id, resolved.key.profile_id)
            self.assertEqual("single_line", resolved.key.style)
            self.assertEqual("Mi subtítulo personalizado", resolved.display_name)

    def test_new_standard_profile_requires_display_name(self):
        profile_key = ProfileKey.for_component("studio", "instagram")
        source = Path(
            "config/profiles/studio/instagram/estandar/"
            "subtitulo_studio_instagram_linea_unica.json"
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "profiles"
            target = root / "studio/instagram/estandar"
            target.mkdir(parents=True)
            data = json.loads(source.read_text(encoding="utf-8"))
            data["profile_id"] = "subtitulo_studio_instagram_linea_unica_sin_nombre"
            data.pop("display_name")
            (target / f"{data['profile_id']}.json").write_text(
                json.dumps(data, ensure_ascii=False),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "requiere display_name"):
                SubtitleProfileResolver(root).discover_profiles(profile_key)

    def test_style_selection_is_compatible_only_when_unambiguous(self):
        resolver = SubtitleProfileResolver()
        profile_key = ProfileKey.for_component("video", "youtube")
        resolved = resolver.load_selection(profile_key, "single_line")

        self.assertEqual(
            "subtitulo_video_youtube_linea_unica",
            resolved.key.profile_id,
        )

    def test_original_remains_outside_the_declarative_catalog(self):
        profile_key = ProfileKey.for_component("studio", "youtube")
        resolver = SubtitleProfileResolver()
        profile_ids = {
            descriptor.profile_id
            for descriptor in resolver.discover_profiles(profile_key)
        }

        self.assertNotIn("original", profile_ids)

        controller = RunController(subtitle_profile_resolver=resolver)
        controller._print = Mock()
        controller._select_from_list = Mock(return_value="original")
        selected, original = controller.select_studio_subtitle_options(
            profile_key,
            StudioInputMode.SRT_VIDEO.value,
        )

        self.assertEqual("single_line", selected)
        self.assertTrue(original)

    def test_design_remains_automatic_and_self_contained(self):
        profile_key = ProfileKey.for_component(
            "studio",
            "instagram",
            family="design",
            profile_id="studio_instagram_design_modo_conciencia_studio_1",
        )
        resolver = SubtitleProfileResolver()
        descriptor = resolver.discover_profiles(profile_key)[0]

        self.assertEqual("word_by_word", descriptor.style)
        self.assertEqual("Modo Conciencia - Studio #1", descriptor.display_name)
        self.assertEqual("word_by_word", resolver.load_selection(profile_key, "word_by_word").key.style)
