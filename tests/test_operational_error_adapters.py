import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main
from app.shared.config_manager import ConfigManager
from app.shared.operational_error import OperationalError
from app.shared.profile_identity import OperationalProfileKey, ProfileKey
from app.shared.profile_resolver import ProfileResolver
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


class OperationalErrorAdaptersTest(unittest.TestCase):

    def test_missing_and_invalid_general_json_are_contextualized(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manager = ConfigManager()
            missing_path = root / "missing.json"

            with self.assertRaises(OperationalError) as missing:
                manager.load_json(missing_path)

            invalid_path = root / "invalid.json"
            invalid_path.write_text("{invalid", encoding="utf-8")
            with self.assertRaises(OperationalError) as invalid:
                manager.load_json(invalid_path)

        self.assertEqual("CONFIG", missing.exception.context.family)
        self.assertEqual(str(missing_path), missing.exception.context.resource)
        self.assertIsInstance(missing.exception.__cause__, FileNotFoundError)
        self.assertEqual("CONFIG", invalid.exception.context.family)
        self.assertEqual(str(invalid_path), invalid.exception.context.resource)
        self.assertIsInstance(invalid.exception.__cause__, json.JSONDecodeError)

    def test_invalid_operational_profile_json_preserves_path_and_cause(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "video/instagram/broken.json"
            path.parent.mkdir(parents=True)
            path.write_text("{invalid", encoding="utf-8")

            with self.assertRaises(OperationalError) as caught:
                ProfileResolver(root).resolve_operational(
                    OperationalProfileKey("video", "instagram", "test_profile")
                )

        self.assertEqual("CONFIG", caught.exception.context.family)
        self.assertEqual(str(path), caught.exception.context.resource)
        self.assertIsInstance(caught.exception.__cause__, json.JSONDecodeError)

    def test_missing_operational_and_subtitle_keys_are_profile_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            operational_key = OperationalProfileKey(
                "video", "instagram", "test_profile"
            )
            subtitle_key = SubtitleProfileKey(
                "video", "instagram", "test_profile", "estandar"
            )

            with self.assertRaises(OperationalError) as operational:
                ProfileResolver(root).resolve_operational(operational_key)
            with self.assertRaises(OperationalError) as subtitle:
                SubtitleProfileResolver(root).resolve(subtitle_key)

        self.assertEqual("PROFILE", operational.exception.context.family)
        self.assertIn("test_profile", operational.exception.context.resource)
        self.assertIsInstance(operational.exception.__cause__, FileNotFoundError)
        self.assertEqual("PROFILE", subtitle.exception.context.family)
        self.assertIn("test_profile", subtitle.exception.context.resource)
        self.assertIsInstance(subtitle.exception.__cause__, FileNotFoundError)

    def test_duplicate_operational_profiles_are_ambiguity_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "video/instagram"
            folder.mkdir(parents=True)
            key = OperationalProfileKey("video", "instagram", "test_profile")
            data = {
                "component": "video",
                "platform": "instagram",
                "profile_id": "test_profile",
            }
            for name in ("first.json", "second.json"):
                (folder / name).write_text(json.dumps(data), encoding="utf-8")

            with self.assertRaises(OperationalError) as caught:
                ProfileResolver(root).resolve_operational(key)

        self.assertEqual("AMBIGUITY", caught.exception.context.family)
        self.assertEqual(2, len(caught.exception.context.technical_metadata["candidates"]))
        self.assertIsInstance(caught.exception.__cause__, ValueError)

    def test_invalid_subtitle_contract_is_a_validation_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            key = SubtitleProfileKey(
                "video", "instagram", "test_profile", "estandar"
            )
            path = root / key.relative_path
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    {
                        "component": "video",
                        "platform": "instagram",
                        "family": "estandar",
                        "profile_id": "test_profile",
                        "display_name": "Test profile",
                        "cue_policy": "invalid",
                        "render_style": {},
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(OperationalError) as caught:
                SubtitleProfileResolver(root).load(key)

        self.assertEqual("VALIDATION", caught.exception.context.family)
        self.assertEqual(str(path), caught.exception.context.resource)
        self.assertIsInstance(caught.exception.__cause__, TypeError)

    def test_main_presents_real_adapter_error_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            error = None
            try:
                ProfileResolver(Path(directory)).resolve_operational(
                    OperationalProfileKey("video", "instagram", "test_profile")
                )
            except OperationalError as caught:
                error = caught

            options = {
                "profile_component": "video",
                "profile_platform": "instagram",
                "profile_id": "test_profile",
                "subtitle_config": "",
                "voice_config": "",
                "music_category": None,
                "overlays_mode": "off",
                "project_name": "adapter error",
                "visual_pipeline": "video",
                "script_source": "manual_design",
                "design_target": "video",
                "pipeline_mode": "design_video",
                "clear_output": False,
            }
            with patch.dict(os.environ, {}, clear=True), patch(
                "main.RunController"
            ) as controller_mock, patch(
                "main.iniciar",
                side_effect=error,
            ), patch("builtins.print") as print_mock:
                controller_mock.return_value.run.return_value = options

                result = main.main()

        self.assertEqual(1, result)
        self.assertTrue(print_mock.call_args.args[0].startswith("ERROR\n"))
        self.assertNotIn("Traceback", print_mock.call_args.args[0])
        self.assertNotIn("FileNotFoundError", print_mock.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
