import unittest
from dataclasses import replace

from app.domain import (
    FindingSeverity,
    StoryboardScene,
    VisualInspectionResult,
)
from app.visual_intelligence import VisualTruthInspector


def dense_scene():
    return StoryboardScene(
        scene_number=1,
        text="Una investigadora recibe una llave antigua.",
        visible_subject="investigadora con abrigo gris",
        visible_action="recibe una llave antigua",
        visible_environment="archivo subterraneo",
        time_context="noche lluviosa",
        key_objects=(
            "llave antigua",
            "sobre lacrado",
        ),
        spatial_relationships=(
            "la llave queda entre ambas manos",
        ),
        continuity_links=(
            "misma investigadora",
        ),
        abstract_source="confianza entregada",
        filmable_interpretation=(
            "una llave antigua cambia de manos en silencio"
        ),
        visual_constraints=(
            "sin texto legible",
        ),
    )


class VisualTruthInspectorTest(unittest.TestCase):

    def test_inspects_complete_visual_truth(self):
        result = VisualTruthInspector().inspect(
            dense_scene()
        )

        self.assertIsInstance(
            result,
            VisualInspectionResult
        )
        self.assertEqual(
            result.completeness,
            "complete"
        )
        self.assertEqual(
            result.consistency,
            "consistent"
        )
        self.assertEqual(
            result.visual_density,
            "saturated"
        )
        self.assertEqual(
            result.specificity,
            "detailed"
        )
        self.assertEqual(
            result.findings,
            ()
        )

    def test_visual_truth_minimum_valid_scene_is_partial_when_optional_data_absent(self):
        scene = StoryboardScene(
            scene_number=1,
            text="Escena minima",
            visible_subject="persona adulta",
            visible_action="observa",
            visible_environment="habitacion iluminada",
            filmable_interpretation="persona adulta observa una habitacion",
        )

        result = VisualTruthInspector().inspect(
            scene
        )

        self.assertEqual(
            result.completeness,
            "complete"
        )
        self.assertEqual(
            result.visual_density,
            "moderate"
        )

    def test_empty_scene_produces_blocking_finding(self):
        result = VisualTruthInspector().inspect(
            StoryboardScene(
                scene_number=1,
                text=""
            )
        )

        self.assertEqual(
            result.completeness,
            "empty"
        )
        self.assertEqual(
            result.findings[0].code,
            "VISUAL_TRUTH_EMPTY_SCENE"
        )
        self.assertEqual(
            result.findings[0].severity,
            FindingSeverity.BLOCKING
        )

    def test_missing_required_fields_are_reported_deterministically(self):
        scene = StoryboardScene(
            scene_number=1,
            text="Accion sin sujeto",
            visible_action="abre una puerta",
            visible_environment="pasillo",
        )

        result = VisualTruthInspector().inspect(
            scene
        )

        self.assertEqual(
            result.missing_fields,
            (
                "visible_subject",
                "filmable_interpretation",
            )
        )
        self.assertIn(
            "VISUAL_TRUTH_REQUIRED_FIELD_MISSING",
            tuple(
                finding.code
                for finding in result.findings
            )
        )

    def test_ambiguous_fields_are_reported(self):
        scene = dense_scene()
        scene = replace(
            scene,
            visible_subject="persona"
        )

        result = VisualTruthInspector().inspect(
            scene
        )

        self.assertEqual(
            result.ambiguous_fields,
            (
                "visible_subject",
            )
        )
        self.assertIn(
            "VISUAL_TRUTH_FIELD_AMBIGUOUS",
            tuple(
                finding.code
                for finding in result.findings
            )
        )

    def test_direct_inconsistency_action_without_subject(self):
        scene = StoryboardScene(
            scene_number=1,
            text="Accion sin sujeto",
            visible_action="abre una puerta",
            visible_environment="pasillo",
            filmable_interpretation="una puerta se abre",
        )

        result = VisualTruthInspector().inspect(
            scene
        )

        self.assertEqual(
            result.consistency,
            "inconsistent"
        )
        self.assertIn(
            "VISUAL_TRUTH_DIRECT_INCONSISTENCY",
            tuple(
                finding.code
                for finding in result.findings
            )
        )

    def test_low_specificity_is_reported_for_generic_scene(self):
        scene = StoryboardScene(
            scene_number=1,
            text="Escena generica",
            visible_subject="persona",
            visible_action="observa",
            visible_environment="lugar",
            filmable_interpretation="persona observa lugar",
        )

        result = VisualTruthInspector().inspect(
            scene
        )

        self.assertEqual(
            result.specificity,
            "general"
        )
        self.assertIn(
            "VISUAL_TRUTH_LOW_SPECIFICITY",
            tuple(
                finding.code
                for finding in result.findings
            )
        )

    def test_fingerprint_and_trace_are_deterministic(self):
        inspector = VisualTruthInspector()
        first = inspector.inspect(
            dense_scene()
        )
        second = inspector.inspect(
            dense_scene()
        )

        self.assertEqual(
            first.fingerprint,
            second.fingerprint
        )
        self.assertEqual(
            first.trace.fingerprint,
            second.trace.fingerprint
        )

    def test_input_is_not_mutated(self):
        scene = dense_scene()
        original = scene

        VisualTruthInspector().inspect(
            scene
        )

        self.assertEqual(
            scene,
            original
        )
        self.assertEqual(
            scene.key_objects,
            (
                "llave antigua",
                "sobre lacrado",
            )
        )

    def test_rejects_invalid_input_type(self):
        with self.assertRaises(
            TypeError
        ):
            VisualTruthInspector().inspect(
                {
                    "visible_subject": "persona",
                }
            )


if __name__ == "__main__":
    unittest.main()
