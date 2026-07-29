import inspect
import unittest
from pathlib import Path

from app.backend_adapters import ComfyUIAdapter
from app.cinematic_direction import CinematicDirectionOrchestrator
from app.domain import StoryboardScene, VisualSynthesisResult
from app.modules.images.image_builder import ImageBuilder
from app.prompt_translation import PromptTranslator


def certification_scene() -> StoryboardScene:
    return StoryboardScene(
        scene_number=7,
        text="Una investigadora recibe una llave antigua en un archivo.",
        visible_subject="investigadora con abrigo gris",
        visible_action="recibe una llave antigua",
        visible_environment="archivo subterraneo silencioso",
        time_context="noche lluviosa",
        key_objects=(
            "llave antigua",
            "sobre lacrado",
        ),
        spatial_relationships=(
            "la llave queda suspendida entre ambas manos",
        ),
        continuity_links=(
            "misma investigadora",
            "misma llave antigua",
        ),
        abstract_source="confianza entregada",
        filmable_interpretation="una llave antigua cambia de manos en silencio",
        visual_constraints=(
            "sin texto legible",
            "sin logos",
        ),
        visual_truth_status="structured",
    )


def certified_pipeline_outputs():
    scene = certification_scene()
    builder = ImageBuilder()
    synthesis_result = builder._build_runtime_visual_synthesis_result(
        storyboard_scene=scene,
        profile={
            "format": "horizontal",
        },
    )
    direction_set = CinematicDirectionOrchestrator().resolve(
        synthesis_result.brief
    )
    backend_prompt = PromptTranslator().translate_visual_synthesis_result(
        synthesis_result,
        cinematic_direction_set=direction_set,
    )
    payload = ComfyUIAdapter().adapt(
        backend_prompt
    )
    return synthesis_result, direction_set, backend_prompt, payload


class VisualIntelligenceRuntimeCertificationTest(unittest.TestCase):

    def test_visual_synthesis_result_governs_runtime_end_to_end(self):
        synthesis_result, direction_set, backend_prompt, payload = (
            certified_pipeline_outputs()
        )

        self.assertIsInstance(
            synthesis_result,
            VisualSynthesisResult,
        )
        self.assertEqual(
            "investigadora con abrigo gris",
            synthesis_result.brief.primary_identity,
        )
        self.assertTrue(
            synthesis_result.trace.fingerprint,
        )
        self.assertEqual(
            synthesis_result.brief.fingerprint,
            backend_prompt.trace.source_effective_brief_fingerprint,
        )
        self.assertEqual(
            backend_prompt.fingerprint,
            payload.trace.source_backend_prompt_fingerprint,
        )
        self.assertTrue(
            direction_set.fingerprint,
        )
        self.assertTrue(
            payload.fingerprint,
        )

    def test_traceability_reaches_backend_payload(self):
        _, _, _, payload = certified_pipeline_outputs()

        source_fields = {
            source_field
            for item in payload.trace.items
            for source_field in item.source_fields
        }

        self.assertIn(
            "VisualSynthesisResult.brief.primary_identity",
            source_fields,
        )
        self.assertIn(
            "VisualSynthesisResult.brief.visual_priorities",
            source_fields,
        )
        self.assertTrue(
            any(
                source_field.startswith(
                    "CinematicDirectionSet."
                )
                for source_field in source_fields
            )
        )

    def test_pipeline_is_deterministic(self):
        first = certified_pipeline_outputs()
        second = certified_pipeline_outputs()

        for first_item, second_item in zip(
            first,
            second
        ):
            with self.subTest(
                item=type(
                    first_item
                ).__name__
            ):
                self.assertEqual(
                    first_item,
                    second_item,
                )
                self.assertEqual(
                    first_item.fingerprint,
                    second_item.fingerprint,
                )

    def test_runtime_has_single_visual_synthesis_entry_point(self):
        source = inspect.getsource(
            ImageBuilder
        )

        self.assertIn(
            "_build_runtime_visual_synthesis_result",
            source,
        )
        self.assertIn(
            "translate_visual_synthesis_result",
            source,
        )
        for forbidden in (
            "_build_runtime_effective_brief",
            "_runtime_effective_brief_fingerprint",
            "Visual" + "BriefTrace",
            "Visual" + "BriefFieldOrigin",
            "Visual" + "DirectionConflict",
        ):
            with self.subTest(
                forbidden=forbidden
            ):
                self.assertNotIn(
                    forbidden,
                    source,
                )

    def test_no_parallel_contracts_or_inverse_adapters_exist(self):
        app_sources = {
            path.as_posix(): path.read_text(
                encoding="utf-8"
            )
            for path in Path(
                "app"
            ).rglob(
                "*.py"
            )
        }

        class_definitions = tuple(
            path
            for path, source in app_sources.items()
            if any(
                line.strip() == "class EffectiveVisualBrief:"
                for line in source.splitlines()
            )
        )
        self.assertEqual(
            (
                "app/domain/visual_intelligence.py",
            ),
            class_definitions,
        )

        for forbidden in (
            "VisualIntelligenceRuntimeAdapter",
            "RuntimeVisualIntelligenceAdapter",
            "EffectiveVisualBriefAdapter",
        ):
            with self.subTest(
                forbidden=forbidden
            ):
                self.assertFalse(
                    any(
                        forbidden in source
                        for source in app_sources.values()
                    )
                )

    def test_prompt_backend_and_quality_layers_do_not_run_visual_intelligence(self):
        forbidden = (
            "VisualAnalysisOrchestrator",
            "VisualReasoningOrchestrator",
            "VisualSynthesisOrchestrator",
        )
        for root in (
            "app/prompt_translation",
            "app/backend_adapters",
            "app/visual_quality",
        ):
            for path in Path(
                root
            ).rglob(
                "*.py"
            ):
                source = path.read_text(
                    encoding="utf-8"
                )
                for item in forbidden:
                    with self.subTest(
                        path=path.as_posix(),
                        item=item,
                    ):
                        self.assertNotIn(
                            item,
                            source,
                        )


if __name__ == "__main__":
    unittest.main()
