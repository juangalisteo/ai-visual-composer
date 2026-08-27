import unittest
from unittest.mock import patch

from app.providers.ollama_provider import OllamaProvider


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

    def test_generate_preserves_original_request_without_timeout(self):
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
            post_mock.call_args.kwargs
        )


if __name__ == "__main__":
    unittest.main()
