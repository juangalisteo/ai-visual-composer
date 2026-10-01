import unittest
import json
from unittest.mock import patch

import requests

from app.modules.script.script_builder import ScriptBuilder
from app.providers.ollama_provider import (
    OllamaProvider,
    OllamaRequestError,
    OllamaRequestPolicy,
)
from app.shared.error_context import ErrorContext, ErrorSeverity, ExitKind
from app.shared.operational_error import OperationalError


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


class _HttpErrorResponse(FakeResponse):

    def raise_for_status(self):
        raise requests.HTTPError("500 Server Error")


if __name__ == "__main__":
    unittest.main()
