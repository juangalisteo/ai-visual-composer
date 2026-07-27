import inspect
import unittest
from dataclasses import asdict

from app.visual_quality import (
    AnatomyCheck,
    IdentityCheck,
    ImageValidator,
    LogoCheck,
    TextCheck,
    ValidationCheck,
    ValidationCheckError,
    VisionAnalysis,
    VisionEngine,
    WardrobeCheck,
    create_generated_asset,
    create_validation_context,
    create_validation_failure,
)


def generated_asset():
    return create_generated_asset(
        asset_id="asset-1",
        scene_id="scene-001",
        sequence_id="sequence-001",
        asset_type="image",
        path="scene_001.png",
        attempt_number=1,
        generation_attempt_id="scene-001-attempt-1",
        width=1024,
        height=576,
    )


def validation_context():
    return create_validation_context(
        scene_id="scene-001",
        sequence_id="sequence-001",
        validation_profile="image-v1",
        required_checks=(
            "text_detected",
            "logo_detected",
        ),
    )


class RecordingCheck(ValidationCheck):
    def __init__(
        self,
        name,
        events,
        failures=()
    ):
        self.name = name
        self.events = events
        self.failures = tuple(
            failures
        )

    def check(
        self,
        asset,
        context
    ):
        self.events.append(
            self.name
        )
        return self.failures


class FailingCheck(ValidationCheck):
    name = "failing_check"

    def check(
        self,
        asset,
        context
    ):
        raise ValidationCheckError(
            self.name,
            "controlled checker failure"
        )


class DummyVisionEngine(VisionEngine):
    def analyze(
        self,
        asset,
        context,
        check_name
    ):
        return VisionAnalysis(
            check_name=check_name,
            observations=(
                (
                    "status",
                    "not used yet",
                ),
            ),
        )


class ImageValidatorTest(unittest.TestCase):

    def test_initial_checkers_return_no_failures(self):
        asset = generated_asset()
        context = validation_context()
        for check in (
            TextCheck(),
            LogoCheck(),
            AnatomyCheck(),
            WardrobeCheck(),
            IdentityCheck(),
        ):
            with self.subTest(
                check=check.name
            ):
                self.assertEqual(
                    (),
                    check.check(
                        asset,
                        context
                    )
                )

    def test_validator_executes_all_checks_in_stable_order(self):
        events = []
        validator = ImageValidator(
            checks=(
                RecordingCheck(
                    "first",
                    events
                ),
                RecordingCheck(
                    "second",
                    events
                ),
            )
        )
        validator.validate(
            generated_asset(),
            validation_context()
        )

        self.assertEqual(
            events,
            [
                "first",
                "second",
            ]
        )

    def test_empty_checks_produce_accepted_report(self):
        report = ImageValidator(
            checks=()
        ).validate(
            generated_asset(),
            validation_context()
        )

        self.assertEqual(
            report.status,
            "accepted"
        )
        self.assertEqual(
            report.score,
            1.0
        )
        self.assertEqual(
            report.failures,
            ()
        )

    def test_checker_failures_are_propagated_to_report(self):
        failure = create_validation_failure(
            failure_type="text_detected",
            severity="high",
            confidence=0.9,
            evidence="visible marks",
            technical_message="detected visible text",
            retry_relevant=True,
        )
        report = ImageValidator(
            checks=(
                RecordingCheck(
                    "text_detected",
                    [],
                    failures=(
                        failure,
                    )
                ),
            )
        ).validate(
            generated_asset(),
            validation_context()
        )

        self.assertEqual(
            report.status,
            "rejected"
        )
        self.assertEqual(
            report.failures,
            (
                failure,
            )
        )
        self.assertEqual(
            report.severity,
            "high"
        )

    def test_checker_can_return_multiple_failures(self):
        text_failure = create_validation_failure(
            failure_type="text_detected",
            severity="medium",
            confidence=0.8,
            evidence="glyphs",
            technical_message="text-like glyphs",
            retry_relevant=True,
        )
        logo_failure = create_validation_failure(
            failure_type="logo_detected",
            severity="high",
            confidence=0.85,
            evidence="uniform mark",
            technical_message="logo-like mark",
            retry_relevant=True,
        )
        report = ImageValidator(
            checks=(
                RecordingCheck(
                    "compound",
                    [],
                    failures=(
                        text_failure,
                        logo_failure,
                    )
                ),
            )
        ).validate(
            generated_asset(),
            validation_context()
        )

        self.assertEqual(
            len(
                report.failures
            ),
            2
        )
        self.assertEqual(
            report.severity,
            "high"
        )

    def test_controlled_checker_exception_produces_uncertain_report(self):
        report = ImageValidator(
            checks=(
                FailingCheck(),
            )
        ).validate(
            generated_asset(),
            validation_context()
        )

        self.assertEqual(
            report.status,
            "uncertain"
        )
        self.assertTrue(
            report.requires_manual_review
        )
        self.assertEqual(
            report.failures[0].failure_type,
            "scene_mismatch"
        )
        self.assertFalse(
            report.failures[0].retry_relevant
        )

    def test_report_contains_executed_checks(self):
        report = ImageValidator(
            checks=(
                TextCheck(),
                LogoCheck(),
            )
        ).validate(
            generated_asset(),
            validation_context()
        )

        self.assertEqual(
            report.checks,
            (
                "text_detected",
                "logo_detected",
            )
        )

    def test_validator_is_deterministic(self):
        checks = (
            TextCheck(),
            LogoCheck(),
        )
        first = ImageValidator(
            checks=checks
        ).validate(
            generated_asset(),
            validation_context()
        )
        second = ImageValidator(
            checks=checks
        ).validate(
            generated_asset(),
            validation_context()
        )

        self.assertEqual(
            first,
            second
        )
        self.assertEqual(
            first.validation_fingerprint,
            second.validation_fingerprint
        )

    def test_report_is_serializable_with_asdict(self):
        report = ImageValidator(
            checks=(
                TextCheck(),
            )
        ).validate(
            generated_asset(),
            validation_context()
        )
        serialized = asdict(
            report
        )

        self.assertEqual(
            serialized["asset_id"],
            "asset-1"
        )
        self.assertEqual(
            serialized["checks"],
            (
                "text_detected",
            )
        )

    def test_vision_engine_interface_is_abstract_and_backend_neutral(self):
        with self.assertRaises(
            TypeError
        ):
            VisionEngine()
        analysis = DummyVisionEngine().analyze(
            generated_asset(),
            validation_context(),
            "text_detected"
        )

        self.assertEqual(
            analysis.check_name,
            "text_detected"
        )

    def test_validator_rejects_empty_version(self):
        with self.assertRaises(
            ValueError
        ):
            ImageValidator(
                checks=(),
                validator_version=""
            )

    def test_image_validator_has_no_runtime_backend_or_prompt_dependencies(self):
        source = inspect.getsource(
            __import__(
                "app.visual_quality.image_validator",
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


if __name__ == "__main__":
    unittest.main()
