import json
import tempfile
import unittest
from pathlib import Path

from app.shared.config_manager import ConfigManager
from app.shared.operational_error import OperationalError
from app.shared.profile_identity import ProfileKey
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


class LegacySubtitleTransportTest(unittest.TestCase):

    def setUp(self):
        self.profile_key = ProfileKey.for_component("studio", "instagram")
        self.resolver = SubtitleProfileResolver()
        self.single_line = next(
            item.key
            for item in self.resolver.discover_profiles_for_family(
                "studio", "instagram", "estandar",
            )
            if item.mode == "single_line"
        )

    def test_modern_resolution_requires_and_uses_the_exact_key(self):
        resolved = self.resolver.load(self.single_line)

        self.assertEqual(self.single_line, resolved.key)
        with self.assertRaises(OperationalError) as captured:
            self.resolver.load(self.single_line.profile_id)
        self.assertEqual("VALIDATION", captured.exception.context.family)
        self.assertIsInstance(captured.exception.__cause__, TypeError)

    def test_legacy_profile_id_adapts_once_to_a_complete_key(self):
        adapted = self.resolver.adapt_legacy_selection(
            self.profile_key,
            self.single_line.profile_id,
        )

        self.assertEqual(self.single_line, adapted)
        self.assertEqual(adapted, self.resolver.load(adapted).key)

    def test_legacy_display_name_and_mode_do_not_become_identity(self):
        with self.assertRaisesRegex(ValueError, "No existe el perfil"):
            self.resolver.adapt_legacy_selection(
                self.profile_key,
                "Línea única",
            )

    def test_config_manager_modern_key_does_not_enter_legacy_adapter(self):
        config = ConfigManager(subtitle_profile_resolver=self.resolver)

        resolved = config.get_subtitle_profile_by_key(self.single_line)

        self.assertEqual(self.single_line, resolved.key)

    def test_dynamic_fixture_has_no_nominal_python_registration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            key = self._write_profile(
                root,
                profile_id="test_profile",
                mode="word_by_word",
                display_name="Technical label",
            )
            resolver = SubtitleProfileResolver(root)
            profile_key = ProfileKey(
                "studio", "test_platform", "test_operational", "test_family",
            )

            adapted = resolver.adapt_legacy_selection(
                profile_key,
                "test_profile",
            )

            self.assertEqual(key, adapted)
            self.assertEqual("word_by_word", resolver.load(adapted).cue_policy["mode"])
            self.assertEqual(
                key,
                resolver.adapt_legacy_selection(profile_key, "word_by_word"),
            )

    def test_legacy_zero_and_ambiguous_matches_are_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_profile(
                root,
                profile_id="test_profile_one",
                mode="single_line",
                display_name="One",
            )
            self._write_profile(
                root,
                profile_id="test_profile_two",
                mode="single_line",
                display_name="Two",
            )
            resolver = SubtitleProfileResolver(root)
            profile_key = ProfileKey(
                "studio", "test_platform", "test_operational", "test_family",
            )

            with self.assertRaisesRegex(ValueError, "No existe el perfil"):
                resolver.adapt_legacy_selection(profile_key, "missing_profile")
            with self.assertRaisesRegex(ValueError, "ambigua"):
                resolver.adapt_legacy_selection(profile_key, "single_line")

    @staticmethod
    def _write_profile(root, profile_id, mode, display_name):
        source = Path(
            "config/profiles/studio/instagram/estandar/subtitulos/"
            "subtitulo_studio_instagram_linea_unica.json"
        )
        payload = json.loads(source.read_text(encoding="utf-8"))
        payload.update({
            "component": "studio",
            "platform": "test_platform",
            "family": "test_family",
            "profile_id": profile_id,
            "display_name": display_name,
            "cue_policy": {**payload["cue_policy"], "mode": mode},
        })
        path = (
            root / "studio" / "test_platform" / "test_family"
            / "subtitulos" / f"{profile_id}.json"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return SubtitleProfileKey(
            "studio", "test_platform", profile_id, "test_family",
        )


if __name__ == "__main__":
    unittest.main()
