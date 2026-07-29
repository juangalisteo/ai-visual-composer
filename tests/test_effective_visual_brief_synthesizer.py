import unittest
from dataclasses import FrozenInstanceError, asdict

from app.domain import EffectiveVisualBrief
from app.visual_intelligence import (
    EffectiveVisualBriefSynthesizer,
    VisualConflictResolver,
)
from tests.test_visual_synthesis_helpers import (
    analysis_and_reasoning,
    complete_scene,
    error_scene,
)


def synthesize_brief(scene):
    analysis, reasoning = analysis_and_reasoning(
        scene
    )
    conflicts = VisualConflictResolver().resolve(
        analysis,
        reasoning
    )
    return EffectiveVisualBriefSynthesizer().synthesize(
        analysis,
        reasoning,
        conflicts
    )


class EffectiveVisualBriefSynthesizerTest(unittest.TestCase):

    def test_synthesizes_effective_brief_without_losing_information(self):
        brief = synthesize_brief(
            complete_scene()
        )

        self.assertIsInstance(
            brief,
            EffectiveVisualBrief
        )
        self.assertEqual(
            brief.primary_identity,
            "investigadora con abrigo gris"
        )
        self.assertEqual(
            brief.primary_actions,
            (
                "recibe una llave antigua",
            )
        )
        self.assertIn(
            "llave antigua",
            brief.visual_priorities
        )
        self.assertEqual(
            brief.restrictions,
            (
                "sin texto legible",
            )
        )
        self.assertEqual(
            brief.continuity.scene_relationships,
            (
                "misma investigadora",
                "misma llave antigua",
            )
        )

    def test_preserves_strategy_intent_conflicts_findings_and_evidence(self):
        brief = synthesize_brief(
            error_scene()
        )

        self.assertTrue(
            brief.strategy
        )
        self.assertTrue(
            brief.emotional_function
        )
        self.assertTrue(
            brief.conflicts
        )
        self.assertTrue(
            brief.findings
        )
        self.assertTrue(
            brief.evidences
        )
        self.assertTrue(
            brief.trace.entries
        )

    def test_brief_is_passive_immutable_and_serializable(self):
        brief = synthesize_brief(
            complete_scene()
        )

        with self.assertRaises(
            FrozenInstanceError
        ):
            brief.primary_identity = "changed"

        serialized = asdict(
            brief
        )

        self.assertEqual(
            serialized["primary_identity"],
            "investigadora con abrigo gris"
        )

    def test_repeated_brief_synthesis_is_deterministic(self):
        first = synthesize_brief(
            complete_scene()
        )
        second = synthesize_brief(
            complete_scene()
        )

        self.assertEqual(
            first,
            second
        )
        self.assertEqual(
            first.fingerprint,
            second.fingerprint
        )

    def test_rejects_invalid_conflict_report(self):
        analysis, reasoning = analysis_and_reasoning(
            complete_scene()
        )

        with self.assertRaises(
            TypeError
        ):
            EffectiveVisualBriefSynthesizer().synthesize(
                analysis,
                reasoning,
                "invalid"
            )


if __name__ == "__main__":
    unittest.main()
