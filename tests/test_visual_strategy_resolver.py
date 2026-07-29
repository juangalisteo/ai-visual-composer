import unittest

from app.domain import (
    FindingSeverity,
    StoryboardScene,
    VisualIntelligenceStrategy,
)
from app.visual_intelligence import (
    SceneIntentResolver,
    VisualAnalysisOrchestrator,
    VisualStrategyResolver,
)


def analysis_with_constraints():
    scene = StoryboardScene(
        scene_number=1,
        text="Una investigadora recibe una llave antigua.",
        visible_subject="investigadora con abrigo gris",
        visible_action="recibe una llave antigua",
        visible_environment="archivo subterraneo",
        time_context="noche lluviosa",
        key_objects=(
            "llave antigua",
        ),
        spatial_relationships=(
            "la llave queda entre ambas manos",
        ),
        continuity_links=(
            "misma investigadora",
        ),
        filmable_interpretation="una llave cambia de manos",
        visual_constraints=(
            "sin texto legible",
            "evitar logos",
        ),
    )
    return VisualAnalysisOrchestrator().analyze(
        scene
    )


def resolve_strategy(analysis):
    intent = SceneIntentResolver().resolve(
        analysis
    )
    return VisualStrategyResolver().resolve(
        analysis,
        intent
    )


class VisualStrategyResolverTest(unittest.TestCase):

    def test_resolves_abstract_strategy_from_analysis_and_intent(self):
        strategy = resolve_strategy(
            analysis_with_constraints()
        )

        self.assertIsInstance(
            strategy,
            VisualIntelligenceStrategy
        )
        self.assertEqual(
            strategy.representation_approach,
            "represent explicit Visual Truth directly"
        )
        self.assertEqual(
            strategy.realism_level,
            "source-constrained high detail"
        )
        self.assertEqual(
            strategy.symbolism_degree,
            "evidence-bound"
        )

    def test_preserves_visual_constraints_as_limits_and_avoidance(self):
        strategy = resolve_strategy(
            analysis_with_constraints()
        )

        self.assertEqual(
            strategy.visual_limits,
            (
                "sin texto legible",
                "evitar logos",
            )
        )
        self.assertEqual(
            strategy.resources_to_avoid,
            (
                "sin texto legible",
            )
        )

    def test_declares_existing_blocking_or_error_findings_without_resolving_them(self):
        scene = StoryboardScene(
            scene_number=1,
            text="Accion sin sujeto",
            visible_action="abre una puerta",
            visible_environment="pasillo",
            filmable_interpretation="una puerta se abre",
        )
        analysis = VisualAnalysisOrchestrator().analyze(
            scene
        )

        strategy = resolve_strategy(
            analysis
        )

        self.assertIn(
            FindingSeverity.ERROR,
            tuple(
                finding.severity
                for finding in strategy.declared_conflicts
            )
        )

    def test_repeated_strategy_is_deterministic(self):
        first = resolve_strategy(
            analysis_with_constraints()
        )
        second = resolve_strategy(
            analysis_with_constraints()
        )

        self.assertEqual(
            first,
            second
        )
        self.assertEqual(
            first.fingerprint,
            second.fingerprint
        )

    def test_rejects_invalid_inputs(self):
        analysis = analysis_with_constraints()

        with self.assertRaises(
            TypeError
        ):
            VisualStrategyResolver().resolve(
                analysis,
                "invalid"
            )


if __name__ == "__main__":
    unittest.main()
