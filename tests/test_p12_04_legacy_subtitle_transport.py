import unittest

from app.shared.config_manager import ConfigManager
from app.shared.operational_error import OperationalError
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


class LegacySubtitleTransportTest(unittest.TestCase):

    def setUp(self):
        self.resolver = SubtitleProfileResolver()
        self.current_profile = next(
            item.key
            for item in self.resolver.discover_profiles_for_family(
                "studio", "instagram", "estandar",
            )
            if item.profile_id == "subtitulo_studio_instagram_linea_unica"
        )

    def test_modern_resolution_requires_and_uses_the_exact_key(self):
        resolved = self.resolver.load(self.current_profile)

        self.assertEqual(self.current_profile, resolved.key)
        with self.assertRaises(OperationalError) as captured:
            self.resolver.load(self.current_profile.profile_id)
        self.assertEqual("VALIDATION", captured.exception.context.family)
        self.assertIsInstance(captured.exception.__cause__, TypeError)

    def test_config_manager_modern_key_does_not_enter_legacy_adapter(self):
        config = ConfigManager(subtitle_profile_resolver=self.resolver)

        resolved = config.get_subtitle_profile_by_key(self.current_profile)

        self.assertEqual(self.current_profile, resolved.key)


if __name__ == "__main__":
    unittest.main()
