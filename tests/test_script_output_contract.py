import tempfile
import unittest
from pathlib import Path

from app.core.prompt_engine import PromptEngine
from app.core.script_length import (
    DurationMargin,
    ScriptLengthBudget,
    SpeechPacing,
)
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
# The margin of config/ai.json (T0): up to 10 % shorter, no upper limit.
TEST_MARGIN = DurationMargin(below=0.10, above=None)
# A symmetric ±10 % margin, to check that an upper limit still works as data.
SYMMETRIC_MARGIN = DurationMargin(below=0.10, above=0.10)
TEST_AI_CONFIG = {
    "model": "test-model",
    "script": {"duration_margin": {"below": 0.10, "above": None}},
}


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

    def test_builder_accepts_a_long_script_without_a_length_retry(self):
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
            1,
        )
        self.assertEqual(
            result.script,
            _words(80),
        )
        self.assertFalse(result.metadata.length_corrected)

    def test_builder_retries_a_long_script_when_the_margin_has_an_upper_limit(self):
        provider = FakeProvider((_words(80), _words(26)))

        result = ScriptBuilder(
            {"model": "test-model"},
            provider=provider,
            max_attempts=2,
        ).generate_result(
            _real_request().prompt,
            length=_real_request(margin=SYMMETRIC_MARGIN).length,
        )

        self.assertEqual(len(provider.prompts), 2)
        self.assertEqual(result.script, _words(26))
        self.assertIn("palabras como máximo", provider.prompts[1])
        self.assertTrue(result.metadata.length_corrected)

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
        self.assertTrue(result.metadata.length_corrected)

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
            "debe contener al menos 23 palabras",
            provider.prompts[1].lower(),
        )
        self.assertFalse(result.metadata.length_corrected)
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
                margin=SYMMETRIC_MARGIN,
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
            (23, None, 26),
        )
        # I2 asked a strict cap at the target; A1 (advisor, after T0) asks
        # «about N words; better a little more than less»: the margin has no
        # upper limit. The range stays as data.
        self.assertIn(
            "- Extensión: unas 26 palabras; mejor algo más que menos.",
            prompt,
        )
        self.assertNotIn("como máximo", prompt)
        self.assertNotIn(
            "entre 23 y 29 palabras",
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
                _words(5),
                _words(15),
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
        self.assertEqual(result.script, _words(15))
        self.assertEqual(result.metadata.attempt, 2)
        self.assertTrue(result.metadata.length_corrected)

    def test_first_script_kept_as_closest_still_spends_the_length_correction(self):
        provider = FakeProvider((_words(15), _words(5)))

        result = ScriptBuilder(
            {"model": "test-model"},
            provider=provider,
            max_attempts=2,
        ).generate_result(
            _real_request().prompt,
            length=_real_request().length,
        )

        self.assertEqual(result.script, _words(15))
        self.assertEqual(result.metadata.attempt, 1)
        self.assertTrue(result.metadata.length_corrected)

    def test_closeness_is_measured_outside_the_margin(self):
        # 15 words fall 3.2 s short; 80 words are far from 10 s but within a
        # margin without upper limit, so they are the closest.
        provider = FakeProvider((_words(15), _words(80)))

        result = ScriptBuilder(
            {"model": "test-model"},
            provider=provider,
            max_attempts=2,
        ).generate_result(
            _real_request().prompt,
            length=_real_request().length,
        )

        self.assertEqual(result.script, _words(80))

    def test_closest_is_the_one_that_lies_less_outside_the_margin(self):
        # Margin 5–10 s: 34 words sound 13.1 s (3.1 s over the top, 3.1 s
        # from the target) and 8 words 3.1 s (1.9 s under the bottom, 6.9 s
        # from the target). The one less outside the margin is kept.
        provider = FakeProvider((_words(34), _words(8)))

        result = ScriptBuilder(
            {"model": "test-model"},
            provider=provider,
            max_attempts=2,
        ).generate_result(
            "TEMA:\nconciencia",
            length=ScriptLengthBudget.for_duration(
                10,
                TEST_PACING,
                DurationMargin(below=0.5, above=0.0),
            ),
        )

        self.assertEqual(len(provider.prompts), 2)
        self.assertEqual(result.script, _words(8))

    def test_length_retry_keeps_the_real_prompt_and_shows_the_previous_script(self):
        request = _real_request()
        provider = FakeProvider(
            (
                _words(10),
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
        self.assertIn(f"GUION ANTERIOR:\n{_words(10)}\n\n", retry)
        self.assertIn("el guion anterior (10 palabras) duraría unos 3,8", retry)
        self.assertIn(
            f"Reescríbelo con {request.length.target_words} palabras como mínimo",
            retry,
        )
        self.assertLess(
            retry.index("GUION ANTERIOR:"),
            retry.index("CORRECCIÓN DE EXTENSIÓN:"),
        )
        self.assertTrue(retry.endswith("Devuelve únicamente el guion reescrito."))

    def test_duration_is_checked_by_letters_not_by_word_count(self):
        length = ScriptLengthBudget.for_duration(
            10,
            SpeechPacing(letters_per_second=13.0, words_per_second=2.6),
            TEST_MARGIN,
        )
        short_words = " ".join(["sol"] * 26)
        long_words = " ".join(["consciencia"] * 26)
        provider = FakeProvider((short_words, long_words))

        result = ScriptBuilder(
            {"model": "test-model"},
            provider=provider,
            max_attempts=2,
        ).generate_result(
            "TEMA:\nconciencia",
            length=length,
        )

        self.assertTrue(length.min_words <= 26)
        self.assertEqual(len(provider.prompts), 2)
        self.assertEqual(result.script, long_words)
        self.assertIn("duraría unos 6,0 segundos", provider.prompts[1])
        self.assertIn("con 43 palabras como mínimo", provider.prompts[1])

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
            TEST_MARGIN,
        )
        faster = PromptEngine().build_script_request(
            "conciencia",
            profile,
            SpeechPacing(letters_per_second=13.69, words_per_second=2.64),
            TEST_MARGIN,
        )

        self.assertEqual(slower.length.target_words, 76)
        self.assertEqual(faster.length.target_words, 79)
        self.assertIn("unas 76 palabras", slower.prompt)
        self.assertIn("unas 79 palabras", faster.prompt)

    def test_prompt_engine_requires_the_voice_pacing(self):
        with self.assertRaises(TypeError):
            PromptEngine().build_script_request(
                "conciencia",
                {"tone": "modo_conciencia", "format": "vertical", "duration": 30},
                None,
                TEST_MARGIN,
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
                margin=SYMMETRIC_MARGIN,
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
                ai_config=TEST_AI_CONFIG,
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

    def test_generated_prepared_script_says_whether_the_length_was_corrected(self):
        for responses, corrected in (
            ((_words(26),), False),
            ((_words(5), _words(26)), True),
        ):
            with self.subTest(corrected=corrected), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                input_topic = root / "tema.txt"
                input_topic.write_text("conciencia", encoding="utf-8")

                prepared = ScriptPreparationService(
                    script_builder_factory=lambda ai_config: ScriptBuilder(
                        ai_config,
                        provider=FakeProvider(responses),
                    ),
                ).prepare(
                    builders={"script": True},
                    ai_config=TEST_AI_CONFIG,
                    profile={
                        "tone": "modo_conciencia",
                        "format": "horizontal",
                        "duration": 10,
                    },
                    input_script_path=root / "missing_manual.txt",
                    input_topic_path=input_topic,
                    output_script_path=root / "guion.txt",
                    voice_pacing=TEST_PACING,
                )

                self.assertEqual(prepared.text, _words(26))
                self.assertEqual(prepared.metadata.length_corrected, corrected)

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
            "La voz leyó el guion anterior (80 palabras) en 30,8 segundos "
            "y debe durar 10,0.",
            adjustment,
        )
        self.assertIn("Reescríbelo con 26 palabras como máximo", adjustment)
        self.assertIn(f"GUION ANTERIOR:\n{_words(80)}\n\n", adjustment)
        self.assertTrue(adjustment.endswith("Devuelve únicamente el guion reescrito."))

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
            "Reescríbelo con 20 palabras como máximo; es un límite estricto",
            provider.prompts[0],
        )

    def test_adjust_of_a_short_voice_asks_for_a_minimum(self):
        request = _real_request()
        provider = FakeProvider((_words(26),))

        ScriptBuilder(
            {"model": "test-model"},
            provider=provider,
        ).adjust(
            request.prompt,
            length=request.length,
            previous_script=_words(13),
            measured_seconds=5.0,
        )

        self.assertIn(
            "Reescríbelo con 26 palabras como mínimo",
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
                ai_config=TEST_AI_CONFIG,
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
                    ai_config=TEST_AI_CONFIG,
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
    margin=TEST_MARGIN,
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
        margin,
    )


if __name__ == "__main__":
    unittest.main()
