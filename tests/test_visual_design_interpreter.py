import json
import unittest

from app.modules.visual_design import (
    VisualDesignInterpretationError,
    VisualDesignInterpreter,
)


class FakeAIBuilder:

    def __init__(
        self,
        ai_config,
        response=None,
        error=None
    ):
        self.ai_config = ai_config
        self.response = response
        self.error = error

    def build(
        self,
        prompt
    ):
        if self.error is not None:
            raise self.error
        return self.response


class VisualDesignInterpreterTest(unittest.TestCase):

    def test_interprets_explicit_visual_input(self):
        source_text = (
            "Nikola Tesla sentado en su despacho "
            "con una bombilla iluminandose."
        )
        interpreter = _interpreter_with_response(
            [
                {
                    "scene": 1,
                    "visible_subject": "Nikola Tesla sentado",
                    "visible_action": (
                        "permanece sentado junto a una bombilla "
                        "que se ilumina"
                    ),
                    "visible_environment": "despacho",
                    "time_context": "",
                    "key_objects": [
                        "bombilla"
                    ],
                    "spatial_relationships": [
                        "Tesla esta junto a la bombilla"
                    ],
                    "continuity_links": [],
                    "filmable_interpretation": (
                        "Nikola Tesla permanece sentado en su "
                        "despacho mientras una bombilla se ilumina."
                    )
                }
            ]
        )

        visual_truth = interpreter.interpret(
            source_text
        )

        self.assertEqual(
            source_text,
            visual_truth["abstract_source"]
        )
        self.assertIn(
            "Tesla",
            visual_truth["visible_subject"]
        )
        self.assertIn(
            "sentado",
            visual_truth["visible_action"]
        )
        self.assertIn(
            "despacho",
            visual_truth["visible_environment"]
        )
        self.assertIn(
            "bombilla",
            " ".join(
                visual_truth["key_objects"]
            )
        )

    def test_interprets_conceptual_input(self):
        source_text = "Harry Potter y el misterio del principe"
        interpreter = _interpreter_with_response(
            [
                {
                    "scene": 1,
                    "visible_subject": (
                        "joven mago observando un libro antiguo"
                    ),
                    "visible_action": (
                        "investiga un misterio en silencio"
                    ),
                    "visible_environment": (
                        "biblioteca oscura de un castillo"
                    ),
                    "time_context": "noche",
                    "key_objects": [
                        "libro antiguo",
                        "varita"
                    ],
                    "spatial_relationships": [
                        "el joven esta frente al libro"
                    ],
                    "continuity_links": [],
                    "filmable_interpretation": (
                        "Un joven mago estudia un libro antiguo "
                        "en una biblioteca oscura."
                    )
                }
            ]
        )

        visual_truth = interpreter.interpret(
            source_text
        )

        self.assertEqual(
            source_text,
            visual_truth["abstract_source"]
        )
        self.assertNotEqual(
            source_text,
            visual_truth["visible_subject"]
        )
        self.assertNotEqual(
            source_text,
            visual_truth["visible_action"]
        )
        self.assertNotEqual(
            source_text,
            visual_truth["visible_environment"]
        )
        self.assertNotEqual(
            source_text,
            visual_truth["filmable_interpretation"]
        )

    def test_rejects_empty_response(self):
        interpreter = _interpreter_with_raw_response(
            ""
        )

        with self.assertRaises(
            VisualDesignInterpretationError
        ):
            interpreter.interpret(
                "El misterio del universo"
            )

    def test_rejects_invalid_json_response(self):
        interpreter = _interpreter_with_raw_response(
            "not-json"
        )

        with self.assertRaises(
            VisualDesignInterpretationError
        ):
            interpreter.interpret(
                "El misterio del universo"
            )

    def test_rejects_degenerate_literal_copy(self):
        source_text = "Harry Potter y el misterio del principe"
        interpreter = _interpreter_with_response(
            [
                {
                    "scene": 1,
                    "visible_subject": source_text,
                    "visible_action": source_text,
                    "visible_environment": source_text,
                    "filmable_interpretation": source_text,
                }
            ]
        )

        with self.assertRaisesRegex(
            VisualDesignInterpretationError,
            "copiar"
        ):
            interpreter.interpret(
                source_text
            )

    def test_reports_timeout_as_controlled_error(self):
        interpreter = _interpreter_with_error(
            TimeoutError()
        )

        with self.assertRaisesRegex(
            VisualDesignInterpretationError,
            "tiempo maximo"
        ):
            interpreter.interpret(
                "El despertar de la conciencia"
            )

    def test_reports_provider_error_as_controlled_error(self):
        interpreter = _interpreter_with_error(
            RuntimeError(
                "provider failed"
            )
        )

        with self.assertRaisesRegex(
            VisualDesignInterpretationError,
            "No se pudo completar"
        ):
            interpreter.interpret(
                "El despertar de la conciencia"
            )


def _interpreter_with_response(
    response
):
    return _interpreter_with_raw_response(
        json.dumps(
            response
        )
    )


def _interpreter_with_raw_response(
    response
):
    return VisualDesignInterpreter(
        ai_config={
            "model": "fake"
        },
        profile={
            "tone": "modo_conciencia",
            "platform": "instagram",
            "format": "vertical",
        },
        ai_builder_factory=lambda ai_config: FakeAIBuilder(
            ai_config,
            response=response
        )
    )


def _interpreter_with_error(
    error
):
    return VisualDesignInterpreter(
        ai_config={
            "model": "fake"
        },
        profile={
            "tone": "modo_conciencia",
            "platform": "instagram",
            "format": "vertical",
        },
        ai_builder_factory=lambda ai_config: FakeAIBuilder(
            ai_config,
            error=error
        )
    )


if __name__ == "__main__":
    unittest.main()
