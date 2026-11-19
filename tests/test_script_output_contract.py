import tempfile
import unittest
from pathlib import Path

from app.core.prompt_engine import PromptEngine
from app.core.script_length import ScriptLengthBudget, SpeechPacing
from app.modules.script import (
    InvalidScriptOutputError,
    ScriptAdjustment,
    ScriptBuilder,
    ScriptGenerationMetadata,
    ScriptGenerationResult,
    ScriptOutputValidator,
    ScriptPreparationService,
)
from app.modules.script.validator import count_script_words


# Every fake word is "palabraN": 7 letters. These pacings make letters and
# words agree, so a test can reason in words: 26 words last 10 s.
TEST_PACING = SpeechPacing(letters_per_second=18.2, words_per_second=2.6)
SHORT_WORD_PACING = SpeechPacing(letters_per_second=17.5, words_per_second=2.5)


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

    def test_builder_retries_when_response_exceeds_duration_budget(self):
        provider = FakeProvider(
            (
                _words(80),
                _words(26),
            )
        )

        result = ScriptBuilder(
            {
                "model": "test-model"
            },
            provider=provider,
            max_attempts=2,
        ).generate_result(
            _real_request().prompt,
            length=_real_request().length,
        )

        self.assertEqual(
            len(provider.prompts),
            2,
        )
        self.assertEqual(
            result.word_count,
            26,
        )
        self.assertEqual(
            result.script,
            _words(26),
        )

    def test_builder_retries_when_response_is_shorter_than_duration_budget(self):
        provider = FakeProvider(
            (
                "Silencio.",
                _words(26),
            )
        )

        result = ScriptBuilder(
            {
                "model": "test-model"
            },
            provider=provider,
            max_attempts=2,
        ).generate_result(
            _real_request().prompt,
            length=_real_request().length,
        )

        self.assertEqual(
            len(provider.prompts),
            2,
        )
        self.assertEqual(
            result.script,
            _words(26),
        )

    def test_builder_retries_once_for_structural_error(self):
        provider = FakeProvider(
            (
                "**Answer:**\nLa conciencia despierta lentamente.",
                _words(26),
            )
        )

        result = ScriptBuilder(
            {
                "model": "test-model"
            },
            provider=provider,
            max_attempts=2,
        ).generate_result(
            _real_request().prompt,
            length=_real_request().length,
        )

        self.assertEqual(
            result.script,
            _words(26),
        )
        self.assertEqual(
            result.metadata.attempt,
            2,
        )
        self.assertIn(
            "La respuesta anterior incumple el formato requerido.",
            provider.prompts[1],
        )
        self.assertIn(
            "debe contener entre",
            provider.prompts[1].lower(),
        )
        self.assertNotIn(
            "Objetivo exacto",
            provider.prompts[1],
        )
        self.assertTrue(
            provider.prompts[1].startswith(_real_request().prompt)
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
                _real_request().prompt,
                length=_real_request().length,
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
                _words(10),
            )
        )

        result = ScriptBuilder(
            {
                "model": "test-model"
            },
            provider=provider,
        ).generate_result(
            "TEMA:\nconciencia",
            length=ScriptLengthBudget(
                duration_seconds=4,
                target_words=10,
                min_words=9,
                max_words=11,
                pacing=SHORT_WORD_PACING,
            ),
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
            10,
        )
        self.assertEqual(
            result.word_count,
            10,
        )
        self.assertAlmostEqual(
            result.metadata.deviation_percentage,
            0.0,
        )

    def test_prompt_engine_makes_duration_budget_explicit(self):
        request = _real_request()
        prompt = request.prompt

        self.assertEqual(
            (
                request.length.min_words,
                request.length.max_words,
                request.length.target_words,
            ),
            (23, 29, 26),
        )
        self.assertIn(
            "entre 23 y 29 palabras",
            prompt,
        )

        self.assertIn(
            "Extensión requerida",
            prompt,
        )
        self.assertIn(
            "objetivo de 26 palabras",
            prompt,
        )
        self.assertIn(
            "presupuesto temporal",
            prompt,
        )
        self.assertNotIn(
            "Puedes utilizar",
            prompt,
        )
        self.assertNotIn(
            "orientativa",
            prompt.lower(),
        )

    def test_out_of_range_script_is_kept_whole_when_no_attempt_fits(self):
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
            {"model": "test-model"},
            provider=provider,
            max_attempts=1,
        ).generate_result(
            _real_request().prompt,
            length=_real_request().length,
        )

        self.assertEqual(result.script, long_script)
        self.assertEqual(result.word_count, 120)

    def test_closest_script_is_kept_when_every_attempt_is_out_of_range(self):
        provider = FakeProvider(
            (
                _words(80),
                _words(40),
            )
        )

        result = ScriptBuilder(
            {"model": "test-model"},
            provider=provider,
            max_attempts=2,
        ).generate_result(
            _real_request().prompt,
            length=_real_request().length,
        )

        self.assertEqual(len(provider.prompts), 2)
        self.assertEqual(result.script, _words(40))
        self.assertEqual(result.metadata.attempt, 2)

    def test_length_retry_keeps_the_real_prompt_and_shows_the_previous_script(self):
        request = _real_request()
        provider = FakeProvider(
            (
                _words(80),
                _words(26),
            )
        )

        ScriptBuilder(
            {"model": "test-model"},
            provider=provider,
            max_attempts=2,
        ).generate_result(
            request.prompt,
            length=request.length,
        )

        retry = provider.prompts[1]
        self.assertTrue(retry.startswith(request.prompt))
        self.assertIn("IDENTIDAD Y TONO", retry)
        self.assertIn("Tu respuesta anterior tenía 80 palabras", retry)
        self.assertIn(
            f"entre {request.length.min_words} y {request.length.max_words} palabras",
            retry,
        )
        self.assertTrue(retry.endswith(_words(80)))

    def test_duration_is_checked_by_letters_not_by_word_count(self):
        length = ScriptLengthBudget.for_duration(
            10,
            SpeechPacing(letters_per_second=13.0, words_per_second=2.6),
        )
        short_words = " ".join(["calma"] * 26)
        long_words = " ".join(["consciencia"] * 26)
        provider = FakeProvider((long_words, short_words))

        result = ScriptBuilder(
            {"model": "test-model"},
            provider=provider,
            max_attempts=2,
        ).generate_result(
            "TEMA:\nconciencia",
            length=length,
        )

        self.assertTrue(length.min_words <= 26 <= length.max_words)
        self.assertEqual(len(provider.prompts), 2)
        self.assertEqual(result.script, short_words)
        self.assertIn("duraría unos 22,0 segundos", provider.prompts[1])
        self.assertIn("entre 11 y 13 palabras", provider.prompts[1])

    def test_prompt_engine_sizes_the_script_with_the_voice_pacing(self):
        profile = {
            "tone": "modo_conciencia",
            "format": "vertical",
            "duration": 30,
        }
        slower = PromptEngine().build_script_request(
            "conciencia",
            profile,
            SpeechPacing(letters_per_second=13.14, words_per_second=2.53),
        )
        faster = PromptEngine().build_script_request(
            "conciencia",
            profile,
            SpeechPacing(letters_per_second=13.69, words_per_second=2.64),
        )

        self.assertEqual(slower.length.target_words, 76)
        self.assertEqual(faster.length.target_words, 79)
        self.assertIn("con objetivo de 76 palabras", slower.prompt)
        self.assertIn("con objetivo de 79 palabras", faster.prompt)

    def test_prompt_engine_requires_the_voice_pacing(self):
        with self.assertRaises(TypeError):
            PromptEngine().build_script_request(
                "conciencia",
                {"tone": "modo_conciencia", "format": "vertical", "duration": 30},
                None,
            )

    def test_length_range_comes_from_data_and_is_never_read_from_the_prompt_text(self):
        old_wording = (
            "TEMA:\nconciencia\n\nDURACIÓN:\n"
            "- Extensión orientativa: aproximadamente entre 23 y 28 palabras, "
            "con un objetivo aproximado de 26 palabras.\n"
            "- Extensión requerida: entre 23 y 28 palabras, con objetivo de "
            "26 palabras."
        )
        free_provider = FakeProvider((_words(80), _words(26)))

        free_result = ScriptBuilder(
            {"model": "test-model"},
            provider=free_provider,
            max_attempts=2,
        ).generate_result(old_wording)

        self.assertEqual(len(free_provider.prompts), 1)
        self.assertEqual(free_result.word_count, 80)

        data_provider = FakeProvider((_words(80), _words(10)))
        data_result = ScriptBuilder(
            {"model": "test-model"},
            provider=data_provider,
            max_attempts=2,
        ).generate_result(
            "TEMA:\nconciencia",
            length=ScriptLengthBudget(
                duration_seconds=4,
                target_words=10,
                min_words=9,
                max_words=11,
                pacing=SHORT_WORD_PACING,
            ),
        )

        self.assertEqual(len(data_provider.prompts), 2)
        self.assertEqual(data_result.word_count, 10)

    def test_duration_compliant_script_is_written_to_script_file(self):
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
            long_script = _words(26)

            script = ScriptPreparationService(
                script_builder_factory=lambda ai_config: ScriptBuilder(
                    ai_config,
                    provider=FakeProvider(
                        (
                            long_script,
                        )
                    ),
                ),
            ).prepare(
                builders={
                    "script": True
                },
                ai_config={
                    "model": "test-model"
                },
                profile={
                    "tone": "modo_conciencia",
                    "format": "horizontal",
                    "duration": 10,
                },
                input_script_path=root / "missing_manual.txt",
                input_topic_path=input_topic,
                output_script_path=output_script,
                voice_pacing=TEST_PACING,
            ).text

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

    def test_adjust_asks_once_with_the_measured_duration_and_the_previous_script(self):
        request = _real_request()
        provider = FakeProvider(
            (
                f"  {_words(26)}  ",
                _words(26),
            )
        )

        script = ScriptBuilder(
            {"model": "test-model"},
            provider=provider,
            max_attempts=2,
        ).adjust(
            request.prompt,
            length=request.length,
            previous_script=_words(80),
            measured_seconds=30.8,
        )

        self.assertEqual(script, _words(26))
        self.assertEqual(len(provider.prompts), 1)
        adjustment = provider.prompts[0]
        self.assertTrue(adjustment.startswith(request.prompt))
        self.assertIn(
            "La voz leyó tu guion anterior (80 palabras) en 30,8 segundos "
            "y debe durar 10,0.",
            adjustment,
        )
        self.assertIn("Reescríbela más corta: entre 23 y 29 palabras", adjustment)
        self.assertTrue(adjustment.endswith(_words(80)))

    def test_adjust_rescales_the_words_with_the_measured_duration(self):
        request = _real_request()
        provider = FakeProvider((_words(30),))

        ScriptBuilder(
            {"model": "test-model"},
            provider=provider,
        ).adjust(
            request.prompt,
            length=request.length,
            previous_script=_words(26),
            measured_seconds=13.0,
        )

        self.assertIn(
            "Reescríbela más corta: entre 18 y 22 palabras, con objetivo de "
            "20 palabras.",
            provider.prompts[0],
        )

    def test_malformed_adjustment_raises_after_a_single_request(self):
        provider = FakeProvider(
            (
                "**Answer:**\nLa conciencia despierta.",
                _words(26),
            )
        )

        with self.assertRaises(InvalidScriptOutputError):
            ScriptBuilder(
                {"model": "test-model"},
                provider=provider,
                max_attempts=2,
            ).adjust(
                _real_request().prompt,
                length=_real_request().length,
                previous_script=_words(80),
                measured_seconds=30.8,
            )

        self.assertEqual(len(provider.prompts), 1)

    def test_service_adjustment_rewrites_the_topic_script_at_the_given_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_topic = root / "tema.txt"
            input_topic.write_text("conciencia", encoding="utf-8")
            candidate = root / "guion_ajuste.txt"
            provider = FakeProvider((_words(26),))

            prepared = ScriptPreparationService(
                script_builder_factory=lambda ai_config: ScriptBuilder(
                    ai_config,
                    provider=provider,
                ),
            ).prepare(
                builders={"script": True},
                ai_config={"model": "test-model"},
                profile={
                    "tone": "modo_conciencia",
                    "format": "horizontal",
                    "duration": 10,
                },
                input_script_path=root / "missing_manual.txt",
                input_topic_path=input_topic,
                output_script_path=candidate,
                voice_pacing=TEST_PACING,
                adjustment=ScriptAdjustment(
                    previous_script=_words(80),
                    measured_seconds=30.8,
                ),
            )

            self.assertEqual(prepared.text, _words(26))
            self.assertEqual(prepared.source, "generated")
            self.assertEqual(candidate.read_text(encoding="utf-8"), _words(26))
            self.assertEqual(len(provider.prompts), 1)
            self.assertIn("CORRECCIÓN DE EXTENSIÓN", provider.prompts[0])
            self.assertIn("TEMA:\nconciencia", provider.prompts[0])

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
                ScriptPreparationService(
                    script_builder_factory=lambda ai_config: ScriptBuilder(
                        ai_config,
                        provider=FakeProvider(
                            (
                                "**Answer:**\nLa conciencia despierta.",
                                "Word count: 4\nLa conciencia despierta.",
                            )
                        ),
                    ),
                ).prepare(
                    builders={
                        "script": True
                    },
                    ai_config={
                        "model": "test-model"
                    },
                    profile={
                        "tone": "modo_conciencia",
                        "format": "horizontal",
                        "duration": 10,
                    },
                    input_script_path=root / "missing_manual.txt",
                    input_topic_path=input_topic,
                    output_script_path=output_script,
                    voice_pacing=TEST_PACING,
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


def _real_request(
    duration=10,
):
    """Prompt and budget exactly as PromptEngine builds them for a topic script."""
    return PromptEngine().build_script_request(
        "conciencia",
        {
            "tone": "modo_conciencia",
            "format": "horizontal",
            "duration": duration,
        },
        TEST_PACING,
    )


if __name__ == "__main__":
    unittest.main()
