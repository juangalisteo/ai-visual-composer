import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from app.controllers.interaction import labels
from app.controllers.interaction.contracts import StudioProfileSelection
from app.controllers.run_controller import RunController
from app.modules.studio import StudioInputMode
from app.shared.profile_resolver import ProfileResolver
from app.shared.profile_identity import OperationalProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


class StudioOperationalIdentityTest(unittest.TestCase):

    def test_dynamic_operational_and_subtitle_keys_are_discovered_independently(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            operational_key, subtitle_key = self._write_dynamic_profiles(root)
            profile_resolver = ProfileResolver(root)
            subtitle_resolver = SubtitleProfileResolver(root)
            controller = RunController(
                profile_resolver=profile_resolver,
                subtitle_profile_resolver=subtitle_resolver,
                studio_profile_loader=Mock(load=Mock(return_value=SimpleNamespace())),
            )
            descriptor = subtitle_resolver.discover_profiles_for_family(
                "studio", "test_format", "test_family",
            )[0]
            controller._select_from_list = Mock(
                side_effect=("test_format", "test_family", descriptor),
            )

            selection = controller._select_studio_profile_selection(
                StudioInputMode.SRT_VIDEO.value,
            )
            selected_operational = selection.operational.operational_key

        self.assertEqual(
            OperationalProfileKey(
                operational_key.component,
                operational_key.format,
                operational_key.profile_id,
            ),
            selected_operational,
        )
        self.assertEqual(subtitle_key, selection.subtitle.subtitle_key)
        self.assertNotEqual(
            selected_operational.profile_id,
            selection.subtitle.subtitle_key.profile_id,
        )
        self.assertTrue(selection.subtitle.subtitle_original)
        self.assertIsInstance(selection, StudioProfileSelection)
        self.assertFalse(hasattr(controller, "_active_studio_subtitle_key"))

    def test_subtitle_selection_uses_operational_format_as_discovery_context(self):
        controller = RunController()
        descriptor = SubtitleProfileResolver().discover_profiles_for_family(
            "studio", "vertical", "estandar",
        )[0]
        messages = []
        controller._print = messages.append
        controller._select_from_list = Mock(
            side_effect=("estandar", descriptor),
        )

        selected, original = controller._select_studio_subtitle_profile(
            StudioInputMode.SRT_VIDEO.value,
            profile_format="vertical",
        )

        self.assertEqual(descriptor.key, selected)
        self.assertTrue(original)
        self.assertNotIn("PLATAFORMA", "\n".join(messages))
        controller._select_from_list.assert_any_call(
            labels.presentation_families(
                SubtitleProfileResolver().discover_families(
                    "studio",
                    "vertical",
                ),
            ),
        )

    @staticmethod
    def _write_dynamic_profiles(root):
        operational_source = Path(
            "config/profiles/studio/vertical/perfil_studio_vertical.json"
        )
        subtitle_source = Path(
            "config/profiles/studio/vertical/estandar/subtitulos/"
            "subtitulo_studio_vertical_linea_unica.json"
        )
        operational = json.loads(operational_source.read_text(encoding="utf-8"))
        operational.update({
            "component": "studio",
            "format": "test_format",
            "profile_id": "test_operational",
            "display_name": "Operational test",
        })
        subtitle = json.loads(subtitle_source.read_text(encoding="utf-8"))
        subtitle.update({
            "component": "studio",
            "format": "test_format",
            "family": "test_family",
            "profile_id": "test_subtitle",
            "display_name": "Subtitle test",
        })
        directory = root / "studio" / "test_format"
        directory.mkdir(parents=True)
        (directory / "test_operational.json").write_text(
            json.dumps(operational), encoding="utf-8",
        )
        subtitle_directory = directory / "test_family" / "subtitulos"
        subtitle_directory.mkdir(parents=True)
        (subtitle_directory / "test_subtitle.json").write_text(
            json.dumps(subtitle), encoding="utf-8",
        )
        return (
            ProfileResolver(root).discover_operational_profiles(
                "studio", "test_format",
            )[0].key,
            SubtitleProfileResolver(root).discover_profiles_for_family(
                "studio", "test_format", "test_family",
            )[0].key,
        )


if __name__ == "__main__":
    unittest.main()
