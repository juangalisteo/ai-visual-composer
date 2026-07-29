import unittest

from app.domain import CertaintyLevel, StoryboardScene, VisualSemantics
from app.visual_intelligence import VisualSemanticsResolver, VisualTruthInspector


def semantic_scene():
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
        filmable_interpretation="una llave cambia de manos",
    )


class VisualSemanticsResolverTest(unittest.TestCase):

    def test_resolves_explicit_visual_semantics(self):
        scene = semantic_scene()
        inspection = VisualTruthInspector().inspect(
            scene
        )

        semantics = VisualSemanticsResolver().resolve(
            scene,
            inspection
        )

        self.assertIsInstance(
            semantics,
            VisualSemantics
        )
        self.assertEqual(
            semantics.primary_subject,
            "investigadora con abrigo gris"
        )
        self.assertEqual(
            semantics.narrative_objects,
            (
                "llave antigua",
                "sobre lacrado",
            )
        )
        self.assertEqual(
            semantics.active_environment,
            "archivo subterraneo"
        )
        self.assertEqual(
            semantics.contextual_environment,
            "noche lluviosa"
        )
        self.assertEqual(
            semantics.observable_action,
            "recibe una llave antigua"
        )
        self.assertEqual(
            semantics.ambiguity_level,
            CertaintyLevel.EXPLICIT
        )

    def test_uses_visual_state_when_action_is_absent(self):
        scene = StoryboardScene(
            scene_number=1,
            text="Escena sin accion",
            visible_subject="puerta metalica",
            visible_environment="pasillo oscuro",
            filmable_interpretation="puerta metalica cerrada en silencio",
        )
        inspection = VisualTruthInspector().inspect(
            scene
        )

        semantics = VisualSemanticsResolver().resolve(
            scene,
            inspection
        )

        self.assertEqual(
            semantics.observable_action,
            ""
        )
        self.assertEqual(
            semantics.visual_state,
            "puerta metalica cerrada en silencio"
        )

    def test_marks_ambiguity_from_inspection(self):
        scene = StoryboardScene(
            scene_number=1,
            text="Escena ambigua",
            visible_subject="persona",
            visible_action="observa",
            visible_environment="lugar",
            filmable_interpretation="persona observa lugar",
        )
        inspection = VisualTruthInspector().inspect(
            scene
        )

        semantics = VisualSemanticsResolver().resolve(
            scene,
            inspection
        )

        self.assertEqual(
            semantics.ambiguity_level,
            CertaintyLevel.WEAK
        )

    def test_unknown_subject_is_explicit_when_missing(self):
        scene = StoryboardScene(
            scene_number=1,
            text="Sin sujeto",
            visible_action="abre una puerta",
            visible_environment="pasillo",
            filmable_interpretation="una puerta se abre",
        )
        inspection = VisualTruthInspector().inspect(
            scene
        )

        semantics = VisualSemanticsResolver().resolve(
            scene,
            inspection
        )

        self.assertEqual(
            semantics.primary_subject,
            "unknown"
        )

    def test_evidence_trace_and_fingerprint_are_deterministic(self):
        scene = semantic_scene()
        inspection = VisualTruthInspector().inspect(
            scene
        )
        resolver = VisualSemanticsResolver()

        first = resolver.resolve(
            scene,
            inspection
        )
        second = resolver.resolve(
            scene,
            inspection
        )

        self.assertEqual(
            first.fingerprint,
            second.fingerprint
        )
        self.assertEqual(
            first.trace.fingerprint,
            second.trace.fingerprint
        )
        self.assertTrue(
            first.evidences
        )

    def test_input_is_not_mutated(self):
        scene = semantic_scene()
        original = scene
        inspection = VisualTruthInspector().inspect(
            scene
        )

        VisualSemanticsResolver().resolve(
            scene,
            inspection
        )

        self.assertEqual(
            scene,
            original
        )

    def test_rejects_invalid_inputs(self):
        scene = semantic_scene()

        with self.assertRaises(
            TypeError
        ):
            VisualSemanticsResolver().resolve(
                scene,
                "invalid"
            )


if __name__ == "__main__":
    unittest.main()
