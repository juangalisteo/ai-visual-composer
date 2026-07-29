import unittest
from dataclasses import FrozenInstanceError

from app.domain import (
    CertaintyLevel,
    StoryboardScene,
    VisualSceneIntent,
)
from app.visual_intelligence import (
    SceneIntentResolver,
    VisualAnalysisOrchestrator,
)


def analysis_result():
    scene = StoryboardScene(
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
        filmable_interpretation="una llave cambia de manos",
    )
    return VisualAnalysisOrchestrator().analyze(
        scene
    )


class SceneIntentResolverTest(unittest.TestCase):

    def test_resolves_scene_intent_from_visual_analysis(self):
        intent = SceneIntentResolver().resolve(
            analysis_result()
        )

        self.assertIsInstance(
            intent,
            VisualSceneIntent
        )
        self.assertEqual(
            intent.emotional_function,
            "hold attention on llave antigua"
        )
        self.assertEqual(
            intent.narrative_tension,
            "object-driven observable tension"
        )
        self.assertEqual(
            intent.visual_subtext,
            "llave antigua carries the observable action"
        )
        self.assertEqual(
            intent.uncertainty,
            CertaintyLevel.EXPLICIT
        )

    def test_minimal_analysis_does_not_invent_intent(self):
        scene = StoryboardScene(
            scene_number=1,
            text="Sin datos"
        )
        analysis = VisualAnalysisOrchestrator().analyze(
            scene
        )

        intent = SceneIntentResolver().resolve(
            analysis
        )

        self.assertEqual(
            intent.emotional_function,
            "unknown"
        )
        self.assertEqual(
            intent.narrative_tension,
            "unknown"
        )
        self.assertEqual(
            intent.visual_subtext,
            "unknown"
        )
        self.assertEqual(
            intent.uncertainty,
            CertaintyLevel.UNKNOWN
        )

    def test_trace_evidence_and_fingerprint_are_deterministic(self):
        resolver = SceneIntentResolver()
        first = resolver.resolve(
            analysis_result()
        )
        second = resolver.resolve(
            analysis_result()
        )

        self.assertEqual(
            first,
            second
        )
        self.assertEqual(
            first.fingerprint,
            second.fingerprint
        )
        self.assertTrue(
            first.evidences
        )
        self.assertTrue(
            first.trace.entries
        )

    def test_result_is_immutable(self):
        intent = SceneIntentResolver().resolve(
            analysis_result()
        )

        with self.assertRaises(
            FrozenInstanceError
        ):
            intent.emotional_function = "changed"

    def test_rejects_invalid_input(self):
        with self.assertRaises(
            TypeError
        ):
            SceneIntentResolver().resolve(
                "invalid"
            )


if __name__ == "__main__":
    unittest.main()
