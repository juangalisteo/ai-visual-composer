import inspect
import unittest
from pathlib import Path

from app.domain import (
    FindingSeverity,
    ResolutionStatus,
    StoryboardScene,
    VisualAnalysisResult,
)
from app.visual_intelligence import VisualAnalysisOrchestrator


def analysis_scene():
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
        filmable_interpretation="una llave cambia de manos",
        visual_constraints=(
            "sin texto legible",
        ),
    )


class VisualAnalysisOrchestratorTest(unittest.TestCase):

    def test_runs_visual_analysis_end_to_end(self):
        result = VisualAnalysisOrchestrator().analyze(
            analysis_scene()
        )

        self.assertIsInstance(
            result,
            VisualAnalysisResult
        )
        self.assertEqual(
            result.inspection.completeness,
            "complete"
        )
        self.assertEqual(
            result.semantics.primary_subject,
            "investigadora con abrigo gris"
        )
        self.assertEqual(
            result.priority.primary_priority,
            "llave antigua"
        )
        self.assertEqual(
            result.status,
            ResolutionStatus.READY
        )

    def test_aggregates_findings_and_status(self):
        scene = StoryboardScene(
            scene_number=1,
            text="Accion sin sujeto",
            visible_action="abre una puerta",
            visible_environment="pasillo",
            filmable_interpretation="una puerta se abre",
        )

        result = VisualAnalysisOrchestrator().analyze(
            scene
        )

        self.assertIn(
            FindingSeverity.ERROR,
            tuple(
                finding.severity
                for finding in result.findings
            )
        )
        self.assertEqual(
            result.status,
            ResolutionStatus.ERROR
        )

    def test_blocking_status_for_empty_visual_truth(self):
        result = VisualAnalysisOrchestrator().analyze(
            StoryboardScene(
                scene_number=1,
                text=""
            )
        )

        self.assertEqual(
            result.status,
            ResolutionStatus.BLOCKED
        )

    def test_aggregates_trace_and_fingerprint(self):
        result = VisualAnalysisOrchestrator().analyze(
            analysis_scene()
        )

        self.assertTrue(
            result.trace.entries
        )
        self.assertTrue(
            result.trace.evidences
        )
        self.assertTrue(
            result.fingerprint
        )

    def test_repeated_analysis_is_deterministic(self):
        orchestrator = VisualAnalysisOrchestrator()
        first = orchestrator.analyze(
            analysis_scene()
        )
        second = orchestrator.analyze(
            analysis_scene()
        )

        self.assertEqual(
            first,
            second
        )
        self.assertEqual(
            first.fingerprint,
            second.fingerprint
        )

    def test_structurally_equivalent_inputs_have_same_result(self):
        first_scene = analysis_scene()
        second_scene = StoryboardScene(
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
            visual_constraints=(
                "sin texto legible",
            ),
        )

        first = VisualAnalysisOrchestrator().analyze(
            first_scene
        )
        second = VisualAnalysisOrchestrator().analyze(
            second_scene
        )

        self.assertEqual(
            first.fingerprint,
            second.fingerprint
        )

    def test_input_is_not_mutated(self):
        scene = analysis_scene()
        original = scene

        VisualAnalysisOrchestrator().analyze(
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

    def test_rejects_invalid_input(self):
        with self.assertRaises(
            TypeError
        ):
            VisualAnalysisOrchestrator().analyze(
                {
                    "visible_subject": "persona",
                }
            )

    def test_visual_analysis_layer_has_no_forbidden_dependencies(self):
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
            "app.visual_intelligence",
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

    def test_no_future_phase_resolvers_are_implemented(self):
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
            "SceneIntentResolver",
            "VisualStrategyResolver",
            "SequenceContinuityResolver",
            "VisualConflictResolver",
            "EffectiveVisualBriefSynthesizer",
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
