import inspect
import unittest
from dataclasses import asdict
from pathlib import Path

from app.domain import ResolutionStatus, VisualSynthesisResult
from app.visual_intelligence import (
    VisualSynthesisOrchestrator,
)
from tests.test_visual_synthesis_helpers import (
    analysis_and_reasoning,
    complete_scene,
    error_scene,
    warning_scene,
)


class VisualSynthesisOrchestratorTest(unittest.TestCase):

    def test_runs_visual_synthesis_end_to_end(self):
        analysis, reasoning = analysis_and_reasoning(
            complete_scene()
        )

        result = VisualSynthesisOrchestrator().synthesize(
            analysis,
            reasoning
        )

        self.assertIsInstance(
            result,
            VisualSynthesisResult
        )
        self.assertEqual(
            result.brief.primary_identity,
            "investigadora con abrigo gris"
        )
        self.assertEqual(
            result.conflicts.conflicts,
            ()
        )
        self.assertTrue(
            result.trace.evidences
        )
        self.assertEqual(
            result.status,
            ResolutionStatus.READY
        )

    def test_synthesis_preserves_warning_status(self):
        analysis, reasoning = analysis_and_reasoning(
            warning_scene()
        )

        result = VisualSynthesisOrchestrator().synthesize(
            analysis,
            reasoning
        )

        self.assertEqual(
            result.status,
            ResolutionStatus.WARNING
        )
        self.assertTrue(
            result.findings
        )

    def test_synthesis_preserves_error_status(self):
        analysis, reasoning = analysis_and_reasoning(
            error_scene()
        )

        result = VisualSynthesisOrchestrator().synthesize(
            analysis,
            reasoning
        )

        self.assertEqual(
            result.status,
            ResolutionStatus.ERROR
        )
        self.assertTrue(
            result.conflicts.conflicts
        )

    def test_visual_synthesis_result_is_serializable_and_deterministic(self):
        analysis, reasoning = analysis_and_reasoning(
            complete_scene()
        )
        orchestrator = VisualSynthesisOrchestrator()

        first = orchestrator.synthesize(
            analysis,
            reasoning
        )
        second = orchestrator.synthesize(
            analysis,
            reasoning
        )

        self.assertEqual(
            first,
            second
        )
        self.assertEqual(
            first.fingerprint,
            second.fingerprint
        )
        self.assertEqual(
            asdict(
                first
            )["brief"]["primary_identity"],
            "investigadora con abrigo gris"
        )

    def test_rejects_invalid_inputs(self):
        analysis, reasoning = analysis_and_reasoning(
            complete_scene()
        )

        with self.assertRaises(
            TypeError
        ):
            VisualSynthesisOrchestrator().synthesize(
                analysis,
                "invalid"
            )

    def test_visual_synthesis_layer_has_no_forbidden_dependencies(self):
        forbidden = (
            "RuntimeCognitiveAdapter",
            "ImageBuilder",
            "PromptTranslator",
            "BackendPrompt",
            "VisualQuality",
            "ComfyUI",
            "VideoPipeline",
            "Workflow",
            "requests",
            "urllib",
            "app.modules",
            "app.prompt_translation",
            "app.backend_adapters",
            "app.visual_quality",
        )
        package = __import__(
            "app.visual_intelligence.synthesis",
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

    def test_runtime_integration_does_not_create_inverse_adapters(self):
        source = ""
        for path in Path(
            "app"
        ).rglob(
            "*.py"
        ):
            source += path.read_text(
                encoding="utf-8"
            )

        for item in (
            "VisualIntelligenceRuntimeAdapter",
            "RuntimeVisualIntelligenceAdapter",
            "EffectiveVisualBriefAdapter",
        ):
            with self.subTest(
                item=item
            ):
                self.assertNotIn(
                    item,
                    source
                )


if __name__ == "__main__":
    unittest.main()
