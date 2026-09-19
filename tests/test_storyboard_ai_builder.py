import unittest

from app.modules.storyboard.storyboard_ai_builder import (
    StoryboardAIBuilder,
    StoryboardRequestPolicy,
    storyboard_response_schema,
)
from app.providers.ollama_provider import (
    OllamaProviderResult,
    OllamaRequestPolicy,
    OllamaResponseMetadata,
)


class FakeProvider:

    def __init__(self, content):
        self.content = content
        self.calls = []

    def generate_result(self, prompt, *, policy=None):
        self.calls.append((prompt, policy))
        return OllamaProviderResult(
            content=self.content,
            metadata=OllamaResponseMetadata(
                requested_model="fake-model",
                response_model=None,
                created_at=None,
                policy=policy,
                done=None,
                done_reason=None,
                prompt_length=len(prompt),
                content_length=len(self.content),
                prompt_sha256="prompt-hash",
                content_sha256="content-hash",
                prompt_eval_count=None,
                eval_count=None,
                total_duration=None,
                load_duration=None,
                prompt_eval_duration=None,
                eval_duration=None,
                thinking_length=None,
                thinking_sha256=None,
            ),
        )


class StoryboardAIBuilderTest(unittest.TestCase):

    def test_default_policy_uses_verified_structured_output_intent(self):
        provider = FakeProvider(" [{\"scene\": 1}] ")
        builder = StoryboardAIBuilder(
            {"model": "fake-model"},
            provider=provider,
        )

        response = builder.build("prompt")

        self.assertEqual("[{\"scene\": 1}]", response)
        self.assertIsInstance(provider.calls[0][1], OllamaRequestPolicy)
        self.assertEqual(storyboard_response_schema(), provider.calls[0][1].format)
        self.assertFalse(provider.calls[0][1].think)
        self.assertIsNone(provider.calls[0][1].options)
        self.assertEqual(" [{\"scene\": 1}] ", builder.last_result.content)

    def test_storyboard_policy_is_scoped_to_its_call(self):
        provider = FakeProvider("contenido")
        policy = StoryboardRequestPolicy()
        builder = StoryboardAIBuilder(
            {"model": "fake-model"},
            provider=provider,
            request_policy=policy,
        )

        builder.build("prompt")

        self.assertIs(policy.ollama_policy, provider.calls[0][1])
        self.assertEqual(storyboard_response_schema(), provider.calls[0][1].format)
        self.assertFalse(provider.calls[0][1].think)

    def test_empty_content_remains_a_storyboard_error(self):
        builder = StoryboardAIBuilder(
            {"model": "fake-model"},
            provider=FakeProvider("  "),
        )

        with self.assertRaisesRegex(ValueError, "respuesta vacía"):
            builder.build("prompt")


if __name__ == "__main__":
    unittest.main()
