import tempfile
import unittest
from pathlib import Path

from app.modules.script import (
    PreparedScript,
    ScriptOperation,
    ScriptPreparationService,
)


class FakePromptEngine:

    def __init__(
        self
    ):
        self.calls = []

    def build_script_prompt(
        self,
        topic,
        profile
    ):
        self.calls.append(
            (
                topic,
                profile
            )
        )
        return f"PROMPT: {topic}"


class FakeScriptBuilder:
    prompts = []

    def __init__(
        self,
        ai_config
    ):
        self.ai_config = ai_config

    def build(
        self,
        prompt
    ):
        self.prompts.append(
            prompt
        )
        return (
            "Guion generado estable para el pipeline actual."
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

            prepared_script = ScriptPreparationService(
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
                input_script_path=root / "input" / "missing.txt",
                input_topic_path=input_topic,
                output_script_path=output_script
            )

            self.assertEqual(
                "generated",
                prepared_script.source
            )
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
                    "model": "test-model"
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

            with self.assertRaises(
                FileNotFoundError
            ):
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
                    input_script_path=root / "input" / "guion.txt",
                    input_topic_path=input_topic,
                    output_script_path=output_script,
                    source_mode="manual"
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
                ValueError
            ):
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
