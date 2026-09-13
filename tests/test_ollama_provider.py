import unittest
from unittest.mock import patch

import requests

from app.providers.ollama_provider import (
    OllamaProvider,
    OllamaRequestError,
)


class FakeResponse:

    def raise_for_status(
        self
    ):
        return None

    def json(
        self
    ):
        return {
            "response": "ok"
        }


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

    def test_timeout_raises_a_clear_error(self):
        with patch(
            "app.providers.ollama_provider.requests.post",
            side_effect=requests.Timeout(),
        ):
            with self.assertRaisesRegex(
                OllamaRequestError,
                "espera de red",
            ):
                OllamaProvider("fake-model").generate("prompt")

    def test_http_error_remains_an_error(self):
        with patch(
            "app.providers.ollama_provider.requests.post",
            return_value=_HttpErrorResponse(),
        ):
            with self.assertRaisesRegex(
                OllamaRequestError,
                "No se pudo conectar",
            ):
                OllamaProvider("fake-model").generate("prompt")


class _HttpErrorResponse(FakeResponse):

    def raise_for_status(self):
        raise requests.HTTPError("500 Server Error")


if __name__ == "__main__":
    unittest.main()
