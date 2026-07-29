import unittest

from app.domain import (
    FindingSeverity,
    SequenceContinuity,
    StoryboardScene,
)
from app.visual_intelligence import (
    SequenceContinuityResolver,
    VisualAnalysisOrchestrator,
)


def continuity_analysis():
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
            "misma llave antigua",
        ),
        filmable_interpretation="una llave cambia de manos",
    )
    return VisualAnalysisOrchestrator().analyze(
        scene
    )


class SequenceContinuityResolverTest(unittest.TestCase):

    def test_resolves_sequence_continuity_from_analysis_trace(self):
        continuity = SequenceContinuityResolver().resolve(
            continuity_analysis()
        )

        self.assertIsInstance(
            continuity,
            SequenceContinuity
        )
        self.assertEqual(
            continuity.character_continuity,
            (
                "investigadora con abrigo gris",
            )
        )
        self.assertEqual(
            continuity.object_continuity,
            (
                "llave antigua",
                "sobre lacrado",
            )
        )
        self.assertIn(
            "archivo subterraneo",
            continuity.location_continuity
        )
        self.assertEqual(
            continuity.scene_relationships,
            (
                "misma investigadora",
                "misma llave antigua",
            )
        )

    def test_reports_risk_when_no_continuity_or_spatial_relationship_exists(self):
        scene = StoryboardScene(
            scene_number=1,
            text="Retrato simple",
            visible_subject="arquitecta",
            visible_action="observa",
            visible_environment="azotea",
            filmable_interpretation="arquitecta observa",
        )
        analysis = VisualAnalysisOrchestrator().analyze(
            scene
        )

        continuity = SequenceContinuityResolver().resolve(
            analysis
        )

        self.assertEqual(
            continuity.detected_risks[0].code,
            "SEQUENCE_CONTINUITY_LINKS_ABSENT"
        )
        self.assertEqual(
            continuity.detected_risks[0].severity,
            FindingSeverity.WARNING
        )

    def test_repeated_continuity_is_deterministic(self):
        resolver = SequenceContinuityResolver()
        first = resolver.resolve(
            continuity_analysis()
        )
        second = resolver.resolve(
            continuity_analysis()
        )

        self.assertEqual(
            first,
            second
        )
        self.assertEqual(
            first.fingerprint,
            second.fingerprint
        )

    def test_rejects_invalid_input(self):
        with self.assertRaises(
            TypeError
        ):
            SequenceContinuityResolver().resolve(
                {}
            )


if __name__ == "__main__":
    unittest.main()
