import json
import math
import unittest
from pathlib import Path

from app.providers.ollama_settings import (
    OllamaCallSettings,
    ollama_call_settings,
)
from app.shared.operational_error import OperationalError


class OllamaCallSettingsTest(unittest.TestCase):

    def test_only_model_declared_sends_nothing_else(self):
        settings = ollama_call_settings({"model": "test-model"}, "test_task")

        self.assertEqual(
            OllamaCallSettings(model="test-model"),
            settings,
        )
        self.assertIsNone(settings.keep_alive)
        self.assertIsNone(settings.think)
        self.assertIsNone(settings.options)

    def test_keep_alive_is_global_and_zero_is_kept(self):
        for value in (0, 0.0, 300, -1, "5m", " 10s "):
            with self.subTest(value=value):
                settings = ollama_call_settings(
                    {"model": "test-model", "keep_alive": value},
                    "test_task",
                )
                expected = value.strip() if isinstance(value, str) else value
                self.assertEqual(expected, settings.keep_alive)
                self.assertIsNotNone(settings.keep_alive)

    def test_keep_alive_rejects_values_ollama_cannot_read(self):
        for value in (True, False, "", "  ", [], {}, math.nan, math.inf):
            with self.subTest(value=value):
                with self.assertRaises(OperationalError) as caught:
                    ollama_call_settings(
                        {"model": "test-model", "keep_alive": value}
                    )
                self.assertEqual("CONFIG", caught.exception.context.family)
                self.assertIn("keep_alive", caught.exception.context.user_message)

    def test_task_section_overrides_model_and_declares_think_and_options(self):
        ai_config = {
            "model": "global-model",
            "keep_alive": 0,
            "test_task": {
                "model": "task-model",
                "think": False,
                "options": {"num_ctx": 8192},
            },
        }

        settings = ollama_call_settings(ai_config, "test_task")
        other = ollama_call_settings(ai_config, "other_task")
        without_task = ollama_call_settings(ai_config)

        self.assertEqual("task-model", settings.model)
        self.assertIs(False, settings.think)
        self.assertEqual({"num_ctx": 8192}, dict(settings.options))
        self.assertEqual(0, settings.keep_alive)
        self.assertEqual(
            OllamaCallSettings(model="global-model", keep_alive=0),
            other,
        )
        self.assertEqual(other, without_task)

    def test_think_accepts_true_false_and_null_only(self):
        for value in (True, False, None):
            with self.subTest(value=value):
                settings = ollama_call_settings(
                    {"model": "m", "test_task": {"think": value}},
                    "test_task",
                )
                self.assertIs(value, settings.think)
        for value in ("sí", 1, 0, "false"):
            with self.subTest(value=value):
                with self.assertRaises(OperationalError) as caught:
                    ollama_call_settings(
                        {"model": "m", "test_task": {"think": value}},
                        "test_task",
                    )
                self.assertIn("test_task.think", caught.exception.context.user_message)

    def test_num_ctx_must_be_a_positive_whole_number_of_tokens(self):
        for value in (0, -4096, 8192.0, "8192", True, None):
            with self.subTest(value=value):
                with self.assertRaises(OperationalError) as caught:
                    ollama_call_settings(
                        {
                            "model": "m",
                            "test_task": {"options": {"num_ctx": value}},
                        },
                        "test_task",
                    )
                self.assertIn("num_ctx", caught.exception.context.user_message)

    def test_options_pass_through_as_declared_and_are_immutable(self):
        options = {"num_ctx": 4096, "temperature": 0.2}
        settings = ollama_call_settings(
            {"model": "m", "test_task": {"options": options}},
            "test_task",
        )
        options["num_ctx"] = 1

        self.assertEqual({"num_ctx": 4096, "temperature": 0.2}, dict(settings.options))
        with self.assertRaises(TypeError):
            settings.options["num_ctx"] = 2

    def test_malformed_sections_and_missing_model_are_config_errors(self):
        cases = (
            ({}, None),
            ({"model": "  "}, None),
            ({"model": 7}, None),
            ({"model": "m", "test_task": "texto"}, "test_task"),
            ({"model": "m", "test_task": {"model": ""}}, "test_task"),
            ({"model": "m", "test_task": {"options": []}}, "test_task"),
            ([], None),
        )
        for ai_config, task in cases:
            with self.subTest(ai_config=ai_config):
                with self.assertRaises(OperationalError) as caught:
                    ollama_call_settings(ai_config, task)
                self.assertEqual("CONFIG", caught.exception.context.family)
                self.assertEqual("config/ai.json", caught.exception.context.resource)


class ProjectAiConfigurationTest(unittest.TestCase):
    """What config/ai.json declares after phase I2."""

    def setUp(self):
        self.ai_config = json.loads(
            Path("config/ai.json").read_text(encoding="utf-8")
        )

    def test_ollama_frees_the_gpu_as_soon_as_it_answers(self):
        self.assertEqual(0, self.ai_config["keep_alive"])

    def test_storyboard_context_fits_twelve_scenes(self):
        # Measured in I0: 12 scenes = 3275 prompt + 2146 answer = 5421 tokens.
        settings = ollama_call_settings(self.ai_config, "storyboard")
        self.assertGreaterEqual(settings.options["num_ctx"], 5421)

    def test_provider_key_nobody_reads_is_gone(self):
        self.assertNotIn("provider", self.ai_config)


if __name__ == "__main__":
    unittest.main()
