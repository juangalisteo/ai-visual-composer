import inspect
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.cinematic_direction import create_cinematic_direction_set
from app.domain import StoryboardScene, VisualSynthesisResult
from app.modules.images.image_builder import ImageBuilder
from app.photography_direction import PhotographyDirection
from app.prompt_translation import BackendPrompt, BackendPromptTrace
from app.visual_quality import (
    ImageQualityFlowCoordinator,
    ImageValidator,
    ValidationCheck,
    create_validation_failure,
)


class FailingImageQualityFlow:

    def evaluate(
        self,
        *args,
        **kwargs
    ):
        raise AssertionError(
            "image validation should be disabled"
        )


class RecordingImageQualityFlow:

    def __init__(
        self,
        status="approved"
    ):
        self.status = status
        self.calls = []

    def evaluate(
        self,
        **kwargs
    ):
        self.calls.append(
            kwargs
        )
        return SimpleNamespace(
            status=self.status,
            generated_asset=SimpleNamespace(
                attempt_number=1
            )
        )


class FailUntilAttemptCheck(ValidationCheck):
    name = "text_detected"
    check_category = "semantic"

    def __init__(
        self,
        accepted_attempt
    ):
        self.accepted_attempt = accepted_attempt

    def check(
        self,
        asset,
        context
    ):
        if asset.attempt_number >= self.accepted_attempt:
            return ()
        return (
            create_validation_failure(
                failure_type="text_detected",
                severity="high",
                confidence=0.9,
                evidence="visible marks",
                technical_message="detected visible text",
                retry_relevant=True,
            ),
        )


class RecordingCinematicOrchestrator:

    def __init__(
        self
    ):
        self.effective_briefs = []
        self.direction_set = create_cinematic_direction_set(
            photography=PhotographyDirection(
                dominant_photographic_language="observational intimacy",
                fingerprint="photography-fingerprint"
            )
        )

    def resolve(
        self,
        effective_brief
    ):
        self.effective_briefs.append(
            effective_brief
        )
        return self.direction_set


class RecordingPromptTranslator:

    def __init__(
        self
    ):
        self.calls = []

    def translate(
        self,
        effective_brief,
        cinematic_direction_set=None,
    ):
        raise AssertionError(
            "ImageBuilder must translate from VisualSynthesisResult"
        )

    def translate_visual_synthesis_result(
        self,
        visual_synthesis_result,
        cinematic_direction_set=None,
    ):
        self.calls.append(
            (
                visual_synthesis_result,
                cinematic_direction_set,
            )
        )
        return BackendPrompt(
            instructions=(),
            trace=BackendPromptTrace(
                source_effective_brief_fingerprint=(
                    visual_synthesis_result.brief.fingerprint
                )
            ),
            fingerprint="backend-prompt-fingerprint"
        )


class RecordingBackendAdapter:

    def __init__(
        self
    ):
        self.backend_prompts = []

    def adapt(
        self,
        backend_prompt
    ):
        self.backend_prompts.append(
            backend_prompt
        )
        return SimpleNamespace(
            prompt="cinematic operative prompt",
            fingerprint="payload-fingerprint"
        )


class ImageBuilderCinematicRuntimeTest(unittest.TestCase):

    def test_build_invokes_single_cinematic_runtime_by_default(self):
        orchestrator = RecordingCinematicOrchestrator()
        translator = RecordingPromptTranslator()
        backend_adapter = RecordingBackendAdapter()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            storyboard_path = self._write_storyboard(
                root
            )
            manifest_path = root / "images_manifest.json"
            output_dir = root / "images"
            workflow_path = self._write_workflow(
                root
            )

            with self._patched_environment(
                manifest_path=manifest_path
            ):
                builder = ImageBuilder(
                    workflow_path=workflow_path,
                    cinematic_orchestrator=orchestrator,
                    prompt_translator=translator,
                    backend_adapter=backend_adapter,
                    image_quality_flow=FailingImageQualityFlow()
                )

                with patch.object(
                    ImageBuilder,
                    "_generate_image",
                    side_effect=self._fake_generate_image
                ):
                    builder.build(
                        storyboard_path=storyboard_path,
                        output_dir=output_dir
                    )

            manifest = json.loads(
                manifest_path.read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                {
                    "scene",
                    "prompt",
                    "positive_prompt",
                    "negative_prompt",
                    "visual_director",
                    "image",
                    "width",
                    "height",
                    "duration"
                },
                set(
                    manifest[0]
                )
            )
            self.assertIn(
                "cinematic operative prompt",
                manifest[0]["prompt"]
            )
            self.assertEqual(
                1,
                len(orchestrator.effective_briefs)
            )
            self.assertEqual(
                1,
                len(translator.calls)
            )
            self.assertEqual(
                1,
                len(backend_adapter.backend_prompts)
            )

    def test_image_validation_disabled_by_default_does_not_invoke_quality_flow(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            storyboard_path = self._write_storyboard(
                root
            )
            manifest_path = root / "images_manifest.json"
            output_dir = root / "images"
            workflow_path = self._write_workflow(
                root
            )

            with self._patched_environment(
                manifest_path=manifest_path
            ):
                builder = ImageBuilder(
                    workflow_path=workflow_path,
                    image_quality_flow=FailingImageQualityFlow()
                )

                with patch.object(
                    ImageBuilder,
                    "_generate_image",
                    side_effect=self._fake_generate_image
                ):
                    builder.build(
                        storyboard_path=storyboard_path,
                        output_dir=output_dir
                    )

            self.assertTrue(
                manifest_path.exists()
            )

    def test_build_persists_visual_intelligence_evidence_without_manifest_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            storyboard_path = self._write_storyboard(
                root
            )
            manifest_path = root / "images_manifest.json"
            output_dir = root / "images"
            workflow_path = self._write_workflow(
                root
            )

            with self._patched_environment(
                manifest_path=manifest_path
            ):
                builder = ImageBuilder(
                    workflow_path=workflow_path,
                    image_quality_flow=FailingImageQualityFlow()
                )

                with patch.object(
                    ImageBuilder,
                    "_generate_image",
                    side_effect=self._fake_generate_image
                ):
                    builder.build(
                        storyboard_path=storyboard_path,
                        output_dir=output_dir
                    )

            evidence_path = (
                output_dir
                / "evidence"
                / "scene_001"
                / "visual_analysis_result.json"
            )
            reasoning_path = (
                output_dir
                / "evidence"
                / "scene_001"
                / "visual_reasoning_result.json"
            )
            conflicts_path = (
                output_dir
                / "evidence"
                / "scene_001"
                / "visual_conflict_report.json"
            )
            brief_path = (
                output_dir
                / "evidence"
                / "scene_001"
                / "effective_visual_brief.json"
            )
            synthesis_path = (
                output_dir
                / "evidence"
                / "scene_001"
                / "visual_synthesis_result.json"
            )
            prompt_observation_path = (
                output_dir
                / "evidence"
                / "scene_001"
                / "prompt_translation_observation.json"
            )
            index_path = (
                output_dir
                / "evidence"
                / "scene_001"
                / "evidence_index.json"
            )
            manifest = json.loads(
                manifest_path.read_text(
                    encoding="utf-8"
                )
            )

            self.assertTrue(
                evidence_path.exists()
            )
            self.assertTrue(
                reasoning_path.exists()
            )
            self.assertTrue(
                conflicts_path.exists()
            )
            self.assertTrue(
                brief_path.exists()
            )
            self.assertTrue(
                synthesis_path.exists()
            )
            self.assertTrue(
                prompt_observation_path.exists()
            )
            self.assertTrue(
                index_path.exists()
            )
            self.assertEqual(
                {
                    "scene",
                    "prompt",
                    "positive_prompt",
                    "negative_prompt",
                    "visual_director",
                    "image",
                    "width",
                    "height",
                    "duration"
                },
                set(
                    manifest[0]
                )
            )

    def test_image_validation_enabled_invokes_quality_flow(self):
        quality_flow = RecordingImageQualityFlow()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            storyboard_path = self._write_storyboard(
                root
            )
            manifest_path = root / "images_manifest.json"
            output_dir = root / "images"
            workflow_path = self._write_workflow(
                root
            )

            with self._patched_environment(
                manifest_path=manifest_path,
                image_validation_enabled=True
            ):
                builder = ImageBuilder(
                    workflow_path=workflow_path,
                    image_quality_flow=quality_flow
                )

                with patch.object(
                    ImageBuilder,
                    "_generate_image",
                    side_effect=self._fake_generate_image
                ):
                    builder.build(
                        storyboard_path=storyboard_path,
                        output_dir=output_dir
                    )

        self.assertEqual(
            1,
            len(
                quality_flow.calls
            )
        )
        self.assertEqual(
            1,
            quality_flow.calls[0]["scene_number"]
        )
        self.assertEqual(
            640,
            quality_flow.calls[0]["width"]
        )

    def test_image_validation_blocks_non_approved_flow_result(self):
        quality_flow = RecordingImageQualityFlow(
            status="manual_review"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            storyboard_path = self._write_storyboard(
                root
            )
            manifest_path = root / "images_manifest.json"
            output_dir = root / "images"
            workflow_path = self._write_workflow(
                root
            )

            with self._patched_environment(
                manifest_path=manifest_path,
                image_validation_enabled=True
            ):
                builder = ImageBuilder(
                    workflow_path=workflow_path,
                    image_quality_flow=quality_flow
                )

                with patch.object(
                    ImageBuilder,
                    "_generate_image",
                    side_effect=self._fake_generate_image
                ):
                    with self.assertRaises(
                        RuntimeError
                    ):
                        builder.build(
                            storyboard_path=storyboard_path,
                            output_dir=output_dir
                        )

    def test_image_validation_retry_uses_approved_retry_path_in_manifest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            storyboard_path = self._write_storyboard(
                root
            )
            manifest_path = root / "images_manifest.json"
            output_dir = root / "images"
            workflow_path = self._write_workflow(
                root
            )

            with self._patched_environment(
                manifest_path=manifest_path,
                image_validation_enabled=True
            ):
                builder = ImageBuilder(
                    workflow_path=workflow_path,
                    image_quality_flow=ImageQualityFlowCoordinator(
                        validator=ImageValidator(
                            checks=(
                                FailUntilAttemptCheck(
                                    accepted_attempt=2
                                ),
                            )
                        )
                    )
                )

                with patch.object(
                    ImageBuilder,
                    "_generate_image",
                    side_effect=self._fake_generate_image
                ):
                    builder.build(
                        storyboard_path=storyboard_path,
                        output_dir=output_dir
                    )

            manifest = json.loads(
                manifest_path.read_text(
                    encoding="utf-8"
                )
            )

        self.assertIn(
            "_quality_attempts",
            manifest[0]["image"]
        )
        self.assertIn(
            "attempt_002",
            manifest[0]["image"]
        )

    def test_runtime_invokes_orchestrator_and_prompt_translator(self):
        orchestrator = RecordingCinematicOrchestrator()
        translator = RecordingPromptTranslator()
        backend_adapter = RecordingBackendAdapter()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            storyboard_path = self._write_storyboard(
                root
            )
            manifest_path = root / "images_manifest.json"
            output_dir = root / "images"
            workflow_path = self._write_workflow(
                root
            )

            with self._patched_environment(
                manifest_path=manifest_path
            ):
                builder = ImageBuilder(
                    workflow_path=workflow_path,
                    cinematic_orchestrator=orchestrator,
                    prompt_translator=translator,
                    backend_adapter=backend_adapter
                )

                with patch.object(
                    ImageBuilder,
                    "_generate_image",
                    side_effect=self._fake_generate_image
                ):
                    builder.build(
                        storyboard_path=storyboard_path,
                        output_dir=output_dir
                    )

            manifest = json.loads(
                manifest_path.read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(
            1,
            len(
                orchestrator.effective_briefs
            )
        )
        self.assertEqual(
            1,
            len(
                translator.calls
            )
        )
        self.assertEqual(
            1,
            len(
                backend_adapter.backend_prompts
            )
        )

        visual_synthesis_result, direction_set = (
            translator.calls[0]
        )

        self.assertIsInstance(
            visual_synthesis_result,
            VisualSynthesisResult
        )
        self.assertIs(
            direction_set,
            orchestrator.direction_set
        )
        self.assertEqual(
            "quiet valley | dawn light spreads slowly | mountain landscape | dawn",
            visual_synthesis_result.brief.visible_content
        )
        self.assertTrue(
            visual_synthesis_result.trace.fingerprint
        )
        self.assertIn(
            "VisualTruthInspector",
            {
                entry.component
                for trace in visual_synthesis_result.trace.traces
                for entry in trace.entries
            },
        )
        self.assertEqual(
            "backend-prompt-fingerprint",
            backend_adapter.backend_prompts[0].fingerprint
        )
        self.assertIn(
            "cinematic operative prompt",
            manifest[0]["prompt"]
        )
        self.assertIn(
            "professional cinematic realism",
            manifest[0]["prompt"]
        )
        self.assertIn(
            "no text",
            manifest[0]["prompt"]
        )
        self.assertEqual(
            "backend-prompt-fingerprint",
            builder._build_cinematic_runtime_metadata(
                storyboard_scene=StoryboardScene(
                    scene_number=1,
                    text="La escena conserva su texto.",
                    visible_subject="quiet valley",
                    visible_action="dawn light spreads slowly",
                    visible_environment="mountain landscape",
                    filmable_interpretation="A quiet dawn over a valley",
                    visual_truth_status="structured",
                )
            )["backend_prompt_fingerprint"]
        )

    def test_cinematic_metadata_records_backend_adapter_traceability(self):
        builder = ImageBuilder(
            cinematic_orchestrator=RecordingCinematicOrchestrator(),
            prompt_translator=RecordingPromptTranslator(),
            backend_adapter=RecordingBackendAdapter()
        )

        metadata = builder._build_cinematic_runtime_metadata(
            storyboard_scene=StoryboardScene(
                scene_number=1,
                text="La escena conserva su texto.",
                visible_subject="quiet valley",
                visible_action="dawn light spreads slowly",
                visible_environment="mountain landscape",
                filmable_interpretation="A quiet dawn over a valley",
                visual_truth_status="structured",
            )
        )

        self.assertEqual(
            "payload-fingerprint",
            metadata["backend_adapter_payload_fingerprint"]
        )
        self.assertTrue(
            metadata["visual_synthesis_result_fingerprint"]
        )
        self.assertTrue(
            metadata["visual_intelligence_trace_fingerprint"]
        )
        self.assertTrue(
            metadata["visual_conflict_report_fingerprint"]
        )
        self.assertIn(
            "cinematic operative prompt",
            metadata["operational_prompt"]
        )
        self.assertIn(
            "natural anatomy",
            metadata["operational_prompt"]
        )
        self.assertIn(
            "no text on books",
            metadata["operational_prompt"]
        )
        self.assertEqual(
            "cinematic operative prompt",
            metadata["backend_payload_prompt"]
        )

    def test_runtime_visual_synthesis_result_preserves_visual_truth_trace(self):
        builder = ImageBuilder()

        synthesis_result = builder._build_runtime_visual_synthesis_result(
            storyboard_scene=StoryboardScene(
                scene_number=9,
                text="Una idea invisible se vuelve accion.",
                visible_subject="investigadora con abrigo gris",
                visible_action="recibe una llave antigua",
                visible_environment="archivo subterraneo",
                time_context="noche",
                key_objects=(
                    "llave antigua",
                ),
                spatial_relationships=(
                    "la llave queda entre ambas manos",
                ),
                continuity_links=(
                    "misma llave antigua",
                ),
                filmable_interpretation=(
                    "una llave cambia de manos en silencio"
                ),
                visual_constraints=(
                    "sin texto legible",
                ),
                visual_truth_status="structured",
            ),
            profile={
                "format": "horizontal",
            },
        )

        self.assertEqual(
            "investigadora con abrigo gris | recibe una llave antigua | archivo subterraneo | noche",
            synthesis_result.brief.visible_content,
        )
        self.assertEqual(
            (
                "llave antigua",
            ),
            synthesis_result.brief.key_objects,
        )
        sources = {
            evidence.source.field
            for evidence in synthesis_result.trace.evidences
        }

        self.assertIn(
            "visible_subject",
            sources,
        )
        self.assertIn(
            "key_objects",
            sources,
        )
        self.assertTrue(
            synthesis_result.trace.fingerprint,
        )
    def test_runtime_visual_synthesis_result_fingerprint_is_deterministic(self):
        builder = ImageBuilder()
        storyboard_scene = StoryboardScene(
            scene_number=1,
            text="La escena conserva su texto.",
            visible_subject="quiet valley",
            visible_action="dawn light spreads slowly",
            visible_environment="mountain landscape",
            filmable_interpretation="A quiet dawn over a valley",
            visual_truth_status="structured",
        )

        first = builder._build_runtime_visual_synthesis_result(
            storyboard_scene=storyboard_scene
        )
        second = builder._build_runtime_visual_synthesis_result(
            storyboard_scene=storyboard_scene
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
            first.fingerprint
        )

    def test_runtime_knows_only_cinematic_orchestrator_not_individual_directions(self):
        source = inspect.getsource(
            ImageBuilder
        )

        self.assertIn(
            "CinematicDirectionOrchestrator",
            source
        )

        for forbidden in (
            "PhotographyDirector",
            "LightingDirector",
            "CompositionDirector",
            "ColorDirector",
            "MovementDirector",
            "ContinuityDirector",
        ):
            with self.subTest(
                forbidden=forbidden
            ):
                self.assertNotIn(
                    forbidden,
                    source
                )

    def _write_storyboard(
        self,
        root
    ):
        storyboard_path = root / "storyboard.json"
        storyboard_path.write_text(
            json.dumps(
                [
                    {
                        "scene": 1,
                        "text": "La escena conserva su texto.",
                        "visible_subject": "quiet valley",
                        "visible_action": "dawn light spreads slowly",
                        "visible_environment": "mountain landscape",
                        "time_context": "dawn",
                        "key_objects": [
                            "mist",
                        ],
                        "spatial_relationships": [
                            "mist rests below the ridge",
                        ],
                        "continuity_links": [],
                        "abstract_source": "beginning",
                        "filmable_interpretation": (
                            "A quiet dawn over a valley"
                        ),
                        "visual_constraints": [
                            "no readable text",
                        ],
                        "visual_truth_status": "structured",
                        "duration": 3
                    }
                ],
                ensure_ascii=False
            ),
            encoding="utf-8"
        )
        return storyboard_path

    def _write_workflow(
        self,
        root
    ):
        workflow_path = root / "workflow.json"
        workflow_path.write_text(
            "{}",
            encoding="utf-8"
        )
        return workflow_path

    def _patched_environment(
        self,
        manifest_path,
        image_validation_enabled=False
    ):
        project = SimpleNamespace(
            images_manifest_path=lambda: manifest_path
        )
        config = SimpleNamespace(
            get_profile_config=lambda: {
                "format": "horizontal",
                "video_style": {
                    "width": 640,
                    "height": 360
                },
                "visual_director": {
                    "enabled": False
                },
                "image_validation": {
                    "enabled": image_validation_enabled
                }
            }
        )

        return patch.multiple(
            "app.modules.images.image_builder",
            ProjectManager=lambda: project,
            ConfigManager=lambda: config
        )

    def _fake_generate_image(
        self,
        prompt,
        scene_number,
        output_dir,
        width,
        height
    ):
        output_dir.mkdir(
            parents=True,
            exist_ok=True
        )
        image_path = output_dir / f"scene_{scene_number:03d}.png"
        image_path.write_text(
            f"{width}x{height}\n{prompt}",
            encoding="utf-8"
        )
        return image_path


if __name__ == "__main__":
    unittest.main()
