import tempfile
import unittest
from pathlib import Path

from app.core.start import cargar_o_generar_guion
from app.modules.script import (
    InvalidScriptOutputError,
    ScriptBuilder,
    ScriptGenerationMetadata,
    ScriptGenerationResult,
    ScriptOutputValidator,
)


class FakeProvider:
    def __init__(
        self,
        responses
    ):
        self.responses = list(
            responses
        )
        self.prompts = []

    def generate(
        self,
        prompt
    ):
        self.prompts.append(
            prompt
        )
        if not self.responses:
            return ""
        return self.responses.pop(
            0
        )


class ScriptOutputContractTest(unittest.TestCase):

    def test_script_generation_models_are_structured(self):
        result = ScriptGenerationResult(
            script="La noche respira despacio y abre una puerta interior.",
            word_count=9,
            metadata=ScriptGenerationMetadata(
                model="llama",
                prompt_id="prompt-id",
            ),
        )

        self.assertEqual(
            result.script,
            "La noche respira despacio y abre una puerta interior.",
        )
        self.assertEqual(
            result.metadata.parser_id,
            "script_generation_contract_v1",
        )

    def test_valid_response_passes_contract(self):
        report = ScriptOutputValidator(
            min_words=3,
            max_words=20,
        ).validate(
            "La conciencia despierta lentamente mientras el mundo guarda silencio."
        )

        self.assertTrue(
            report.valid
        )

    def test_answer_heading_is_rejected(self):
        self.assertInvalid(
            "**Answer:**\nLa conciencia despierta lentamente.",
            "markdown_not_allowed",
        )

    def test_word_count_metadata_is_rejected(self):
        self.assertInvalid(
            "La conciencia despierta lentamente.\n\nWord count: 26",
            "word_count_metadata_not_allowed",
        )

    def test_model_explanation_is_rejected(self):
        self.assertInvalid(
            "La conciencia despierta lentamente. This response has 26 words.",
            "model_comment_not_allowed",
        )

    def test_markdown_is_rejected(self):
        self.assertInvalid(
            "# Guion\nLa conciencia despierta lentamente.",
            "markdown_not_allowed",
        )

    def test_json_is_rejected(self):
        self.assertInvalid(
            '{"script": "La conciencia despierta lentamente."}',
            "json_not_allowed",
        )

    def test_xml_is_rejected(self):
        self.assertInvalid(
            "<script>La conciencia despierta lentamente.</script>",
            "xml_not_allowed",
        )

    def test_empty_response_is_rejected(self):
        self.assertInvalid(
            "",
            "empty_script",
        )

    def test_too_long_response_is_rejected(self):
        self.assertInvalid(
            "palabra " * 30,
            "too_long",
            max_words=10,
        )

    def test_too_short_response_is_rejected(self):
        self.assertInvalid(
            "Silencio.",
            "too_short",
            min_words=3,
        )

    def test_mixed_language_model_comment_is_rejected(self):
        self.assertInvalid(
            "La conciencia despierta lentamente. This response follows the rules.",
            "model_comment_not_allowed",
        )

    def test_model_comment_is_rejected(self):
        self.assertInvalid(
            "Aqui tienes el guion solicitado. La conciencia despierta lentamente.",
            "model_comment_not_allowed",
        )

    def test_builder_returns_only_script_field(self):
        provider = FakeProvider(
            (
                "La conciencia despierta lentamente mientras el mundo guarda silencio.",
            )
        )

        script = ScriptBuilder(
            {
                "model": "test-model"
            },
            provider=provider,
        ).build(
            "Longitud aproximada: entre 3 y 20 palabras."
        )

        self.assertEqual(
            script,
            "La conciencia despierta lentamente mientras el mundo guarda silencio.",
        )

    def test_builder_retries_once_with_controlled_prompt(self):
        provider = FakeProvider(
            (
                "**Answer:**\nLa conciencia despierta lentamente.",
                "La conciencia despierta lentamente mientras el mundo guarda silencio.",
            )
        )

        result = ScriptBuilder(
            {
                "model": "test-model"
            },
            provider=provider,
            max_attempts=2,
        ).generate_result(
            "Longitud aproximada: entre 3 y 20 palabras."
        )

        self.assertEqual(
            result.script,
            "La conciencia despierta lentamente mientras el mundo guarda silencio.",
        )
        self.assertEqual(
            result.metadata.attempt,
            2,
        )
        self.assertIn(
            "La respuesta anterior incumple el formato requerido.",
            provider.prompts[1],
        )
        self.assertNotIn(
            "**Answer:**",
            provider.prompts[1],
        )

    def test_builder_raises_structured_error_after_failed_attempts(self):
        provider = FakeProvider(
            (
                "**Answer:**\nLa conciencia despierta.",
                "Word count: 4\nLa conciencia despierta.",
            )
        )

        with self.assertRaises(
            InvalidScriptOutputError
        ) as context:
            ScriptBuilder(
                {
                    "model": "test-model"
                },
                provider=provider,
                max_attempts=2,
            ).build(
                "Longitud aproximada: entre 3 y 20 palabras."
            )

        self.assertEqual(
            context.exception.code,
            "INVALID_SCRIPT_OUTPUT",
        )
        self.assertEqual(
            context.exception.parser_id,
            "script_generation_contract_v1",
        )
        self.assertEqual(
            context.exception.model,
            "test-model",
        )
        self.assertIn(
            "Word count",
            context.exception.original_response,
        )

    def test_invalid_llm_output_is_not_written_for_storyboard(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            input_topic = root / "tema.txt"
            input_topic.write_text(
                "conciencia",
                encoding="utf-8",
            )
            output_script = root / "guion.txt"

            with self.assertRaises(
                InvalidScriptOutputError
            ):
                cargar_o_generar_guion(
                    builders={
                        "script": True
                    },
                    ai_config={
                        "model": "test-model"
                    },
                    profile={
                        "tone": "modo_conciencia",
                        "platform": "youtube",
                        "format": "horizontal",
                        "duration": 10,
                    },
                    input_script_path=root / "missing_manual.txt",
                    input_topic_path=input_topic,
                    output_script_path=output_script,
                    script_builder_factory=lambda ai_config: ScriptBuilder(
                        ai_config,
                        provider=FakeProvider(
                            (
                                "**Answer:**\nLa conciencia despierta.",
                                "Word count: 4\nLa conciencia despierta.",
                            )
                        ),
                    ),
                )

            self.assertFalse(
                output_script.exists()
            )

    def assertInvalid(
        self,
        value,
        expected_reason,
        *,
        min_words=1,
        max_words=20,
    ):
        report = ScriptOutputValidator(
            min_words=min_words,
            max_words=max_words,
        ).validate(
            value
        )
        reasons = {
            issue.reason
            for issue in report.issues
        }

        self.assertFalse(
            report.valid
        )
        self.assertIn(
            expected_reason,
            reasons,
        )


if __name__ == "__main__":
    unittest.main()
