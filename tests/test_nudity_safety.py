import tempfile
import unittest
from pathlib import Path

from app.visual_quality import (
    ImageQualityFlowCoordinator,
    ImageValidator,
    NuditySafetyCheck,
    NuditySafetyConfig,
    RegenerationPolicy,
    RetryCoordinator,
    create_generated_asset,
    create_validation_context,
)


class RecordingDetector:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.paths = []

    def detect(self, path):
        self.paths.append(path)
        return next(self.responses)


class NuditySafetyCheckTest(unittest.TestCase):
    def _asset(self, image_path, metadata=()):
        return create_generated_asset(
            asset_id="scene_001:attempt-1",
            scene_id="scene_001",
            asset_type="image",
            path=str(image_path),
            local_artifact_path=str(image_path),
            attempt_number=1,
            generation_attempt_id="scene_001:attempt-1",
            width=16,
            height=16,
            metadata=metadata,
        )

    def _context(self):
        return create_validation_context(
            scene_id="scene_001",
            validation_profile="image-v1",
        )

    def test_safe_image_returns_false_to_pipeline(self):
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "safe.png"
            image_path.write_bytes(b"pixel-input")
            detector = RecordingDetector([[]])
            check = NuditySafetyCheck(detector=detector)
            self.assertEqual(
                (),
                check.check(
                    self._asset(
                        image_path,
                        metadata=(("prompt", "preserve this value"),),
                    ),
                    self._context(),
                ),
            )
            self.assertEqual([str(image_path)], detector.paths)

    def test_only_configured_exposed_classes_trigger_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "candidate.png"
            image_path.write_bytes(b"pixel-input")
            check = NuditySafetyCheck(detector=RecordingDetector([[
                {"class": "BELLY_EXPOSED", "score": 0.99, "box": [0, 0, 2, 2]},
                {"class": "FEMALE_BREAST_EXPOSED", "score": 0.70, "box": [1, 1, 3, 3]},
            ]]))
            failures = check.check(self._asset(image_path), self._context())
            self.assertEqual(1, len(failures))
            self.assertEqual("nudity_detected", failures[0].failure_type)
            self.assertTrue(failures[0].retry_relevant)

    def test_missing_model_is_a_controlled_validator_error(self):
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "candidate.png"
            image_path.write_bytes(b"pixel-input")
            validator = ImageValidator(
                checks=(
                    NuditySafetyCheck(
                        config=NuditySafetyConfig(
                            model_path=Path(directory) / "missing.onnx"
                        )
                    ),
                )
            )
            report = validator.validate(self._asset(image_path), self._context())
            self.assertEqual("uncertain", report.status)
            self.assertTrue(report.requires_manual_review)

    def test_safe_original_is_accepted_without_regeneration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = root / "original.png"
            original.write_bytes(b"image")
            coordinator = ImageQualityFlowCoordinator(
                validator=ImageValidator(
                    checks=(NuditySafetyCheck(detector=RecordingDetector([[]])),)
                ),
            )
            calls = []

            def generate(attempt, seed):
                calls.append((attempt, seed))
                return root / f"attempt_{attempt}.png"

            result = coordinator.evaluate(
                image_path=original,
                scene_number=1,
                width=16,
                height=16,
                generate_attempt=generate,
            )
            self.assertEqual("approved", result.status)
            self.assertEqual([], calls)
            self.assertEqual(1, len(result.history.generated_assets))

    def test_two_nudity_retries_then_forced_acceptance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = root / "original.png"
            original.write_bytes(b"image")
            detector = RecordingDetector([
                [{"class": "ANUS_EXPOSED", "score": 0.9, "box": [0, 0, 1, 1]}],
                [{"class": "ANUS_EXPOSED", "score": 0.9, "box": [0, 0, 1, 1]}],
                [{"class": "ANUS_EXPOSED", "score": 0.9, "box": [0, 0, 1, 1]}],
            ])
            coordinator = ImageQualityFlowCoordinator(
                validator=ImageValidator(checks=(NuditySafetyCheck(detector=detector),)),
                policy=RegenerationPolicy(),
                retry_coordinator=RetryCoordinator(),
            )
            calls = []

            def generate(attempt, seed):
                calls.append((attempt, seed))
                path = root / f"attempt_{attempt}.png"
                path.write_bytes(b"image")
                return path

            result = coordinator.evaluate(
                image_path=original,
                scene_number=1,
                width=16,
                height=16,
                generate_attempt=generate,
            )
            self.assertEqual("approved", result.status)
            self.assertEqual([2, 3], [attempt for attempt, _ in calls])
            self.assertEqual(3, len(result.history.generated_assets))
            self.assertTrue(
                result.history.regeneration_decisions[-1].forced_accept
            )
            self.assertIn(
                "nudity_detected",
                result.history.regeneration_decisions[-1].failure_types,
            )
            self.assertEqual(
                "rejected",
                result.history.validation_reports[-1].status,
            )

    def test_safe_retry_candidate_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = root / "original.png"
            original.write_bytes(b"image")
            detector = RecordingDetector([
                [{"class": "MALE_GENITALIA_EXPOSED", "score": 0.9, "box": [0, 0, 1, 1]}],
                [],
            ])
            coordinator = ImageQualityFlowCoordinator(
                validator=ImageValidator(checks=(NuditySafetyCheck(detector=detector),)),
            )

            def generate(attempt, seed):
                path = root / f"attempt_{attempt}.png"
                path.write_bytes(b"image")
                return path

            result = coordinator.evaluate(
                image_path=original,
                scene_number=1,
                width=16,
                height=16,
                generate_attempt=generate,
            )
            self.assertEqual("approved", result.status)
            self.assertEqual(2, len(result.history.generated_assets))
