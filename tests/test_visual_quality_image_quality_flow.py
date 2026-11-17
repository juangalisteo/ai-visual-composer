import inspect
import tempfile
import unittest
from pathlib import Path

from app.visual_quality import (
    ImageQualityFlowCoordinator,
    RegenerationPolicy,
    ValidationCheck,
    create_validation_failure,
)


class FailureCheck(ValidationCheck):
    name = "text_detected"
    check_category = "semantic"

    def __init__(
        self,
        severity="high",
        retry_relevant=True
    ):
        self.severity = severity
        self.retry_relevant = retry_relevant

    def check(
        self,
        asset,
        context
    ):
        return (
            create_validation_failure(
                failure_type="text_detected",
                severity=self.severity,
                confidence=0.9,
                evidence="visible marks",
                technical_message="detected visible text",
                retry_relevant=self.retry_relevant,
            ),
        )


NUDENET_MODEL_AVAILABLE = (
    Path(__file__).resolve().parents[1] / "models" / "visual_safety" / "nudenet-320n.onnx"
).is_file()
NUDENET_MODEL_REASON = "Falta el modelo NudeNet en models/visual_safety/."


class ImageQualityFlowCoordinatorTest(unittest.TestCase):

    @unittest.skipUnless(NUDENET_MODEL_AVAILABLE, NUDENET_MODEL_REASON)
    def test_approved_flow_creates_approved_asset_and_history(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(
                temp_dir
            ) / "scene_001.png"
            from PIL import Image

            Image.new("RGB", (1024, 576)).save(image_path)
            result = ImageQualityFlowCoordinator().evaluate(
                image_path=image_path,
                scene_number=1,
                width=1024,
                height=576
            )

        self.assertEqual(
            result.status,
            "approved"
        )
        self.assertIsNotNone(
            result.approved_asset
        )
        self.assertIsNone(
            result.manual_review_marker
        )
        self.assertEqual(
            result.history.status,
            "accepted"
        )
        self.assertEqual(
            result.history.approved_asset,
            result.approved_asset
        )

    def test_retry_requested_does_not_execute_retry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(
                temp_dir
            ) / "scene_001.png"
            image_path.write_bytes(
                b"image"
            )
            result = ImageQualityFlowCoordinator(
                validator=_validator_with(
                    FailureCheck()
                ),
                policy=RegenerationPolicy()
            ).evaluate(
                image_path=image_path,
                scene_number=1,
                width=1024,
                height=576,
                attempt_number=1
            )

        self.assertEqual(
            result.status,
            "retry_requested"
        )
        self.assertIsNone(
            result.approved_asset
        )
        self.assertIsNone(
            result.manual_review_marker
        )
        self.assertEqual(
            result.history.status,
            "generating"
        )
        self.assertEqual(
            len(
                result.history.generated_assets
            ),
            1
        )

    def test_manual_review_flow_creates_marker_and_history(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(
                temp_dir
            ) / "scene_001.png"
            image_path.write_bytes(
                b"image"
            )
            result = ImageQualityFlowCoordinator(
                validator=_validator_with(
                    FailureCheck()
                ),
                policy=RegenerationPolicy()
            ).evaluate(
                image_path=image_path,
                scene_number=1,
                width=1024,
                height=576,
                attempt_number=3
            )

        self.assertEqual(
            result.status,
            "manual_review"
        )
        self.assertIsNone(
            result.approved_asset
        )
        self.assertIsNotNone(
            result.manual_review_marker
        )
        self.assertEqual(
            result.history.status,
            "manual_review"
        )

    def test_stopped_flow_updates_history_without_manual_marker(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(
                temp_dir
            ) / "scene_001.png"
            image_path.write_bytes(
                b"image"
            )
            result = ImageQualityFlowCoordinator(
                validator=_validator_with(
                    FailureCheck(
                        severity="critical",
                        retry_relevant=False
                    )
                ),
                policy=RegenerationPolicy()
            ).evaluate(
                image_path=image_path,
                scene_number=1,
                width=1024,
                height=576
            )

        self.assertEqual(
            result.status,
            "stopped"
        )
        self.assertIsNone(
            result.approved_asset
        )
        self.assertIsNone(
            result.manual_review_marker
        )
        self.assertEqual(
            result.history.status,
            "stopped"
        )

    def test_flow_is_deterministic(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(
                temp_dir
            ) / "scene_001.png"
            image_path.write_bytes(
                b"image"
            )
            coordinator = ImageQualityFlowCoordinator()
            first = coordinator.evaluate(
                image_path=image_path,
                scene_number=1,
                width=1024,
                height=576
            )
            second = coordinator.evaluate(
                image_path=image_path,
                scene_number=1,
                width=1024,
                height=576
            )

        self.assertEqual(
            first,
            second
        )
        self.assertEqual(
            first.result_fingerprint,
            second.result_fingerprint
        )

    def test_required_checks_are_taken_from_validator(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(
                temp_dir
            ) / "scene_001.png"
            image_path.write_bytes(
                b"image"
            )
            result = ImageQualityFlowCoordinator(
                validator=_validator_with(
                    FailureCheck()
                )
            ).evaluate(
                image_path=image_path,
                scene_number=1,
                width=1024,
                height=576
            )

        self.assertEqual(
            result.history.validation_reports[0].checks,
            (
                "text_detected",
            )
        )

    def test_flow_has_no_backend_runtime_or_prompt_dependencies(self):
        source = inspect.getsource(
            __import__(
                "app.visual_quality.image_quality_flow",
                fromlist=[
                    "x"
                ]
            )
        )
        forbidden = (
            "PromptTranslator",
            "BackendPrompt",
            "ComfyUI",
            "ComfyUIBackend",
            "ImageBuilder",
            "ImagePromptSystem",
            "ImageManifestWriter",
            "CinematicDirection",
            "EffectiveVisualBrief",
            "requests",
            "urllib",
            "workflow",
            "payload",
            "manifest",
        )

        for item in forbidden:
            with self.subTest(
                item=item
            ):
                self.assertNotIn(
                    item,
                    source
                )


def _validator_with(
    *checks
):
    from app.visual_quality import ImageValidator

    return ImageValidator(
        checks=tuple(
            checks
        )
    )


if __name__ == "__main__":
    unittest.main()
