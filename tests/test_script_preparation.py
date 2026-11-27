import tempfile
import unittest
from pathlib import Path

from app.core.script_length import (
    DurationMargin,
    ScriptLengthBudget,
    ScriptRequest,
    SpeechPacing,
)
from app.modules.script import (
    PreparedScript,
    ScriptGenerationMetadata,
    ScriptGenerationResult,
    ScriptOperation,
    ScriptPreparationService,
)
from app.shared.error_context import ErrorSeverity
from app.shared.operational_error import OperationalError


class FakePromptEngine:

    def __init__(
        self
    ):
        self.calls = []
        self.pacings = []
        self.margins = []

    def build_script_request(
        self,
        topic,
        profile,
        pacing,
        margin,
    ):
        self.margins.append(margin)
        self.calls.append(
            (
                topic,
                profile
            )
        )
        self.pacings.append(
            pacing
        )
        return ScriptRequest(
            prompt=f"PROMPT: {topic}",
            length=TEST_LENGTH,
        )


TEST_PACING = SpeechPacing(
    letters_per_second=13.0,
    words_per_second=2.5,
)
TEST_LENGTH = ScriptLengthBudget(
    duration_seconds=10,
    target_words=25,
    min_words=22,
    max_words=None,
    pacing=TEST_PACING,
    margin=DurationMargin(below=0.10, above=None),
)


class FakeScriptBuilder:
    prompts = []
    lengths = []

    def __init__(
        self,
        ai_config
    ):
        self.ai_config = ai_config

    def build_result(
        self,
        prompt,
        *,
        length=None,
    ):
        self.prompts.append(
            prompt
        )
        self.lengths.append(
            length
        )
        script = "Guion generado estable para el pipeline actual."
        return ScriptGenerationResult(
            script=script,
            word_count=7,
            metadata=ScriptGenerationMetadata(length_corrected=True),
        )


class FakePreparationService:

    def __init__(
        self
    ):
        self.calls = []

    def prepare(
        self,
        **kwargs
    ):
        self.calls.append(
            kwargs
        )
        return PreparedScript(
            text="Guion preparado.",
            source="generated",
            path=kwargs["output_script_path"],
            word_count=2
        )


class ScriptPreparationServiceTest(
    unittest.TestCase
):

    def test_manual_script_produces_prepared_script(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            input_script = root / "input" / "guion.txt"
            input_script.parent.mkdir()
            input_script.write_text(
                "Guion manual preparado.",
                encoding="utf-8"
            )
            output_script = root / "output" / "scripts" / "guion.txt"

            prepared_script = ScriptPreparationService(
                prompt_engine=FakePromptEngine(),
                script_builder_factory=FakeScriptBuilder
            ).prepare(
                builders={
                    "script": True
                },
                ai_config={
                    "model": "test-model"
                },
                profile={},
                input_script_path=input_script,
                input_topic_path=root / "input" / "tema.txt",
                output_script_path=output_script,
                source_mode="manual"
            )

            self.assertIsInstance(
                prepared_script,
                PreparedScript
            )
            self.assertEqual(
                "manual",
                prepared_script.source
            )
            self.assertEqual(
                "Guion manual preparado.",
                prepared_script.text
            )
            self.assertEqual(
                output_script,
                prepared_script.path
            )
            self.assertEqual(
                "Guion manual preparado.",
                output_script.read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                3,
                prepared_script.word_count
            )

    def test_generated_script_produces_prepared_script(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            input_topic = root / "input" / "tema.txt"
            input_topic.parent.mkdir()
            input_topic.write_text(
                "conciencia",
                encoding="utf-8"
            )
            output_script = root / "output" / "scripts" / "guion.txt"
            prompt_engine = FakePromptEngine()
            FakeScriptBuilder.prompts = []
            FakeScriptBuilder.lengths = []

            prepared_script = ScriptPreparationService(
                prompt_engine=prompt_engine,
                script_builder_factory=FakeScriptBuilder
            ).prepare(
                builders={
                    "script": True
                },
                ai_config={
                    "model": "test-model",
                    "script": {"duration_margin": {"below": 0.1, "above": None}},
                },
                profile={
                    "duration": 10
                },
                input_script_path=root / "input" / "missing.txt",
                input_topic_path=input_topic,
                output_script_path=output_script,
                voice_pacing=TEST_PACING,
            )

            self.assertEqual(
                "generated",
                prepared_script.source
            )
            self.assertEqual(
                [TEST_PACING],
                prompt_engine.pacings,
            )
            self.assertEqual(
                [DurationMargin(below=0.1, above=None)],
                prompt_engine.margins,
            )
            self.assertTrue(prepared_script.metadata.length_corrected)
            self.assertEqual(
                "Guion generado estable para el pipeline actual.",
                prepared_script.text
            )
            self.assertEqual(
                [
                    "PROMPT: conciencia"
                ],
                FakeScriptBuilder.prompts
            )
            self.assertEqual(
                [TEST_LENGTH],
                FakeScriptBuilder.lengths,
            )
            self.assertEqual(
                [
                    (
                        "conciencia",
                        {
                            "duration": 10
                        }
                    )
                ],
                prompt_engine.calls
            )
            self.assertEqual(
                prepared_script.text,
                output_script.read_text(
                    encoding="utf-8"
                )
            )

    def test_generated_script_without_duration_margin_is_a_config_error(self):
        for ai_config in (
            {"model": "test-model"},
            {"model": "test-model", "script": {"think": False}},
            {"model": "test-model", "script": {"duration_margin": None}},
        ):
            with self.subTest(ai_config=ai_config), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                input_topic = root / "tema.txt"
                input_topic.write_text("conciencia", encoding="utf-8")
                FakeScriptBuilder.prompts = []

                with self.assertRaises(OperationalError) as raised:
                    ScriptPreparationService(
                        prompt_engine=FakePromptEngine(),
                        script_builder_factory=FakeScriptBuilder,
                    ).prepare(
                        builders={"script": True},
                        ai_config=ai_config,
                        profile={"duration": 10},
                        input_script_path=root / "missing.txt",
                        input_topic_path=input_topic,
                        output_script_path=root / "guion.txt",
                        voice_pacing=TEST_PACING,
                    )

                context = raised.exception.context
                self.assertEqual(context.family, "CONFIG")
                self.assertEqual(context.resource, "config/ai.json")
                self.assertIn("config/ai.json", context.user_message)
                self.assertIn("script.duration_margin", context.user_message)
                self.assertEqual(FakeScriptBuilder.prompts, [])
                self.assertFalse((root / "guion.txt").exists())

    def test_generated_source_ignores_existing_manual_script(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            input_dir = root / "input"
            input_dir.mkdir()
            input_script = input_dir / "guion.txt"
            input_topic = input_dir / "tema.txt"
            input_script.write_text(
                "Guion manual que Imagen no debe consumir.",
                encoding="utf-8"
            )
            input_topic.write_text(
                "conciencia",
                encoding="utf-8"
            )
            output_script = root / "output" / "scripts" / "guion.txt"
            prompt_engine = FakePromptEngine()
            FakeScriptBuilder.prompts = []

            prepared_script = ScriptPreparationService(
                prompt_engine=prompt_engine,
                script_builder_factory=FakeScriptBuilder
            ).prepare(
                builders={
                    "script": True
                },
                ai_config={
                    "model": "test-model",
                    "script": {"duration_margin": {"below": 0.1, "above": None}},
                },
                profile={
                    "duration": 10
                },
                input_script_path=input_script,
                input_topic_path=input_topic,
                output_script_path=output_script,
                source_mode="generated"
            )

            self.assertEqual(
                "generated",
                prepared_script.source
            )
            self.assertEqual(
                "Guion generado estable para el pipeline actual.",
                prepared_script.text
            )
            self.assertNotEqual(
                input_script.read_text(
                    encoding="utf-8"
                ),
                prepared_script.text
            )
            self.assertEqual(
                [
                    (
                        "conciencia",
                        {
                            "duration": 10
                        }
                    )
                ],
                prompt_engine.calls
            )
            self.assertEqual(
                prepared_script.text,
                output_script.read_text(
                    encoding="utf-8"
                )
            )

    def test_manual_source_does_not_fallback_to_topic_generation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            input_topic = root / "input" / "tema.txt"
            input_topic.parent.mkdir()
            input_topic.write_text(
                "conciencia",
                encoding="utf-8"
            )
            output_script = root / "output" / "scripts" / "guion.txt"
            prompt_engine = FakePromptEngine()
            FakeScriptBuilder.prompts = []

            input_script = root / "input" / "guion.txt"
            with self.assertRaises(
                OperationalError
            ) as raised:
                ScriptPreparationService(
                    prompt_engine=prompt_engine,
                    script_builder_factory=FakeScriptBuilder
                ).prepare(
                    builders={
                        "script": True
                    },
                    ai_config={
                        "model": "test-model"
                    },
                    profile={
                        "duration": 10
                    },
                    input_script_path=input_script,
                    input_topic_path=input_topic,
                    output_script_path=output_script,
                    source_mode="manual"
                )

            self.assert_input_error(
                raised.exception,
                f"No existe {input_script.as_posix()}.",
                f"Crea {input_script.as_posix()} con el guion "
                "y vuelve a intentarlo."
            )
            self.assertEqual(
                [],
                prompt_engine.calls
            )
            self.assertEqual(
                [],
                FakeScriptBuilder.prompts
            )
            self.assertFalse(
                output_script.exists()
            )

    def test_manual_source_rejects_empty_manual_script(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            input_script = root / "input" / "guion.txt"
            input_script.parent.mkdir()
            input_script.write_text(
                "   ",
                encoding="utf-8"
            )

            with self.assertRaises(
                OperationalError
            ) as raised:
                ScriptPreparationService().prepare(
                    builders={
                        "script": True
                    },
                    ai_config={},
                    profile={},
                    input_script_path=input_script,
                    input_topic_path=root / "input" / "tema.txt",
                    output_script_path=(
                        root
                        / "output"
                        / "scripts"
                        / "guion.txt"
                    ),
                    source_mode="manual"
                )

            self.assert_input_error(
                raised.exception,
                f"El archivo {input_script.as_posix()} está vacío.",
                f"Escribe el guion en {input_script.as_posix()} "
                "y vuelve a intentarlo."
            )

    def test_generated_source_rejects_empty_topic(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            input_topic = root / "input" / "tema.txt"
            input_topic.parent.mkdir()
            input_topic.write_text(
                " \n",
                encoding="utf-8"
            )

            with self.assertRaises(
                OperationalError
            ) as raised:
                self.prepare_generated(root, input_topic)

            self.assert_input_error(
                raised.exception,
                f"El archivo {input_topic.as_posix()} está vacío.",
                "Escribe el tema del vídeo en "
                f"{input_topic.as_posix()} y vuelve a intentarlo."
            )

    def test_generated_source_rejects_missing_topic(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            input_topic = root / "input" / "tema.txt"

            with self.assertRaises(
                OperationalError
            ) as raised:
                self.prepare_generated(root, input_topic)

            self.assert_input_error(
                raised.exception,
                f"No existe {input_topic.as_posix()}.",
                f"Crea {input_topic.as_posix()} con el tema del vídeo "
                "y vuelve a intentarlo."
            )

    def prepare_generated(self, root, input_topic):
        FakeScriptBuilder.prompts = []
        return ScriptPreparationService(
            prompt_engine=FakePromptEngine(),
            script_builder_factory=FakeScriptBuilder
        ).prepare(
            builders={
                "script": True
            },
            ai_config={},
            profile={},
            input_script_path=root / "input" / "guion.txt",
            input_topic_path=input_topic,
            output_script_path=root / "output" / "scripts" / "guion.txt",
            source_mode="generated"
        )

    def assert_input_error(self, error, user_message, recommended_action):
        context = error.context
        self.assertIs(ErrorSeverity.FATAL_OPERATIONAL, context.severity)
        self.assertEqual(user_message, context.user_message)
        self.assertEqual(recommended_action, context.recommended_action)
        self.assertEqual("Preparar el guion", context.operation)

    def test_existing_script_keeps_current_disabled_builder_behavior(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            output_script = root / "output" / "scripts" / "guion.txt"
            output_script.parent.mkdir(
                parents=True
            )
            output_script.write_text(
                "Guion existente.",
                encoding="utf-8"
            )

            prepared_script = ScriptPreparationService().prepare(
                builders={
                    "script": False
                },
                ai_config={},
                profile={},
                input_script_path=root / "input" / "guion.txt",
                input_topic_path=root / "input" / "tema.txt",
                output_script_path=output_script
            )

            self.assertEqual(
                "existing",
                prepared_script.source
            )
            self.assertEqual(
                "Guion existente.",
                prepared_script.text
            )
            self.assertEqual(
                "Guion existente.",
                output_script.read_text(
                    encoding="utf-8"
                )
            )

    def test_no_unexpected_output_route_is_created(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            input_script = root / "input" / "guion.txt"
            input_script.parent.mkdir()
            input_script.write_text(
                "Guion manual preparado.",
                encoding="utf-8"
            )
            output_script = root / "output" / "scripts" / "guion.txt"

            ScriptPreparationService().prepare(
                builders={
                    "script": True
                },
                ai_config={},
                profile={},
                input_script_path=input_script,
                input_topic_path=root / "input" / "tema.txt",
                output_script_path=output_script,
                source_mode="manual"
            )

            self.assertEqual(
                [
                    output_script
                ],
                [
                    path
                    for path in root.rglob("*")
                    if path.is_file()
                    and "input" not in path.parts
                ]
            )


class ScriptOperationTest(
    unittest.TestCase
):

    def test_script_operation_returns_prepared_script_from_preparation_service(self):
        service = FakePreparationService()
        output_script = Path(
            "output/project/scripts/guion.txt"
        )

        result = ScriptOperation(
            preparation_service=service
        ).execute(
            builders={
                "script": True
            },
            ai_config={
                "model": "test-model"
            },
            profile={
                "duration": 10
            },
            input_script_path=Path(
                "input/guion.txt"
            ),
            input_topic_path=Path(
                "input/tema.txt"
            ),
            output_script_path=output_script,
            source_mode="manual"
        )

        self.assertIsInstance(
            result,
            PreparedScript
        )
        self.assertEqual(
            "Guion preparado.",
            result.text
        )
        self.assertEqual(
            output_script,
            result.path
        )
        self.assertEqual(
            1,
            len(service.calls)
        )
        self.assertEqual(
            output_script,
            service.calls[0]["output_script_path"]
        )
        self.assertEqual(
            "manual",
            service.calls[0]["source_mode"]
        )


if __name__ == "__main__":
    unittest.main()
