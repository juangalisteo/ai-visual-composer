import tempfile
import unittest
from pathlib import Path

from app.core.prompt_engine import PromptEngine
from app.core.start import cargar_o_generar_guion
from app.modules.script import (
    InvalidScriptOutputError,
    ScriptBuilder,
    ScriptGenerationMetadata,
    ScriptGenerationResult,
    ScriptOutputValidator,
)
from app.modules.script.validator import count_script_words


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
                target_words=26,
                recommended_min_words=23,
                recommended_max_words=28,
                actual_words=9,
                deviation_percentage=-65.38461538461539,
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
        self.assertEqual(
            result.metadata.target_words,
            26,
        )

    def test_valid_response_inside_reference_range_passes_contract(self):
        report = ScriptOutputValidator().validate(
            _words(10)
        )

        self.assertTrue(
            report.valid
        )

    def test_response_above_reference_range_passes_contract(self):
        report = ScriptOutputValidator().validate(
            _words(40)
        )

        self.assertTrue(
            report.valid
        )

    def test_response_far_above_reference_range_passes_contract(self):
        report = ScriptOutputValidator().validate(
            _words(400)
        )

        self.assertTrue(
            report.valid
        )

    def test_response_below_reference_range_passes_contract(self):
        report = ScriptOutputValidator().validate(
            _words(2)
        )

        self.assertTrue(
            report.valid
        )

    def test_response_far_below_reference_range_but_not_empty_passes_contract(self):
        report = ScriptOutputValidator().validate(
            "Silencio."
        )

        self.assertTrue(
            report.valid
        )

    def test_empty_response_is_rejected(self):
        self.assertInvalid(
            "",
            "empty_script",
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

    def test_markdown_is_rejected(self):
        self.assertInvalid(
            "# Guion\nLa conciencia despierta lentamente.",
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

    def test_builder_does_not_retry_only_because_response_is_long(self):
        provider = FakeProvider(
            (
                _words(80),
            )
        )

        result = ScriptBuilder(
            {
                "model": "test-model"
            },
            provider=provider,
            max_attempts=2,
        ).generate_result(
            _prompt_with_reference()
        )

        self.assertEqual(
            len(provider.prompts),
            1,
        )
        self.assertEqual(
            result.word_count,
            80,
        )
        self.assertEqual(
            result.script,
            _words(80),
        )

    def test_builder_does_not_retry_only_because_response_is_short(self):
        provider = FakeProvider(
            (
                "Silencio.",
            )
        )

        result = ScriptBuilder(
            {
                "model": "test-model"
            },
            provider=provider,
            max_attempts=2,
        ).generate_result(
            _prompt_with_reference()
        )

        self.assertEqual(
            len(provider.prompts),
            1,
        )
        self.assertEqual(
            result.script,
            "Silencio.",
        )

    def test_builder_retries_once_for_structural_error(self):
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
            _prompt_with_reference()
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
            "debe contener entre",
            provider.prompts[1].lower(),
        )
        self.assertNotIn(
            "Objetivo exacto",
            provider.prompts[1],
        )

    def test_builder_raises_structured_error_after_structural_failures(self):
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
                _prompt_with_reference()
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

    def test_count_script_words_is_deterministic(self):
        text = "La conciencia despierta, respira y avanza."

        self.assertEqual(
            count_script_words(text),
            6,
        )
        self.assertEqual(
            count_script_words(text),
            count_script_words(text),
        )

    def test_length_metadata_is_calculated(self):
        provider = FakeProvider(
            (
                _words(13),
            )
        )

        result = ScriptBuilder(
            {
                "model": "test-model"
            },
            provider=provider,
        ).generate_result(
            _prompt_with_reference(
                minimum=9,
                maximum=11,
                target=10,
            )
        )

        self.assertEqual(
            result.metadata.recommended_min_words,
            9,
        )
        self.assertEqual(
            result.metadata.recommended_max_words,
            11,
        )
        self.assertEqual(
            result.metadata.target_words,
            10,
        )
        self.assertEqual(
            result.metadata.actual_words,
            13,
        )
        self.assertEqual(
            result.word_count,
            13,
        )
        self.assertAlmostEqual(
            result.metadata.deviation_percentage,
            30.0,
        )

    def test_prompt_engine_uses_orientative_language(self):
        prompt = PromptEngine().build_script_prompt(
            "conciencia",
            {
                "tone": "modo_conciencia",
                "platform": "youtube",
                "format": "horizontal",
                "duration": 10,
            },
        )

        self.assertIn(
            "Extensión orientativa",
            prompt,
        )
        self.assertIn(
            "objetivo aproximado de 26 palabras",
            prompt,
        )
        self.assertIn(
            "Puedes utilizar más o menos palabras",
            prompt,
        )
        self.assertNotIn(
            "No superes el máximo",
            prompt,
        )
        self.assertNotIn(
            "será inválida",
            prompt,
        )
        self.assertNotIn(
            "sera invalida",
            prompt,
        )
        self.assertNotIn(
            "debe contener entre",
            prompt.lower(),
        )

    def test_no_truncation_slicing_or_automatic_cut(self):
        long_script = " ".join(
            f"palabra{i}"
            for i in range(
                1,
                121
            )
        )
        provider = FakeProvider(
            (
                long_script,
            )
        )

        result = ScriptBuilder(
            {
                "model": "test-model"
            },
            provider=provider,
        ).generate_result(
            _prompt_with_reference()
        )

        self.assertEqual(
            result.script,
            long_script,
        )
        self.assertEqual(
            result.word_count,
            120,
        )

    def test_long_script_can_be_written_to_script_file(self):
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
            long_script = _words(80)

            script = cargar_o_generar_guion(
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
                            long_script,
                        )
                    ),
                ),
            )

            self.assertEqual(
                script,
                long_script,
            )
            self.assertEqual(
                output_script.read_text(
                    encoding="utf-8"
                ),
                long_script,
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
    ):
        report = ScriptOutputValidator().validate(
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


def _words(
    count
):
    return " ".join(
        f"palabra{i}"
        for i in range(
            1,
            count + 1
        )
    )


def _prompt_with_reference(
    *,
    minimum=23,
    maximum=28,
    target=26,
):
    return (
        "TEMA:\n"
        "conciencia\n\n"
        "DURACIÓN:\n"
        f"- Extensión orientativa: aproximadamente entre {minimum} "
        f"y {maximum} palabras, con un objetivo aproximado de "
        f"{target} palabras.\n\n"
        "SALIDA OBLIGATORIA:\n"
        "- Devuelve únicamente el guion final."
    )


if __name__ == "__main__":
    unittest.main()
