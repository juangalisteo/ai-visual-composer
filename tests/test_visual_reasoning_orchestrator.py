import inspect
import unittest
from pathlib import Path

from app.domain import (
    ResolutionStatus,
    StoryboardScene,
    VisualReasoningResult,
)
from app.visual_intelligence import (
    VisualAnalysisOrchestrator,
    VisualReasoningOrchestrator,
)


def reasoning_analysis():
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
        ),
    )
    return VisualAnalysisOrchestrator().analyze(
        scene
    )


class VisualReasoningOrchestratorTest(unittest.TestCase):

    def test_runs_visual_reasoning_end_to_end(self):
        result = VisualReasoningOrchestrator().reason(
            reasoning_analysis()
        )

        self.assertIsInstance(
            result,
            VisualReasoningResult
        )
        self.assertEqual(
            result.scene_intent.emotional_function,
            "hold attention on llave antigua"
        )
        self.assertEqual(
            result.strategy.representation_approach,
            "represent explicit Visual Truth directly"
        )
        self.assertEqual(
            result.continuity.scene_relationships,
            (
                "misma investigadora",
            )
        )
        self.assertEqual(
            result.status,
            ResolutionStatus.READY
        )

    def test_aggregates_findings_trace_and_status(self):
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

        result = VisualReasoningOrchestrator().reason(
            analysis
        )

        self.assertEqual(
            result.status,
            ResolutionStatus.WARNING
        )
        self.assertTrue(
            result.findings
        )
        self.assertTrue(
            result.trace.entries
        )
        self.assertTrue(
            result.trace.evidences
        )

    def test_repeated_reasoning_is_deterministic(self):
        orchestrator = VisualReasoningOrchestrator()
        first = orchestrator.reason(
            reasoning_analysis()
        )
        second = orchestrator.reason(
            reasoning_analysis()
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
            VisualReasoningOrchestrator().reason(
                "invalid"
            )

    def test_visual_reasoning_layer_has_no_forbidden_dependencies(self):
        forbidden = (
            "RuntimeCognitiveAdapter",
            "ImageBuilder",
            "PromptTranslator",
            "BackendPrompt",
            "ComfyUI",
            "VisualQuality",
            "VideoBuilder",
            "workflow",
            "requests",
            "urllib",
        )
        package = __import__(
            "app.visual_intelligence.reasoning",
            fromlist=[
                "x"
            ]
        )
        source = inspect.getsource(
            package
        )

        for item in forbidden:
            with self.subTest(
                item=item
            ):
                self.assertNotIn(
                    item,
                    source
                )

    def test_no_future_synthesis_components_are_implemented(self):
        source = ""
        for path in Path(
            "app"
        ).rglob(
            "*.py"
        ):
            source += path.read_text(
                encoding="utf-8"
            )

        self.assertNotIn(
            "VisualIntelligenceRuntimeAdapter",
            source
        )


if __name__ == "__main__":
    unittest.main()
