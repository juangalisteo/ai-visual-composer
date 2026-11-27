import os
import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

import requests

from app.modules.script.script_builder import ScriptBuilder
from app.providers.ollama_provider import (
    OllamaProvider,
    OllamaRequestError,
    OllamaRequestPolicy,
)
from app.providers.ollama_settings import ollama_call_settings
from app.shared.error_context import ErrorContext, ErrorSeverity, ExitKind
from app.shared.operational_error import OperationalError
from app.shared.prompt_library import PromptLibrary


REPOSITORY_PROMPTS = Path(__file__).resolve().parents[1] / "prompts"


class FakeResponse:

    def __init__(
        self,
        payload=None,
    ):
        self.payload = payload or {
            "response": "ok"
        }

    def raise_for_status(
        self
    ):
        return None

    def json(
        self
    ):
        return self.payload


class OllamaProviderTest(unittest.TestCase):

    def setUp(self):
        # El proveedor escribe logs/ en el directorio actual: se aísla en una carpeta temporal.
        previous_cwd = os.getcwd()
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.addCleanup(os.chdir, previous_cwd)
        os.chdir(temp_dir.name)

    def test_generate_omits_request_timeout(self):
        with patch(
            "app.providers.ollama_provider.requests.post",
            return_value=FakeResponse()
        ) as post_mock:
            response = OllamaProvider("fake-model").generate(
                "prompt"
            )

        self.assertEqual(
            "ok",
            response
        )
        self.assertNotIn(
            "timeout",
            post_mock.call_args.kwargs,
        )

    def test_timeout_becomes_contextual_external_service_error(self):
        with patch(
            "app.providers.ollama_provider.requests.post",
            side_effect=requests.Timeout(),
        ):
            with self.assertRaises(OperationalError) as context:
                OllamaProvider("fake-model").generate("prompt")

        self.assertEqual("EXTERNAL_SERVICE", context.exception.context.family)
        self.assertEqual("ollama", context.exception.context.technical_metadata["service"])
        self.assertEqual("fake-model", context.exception.context.technical_metadata["model"])
        self.assertIsInstance(context.exception.__cause__, OllamaRequestError)
        self.assertIsInstance(context.exception.__cause__.__cause__, requests.Timeout)

    def test_generate_result_separates_content_and_metadata(self):
        response = FakeResponse(
            {
                "model": "fake-model:latest",
                "created_at": "2026-09-19T00:00:00Z",
                "response": "contenido",
                "thinking": "razonamiento separado",
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 12,
                "eval_count": 7,
                "total_duration": 100,
                "load_duration": 20,
                "prompt_eval_duration": 30,
                "eval_duration": 40,
            }
        )

        with patch(
            "app.providers.ollama_provider.requests.post",
            return_value=response,
        ):
            result = OllamaProvider("fake-model").generate_result(
                "prompt"
            )

        self.assertEqual("contenido", result.content)
        self.assertEqual("fake-model", result.metadata.requested_model)
        self.assertEqual("fake-model:latest", result.metadata.response_model)
        self.assertEqual("2026-09-19T00:00:00Z", result.metadata.created_at)
        self.assertTrue(result.metadata.done)
        self.assertEqual("stop", result.metadata.done_reason)
        self.assertEqual(6, result.metadata.prompt_length)
        self.assertEqual(9, result.metadata.content_length)
        self.assertEqual(12, result.metadata.prompt_eval_count)
        self.assertEqual(7, result.metadata.eval_count)
        self.assertEqual(len("razonamiento separado"), result.metadata.thinking_length)
        self.assertIsNotNone(result.metadata.thinking_sha256)

    def test_metadata_tolerates_absent_optional_ollama_fields(self):
        with patch(
            "app.providers.ollama_provider.requests.post",
            return_value=FakeResponse({"response": "ok"}),
        ):
            result = OllamaProvider("fake-model").generate_result("prompt")

        self.assertEqual("ok", result.content)
        self.assertIsNone(result.metadata.response_model)
        self.assertIsNone(result.metadata.done)
        self.assertIsNone(result.metadata.done_reason)
        self.assertIsNone(result.metadata.thinking_length)
        self.assertIsNone(result.metadata.eval_count)

    def test_policy_serializes_only_explicit_per_call_fields(self):
        policy = OllamaRequestPolicy(
            format="json",
            think=False,
            options={"seed": 7},
            timeout=3.0,
        )
        with patch(
            "app.providers.ollama_provider.requests.post",
            return_value=FakeResponse(),
        ) as post_mock:
            OllamaProvider("fake-model").generate_result(
                "prompt",
                policy=policy,
            )

        self.assertEqual(
            {
                "model": "fake-model",
                "prompt": "prompt",
                "stream": False,
                "format": "json",
                "think": False,
                "options": {"seed": 7},
            },
            post_mock.call_args.kwargs["json"],
        )
        self.assertEqual(3.0, post_mock.call_args.kwargs["timeout"])

    def test_schema_format_serializes_as_a_payload_mapping(self):
        schema = {
            "type": "array",
            "items": {
                "type": "object",
            },
        }
        with patch(
            "app.providers.ollama_provider.requests.post",
            return_value=FakeResponse(),
        ) as post_mock:
            OllamaProvider("fake-model").generate_result(
                "prompt",
                policy=OllamaRequestPolicy(
                    format=schema,
                    think=False,
                ),
            )

        self.assertEqual(
            schema,
            post_mock.call_args.kwargs["json"]["format"],
        )
        self.assertFalse(post_mock.call_args.kwargs["json"]["think"])
        json.dumps(post_mock.call_args.kwargs["json"])

    def test_policies_do_not_contaminate_consecutive_calls(self):
        provider = OllamaProvider("fake-model")
        with patch(
            "app.providers.ollama_provider.requests.post",
            return_value=FakeResponse(),
        ) as post_mock:
            provider.generate_result(
                "first",
                policy=OllamaRequestPolicy(think=False),
            )
            provider.generate_result("second")

        first_payload = post_mock.call_args_list[0].kwargs["json"]
        second_payload = post_mock.call_args_list[1].kwargs["json"]
        self.assertFalse(first_payload["think"])
        self.assertNotIn("think", second_payload)
        self.assertNotIn("format", second_payload)
        self.assertNotIn("options", second_payload)

    def test_script_builder_keeps_the_legacy_free_text_payload(self):
        with patch(
            "app.providers.ollama_provider.requests.post",
            return_value=FakeResponse({"response": "Guion libre válido."}),
        ) as post_mock:
            script = ScriptBuilder(
                {"model": "fake-model"},
                max_attempts=1,
            ).build("Prompt libre")

        self.assertEqual("Guion libre válido.", script)
        self.assertEqual(
            {
                "model": "fake-model",
                "prompt": "Prompt libre",
                "stream": False,
            },
            post_mock.call_args.kwargs["json"],
        )
        self.assertNotIn("timeout", post_mock.call_args.kwargs)

    def test_policy_mapping_is_immutable_snapshot(self):
        options = {"seed": 7}
        policy = OllamaRequestPolicy(options=options)
        options["seed"] = 8

        self.assertEqual(7, policy.options["seed"])
        with self.assertRaises(TypeError):
            policy.options["seed"] = 9

    def test_http_error_preserves_provider_error_as_cause(self):
        with patch(
            "app.providers.ollama_provider.requests.post",
            return_value=_HttpErrorResponse(),
        ):
            with self.assertRaises(OperationalError) as context:
                OllamaProvider("fake-model").generate("prompt")

        self.assertIsInstance(context.exception.__cause__, OllamaRequestError)
        self.assertIsInstance(context.exception.__cause__.__cause__, requests.HTTPError)

    def test_existing_operational_error_is_not_wrapped_again(self):
        expected = OperationalError(
            ErrorContext(
                family="EXTERNAL_SERVICE",
                severity=ErrorSeverity.FATAL_OPERATIONAL,
                user_message="Fallo previo.",
                exit_kind=ExitKind.OPERATIONAL_ERROR,
            )
        )

        class PrecontextualizedProvider(OllamaProvider):
            def _generate_result(self, *, prompt, policy):
                raise expected

        with self.assertRaises(OperationalError) as context:
            PrecontextualizedProvider("fake-model").generate("prompt")

        self.assertIs(expected, context.exception)


class OllamaConfiguredCallsTest(unittest.TestCase):
    """keep_alive, model, think and options declared in config/ai.json (I2)."""

    def setUp(self):
        previous_cwd = os.getcwd()
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.addCleanup(os.chdir, previous_cwd)
        os.chdir(temp_dir.name)

    def _post(self, response=None):
        return patch(
            "app.providers.ollama_provider.requests.post",
            return_value=FakeResponse(response),
        )

    def test_keep_alive_zero_is_sent_to_free_the_gpu(self):
        with self._post() as post_mock:
            OllamaProvider("fake-model", keep_alive=0).generate("prompt")

        self.assertEqual(0, post_mock.call_args.kwargs["json"]["keep_alive"])

    def test_undeclared_keep_alive_is_not_sent(self):
        with self._post() as post_mock:
            OllamaProvider("fake-model").generate("prompt")

        self.assertNotIn("keep_alive", post_mock.call_args.kwargs["json"])

    def test_default_script_provider_uses_model_and_keep_alive(self):
        provider = ScriptBuilder(
            {"model": "m", "keep_alive": "5m", "script": {"model": "t"}},
        ).provider

        self.assertEqual("t", provider.model)
        self.assertEqual("5m", provider.keep_alive)

    def test_script_builder_sends_the_script_section(self):
        ai_config = {
            "model": "global-model",
            "keep_alive": 0,
            "script": {
                "model": "script-model",
                "think": False,
                "options": {"num_ctx": 8192},
            },
        }
        with self._post({"response": "Guion libre válido."}) as post_mock:
            # The test runs in a temporary folder: prompts/ is the repository one.
            builder = ScriptBuilder(
                ai_config,
                max_attempts=1,
                prompts=PromptLibrary(REPOSITORY_PROMPTS),
            )
            builder.build("Prompt libre")
            builder.adjust(
                "Prompt libre",
                length=_length_budget(),
                previous_script="Guion anterior más largo de lo pedido.",
                measured_seconds=40.0,
            )

        self.assertEqual("script-model", builder.model)
        for call in post_mock.call_args_list:
            payload = call.kwargs["json"]
            self.assertEqual("script-model", payload["model"])
            self.assertEqual(0, payload["keep_alive"])
            self.assertIs(False, payload["think"])
            self.assertEqual({"num_ctx": 8192}, payload["options"])
            self.assertNotIn("format", payload)
        self.assertEqual(2, len(post_mock.call_args_list))

    def test_script_think_true_is_sent_and_null_is_not(self):
        for think, expected in ((True, True), (None, "absent")):
            with self.subTest(think=think):
                with self._post({"response": "Guion libre válido."}) as post_mock:
                    ScriptBuilder(
                        {"model": "m", "script": {"think": think}},
                        max_attempts=1,
                    ).build("Prompt libre")
                payload = post_mock.call_args.kwargs["json"]
                if expected == "absent":
                    self.assertNotIn("think", payload)
                else:
                    self.assertIs(True, payload["think"])

    def test_script_section_does_not_reach_other_tasks(self):
        settings = ollama_call_settings(
            {"model": "m", "script": {"think": True, "options": {"num_ctx": 1}}},
            "storyboard",
        )

        self.assertIsNone(settings.think)
        self.assertIsNone(settings.options)


def _length_budget():
    from app.core.script_length import (
        DurationMargin,
        ScriptLengthBudget,
        SpeechPacing,
    )

    return ScriptLengthBudget.for_duration(
        30,
        SpeechPacing(letters_per_second=13.0, words_per_second=2.5),
        DurationMargin(below=0.10, above=None),
    )


class _HttpErrorResponse(FakeResponse):

    def raise_for_status(self):
        raise requests.HTTPError("500 Server Error")


if __name__ == "__main__":
    unittest.main()
