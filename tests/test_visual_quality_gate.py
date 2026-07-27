import inspect
import unittest
from dataclasses import FrozenInstanceError, asdict, is_dataclass

from app.visual_quality import (
    AssetValidator,
    RegenerationPolicy,
    VisualQualityGate,
    VisualQualityGateResult,
    create_generated_asset,
    create_validation_context,
    create_validation_failure,
    create_validation_report,
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
        ),
    )


def accepted_report():
    return create_validation_report(
        report_id="report-1",
        asset_id="asset-1",
        scene_id="scene-001",
        status="accepted",
        score=1.0,
        checks=(
            "text_detected",
        ),
    )


def rejected_report():
    failure = create_validation_failure(
        failure_type="text_detected",
        severity="high",
        confidence=0.9,
        evidence="visible marks",
        technical_message="detected visible text",
        retry_relevant=True,
    )
    return create_validation_report(
        report_id="report-1",
        asset_id="asset-1",
        scene_id="scene-001",
        status="rejected",
        score=0.2,
        checks=(
            "text_detected",
        ),
        failures=(
            failure,
        ),
        severity="high",
    )


class RecordingValidator(AssetValidator):
    def __init__(
        self,
        report,
        events
    ):
        self.report = report
        self.events = events
        self.calls = []

    def validate(
        self,
        asset,
        context
    ):
        self.events.append(
            "validator"
        )
        self.calls.append(
            (
                asset,
                context,
            )
        )
        return self.report


class RecordingPolicy(RegenerationPolicy):
    def __init__(
        self,
        events
    ):
        super().__init__()
        self.events = events
        self.calls = []

    def decide(
        self,
        report,
        attempt_number
    ):
        self.events.append(
            "policy"
        )
        self.calls.append(
            (
                report,
                attempt_number,
            )
        )
        return super().decide(
            report,
            attempt_number
        )


class VisualQualityGateTest(unittest.TestCase):

    def test_result_is_passive_frozen_dataclass(self):
        self.assertTrue(
            is_dataclass(
                VisualQualityGateResult
            )
        )
        self.assertTrue(
            VisualQualityGateResult.__dataclass_params__.frozen
        )
        result = VisualQualityGate(
            RecordingValidator(
                accepted_report(),
                []
            ),
            RegenerationPolicy()
        ).evaluate(
            generated_asset(),
            validation_context()
        )

        with self.assertRaises(
            FrozenInstanceError
        ):
            result.result_fingerprint = "changed"

    def test_gate_executes_validator_then_policy(self):
        events = []
        validator = RecordingValidator(
            accepted_report(),
            events
        )
        policy = RecordingPolicy(
            events
        )
        asset = generated_asset()
        context = validation_context()
        result = VisualQualityGate(
            validator,
            policy
        ).evaluate(
            asset,
            context
        )

        self.assertEqual(
            events,
            [
                "validator",
                "policy",
            ]
        )
        self.assertEqual(
            len(
                validator.calls
            ),
            1
        )
        self.assertEqual(
            len(
                policy.calls
            ),
            1
        )
        self.assertIs(
            result.generated_asset,
            asset
        )

    def test_gate_passes_generated_asset_and_context_to_validator(self):
        events = []
        validator = RecordingValidator(
            accepted_report(),
            events
        )
        asset = generated_asset()
        context = validation_context()
        VisualQualityGate(
            validator,
            RecordingPolicy(
                events
            )
        ).evaluate(
            asset,
            context
        )

        self.assertEqual(
            validator.calls,
            [
                (
                    asset,
                    context,
                ),
            ]
        )

    def test_gate_passes_report_and_attempt_to_policy(self):
        events = []
        report = accepted_report()
        policy = RecordingPolicy(
            events
        )
        asset = generated_asset()
        VisualQualityGate(
            RecordingValidator(
                report,
                events
            ),
            policy
        ).evaluate(
            asset,
            validation_context()
        )

        self.assertEqual(
            policy.calls,
            [
                (
                    report,
                    asset.attempt_number,
                ),
            ]
        )

    def test_gate_propagates_report_and_decision_without_replacement(self):
        events = []
        report = accepted_report()
        result = VisualQualityGate(
            RecordingValidator(
                report,
                events
            ),
            RecordingPolicy(
                events
            )
        ).evaluate(
            generated_asset(),
            validation_context()
        )

        self.assertIs(
            result.validation_report,
            report
        )
        self.assertEqual(
            result.regeneration_decision.action,
            "accept"
        )

    def test_gate_does_not_modify_generated_asset_or_report(self):
        asset = generated_asset()
        report = rejected_report()
        asset_before = asset
        report_before = report

        result = VisualQualityGate(
            RecordingValidator(
                report,
                []
            ),
            RegenerationPolicy()
        ).evaluate(
            asset,
            validation_context()
        )

        self.assertEqual(
            asset,
            asset_before
        )
        self.assertEqual(
            report,
            report_before
        )
        self.assertIs(
            result.generated_asset,
            asset
        )
        self.assertIs(
            result.validation_report,
            report
        )

    def test_gate_result_is_deterministic(self):
        asset = generated_asset()
        context = validation_context()
        report = rejected_report()

        first = VisualQualityGate(
            RecordingValidator(
                report,
                []
            ),
            RegenerationPolicy()
        ).evaluate(
            asset,
            context
        )
        second = VisualQualityGate(
            RecordingValidator(
                report,
                []
            ),
            RegenerationPolicy()
        ).evaluate(
            asset,
            context
        )

        self.assertEqual(
            first,
            second
        )
        self.assertEqual(
            first.result_fingerprint,
            second.result_fingerprint
        )

    def test_gate_result_is_serializable_with_asdict(self):
        result = VisualQualityGate(
            RecordingValidator(
                accepted_report(),
                []
            ),
            RegenerationPolicy()
        ).evaluate(
            generated_asset(),
            validation_context()
        )

        serialized = asdict(
            result
        )

        self.assertEqual(
            serialized["generated_asset"]["asset_id"],
            "asset-1"
        )
        self.assertEqual(
            serialized["validation_report"]["report_id"],
            "report-1"
        )
        self.assertEqual(
            serialized["regeneration_decision"]["action"],
            "accept"
        )

    def test_gate_rejects_report_for_different_asset(self):
        bad_report = create_validation_report(
            report_id="report-1",
            asset_id="other-asset",
            scene_id="scene-001",
            status="accepted",
            score=1.0,
        )

        with self.assertRaises(
            ValueError
        ):
            VisualQualityGate(
                RecordingValidator(
                    bad_report,
                    []
                ),
                RegenerationPolicy()
            ).evaluate(
                generated_asset(),
                validation_context()
            )

    def test_gate_rejects_report_for_different_scene(self):
        bad_report = create_validation_report(
            report_id="report-1",
            asset_id="asset-1",
            scene_id="other-scene",
            status="accepted",
            score=1.0,
        )

        with self.assertRaises(
            ValueError
        ):
            VisualQualityGate(
                RecordingValidator(
                    bad_report,
                    []
                ),
                RegenerationPolicy()
            ).evaluate(
                generated_asset(),
                validation_context()
            )

    def test_gate_has_no_backend_runtime_or_prompt_dependencies(self):
        source = inspect.getsource(
            __import__(
                "app.visual_quality.gate",
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
