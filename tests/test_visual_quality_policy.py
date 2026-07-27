import inspect
import unittest
from dataclasses import FrozenInstanceError, is_dataclass

from app.visual_quality import (
    RegenerationPolicy,
    RegenerationPolicyConfig,
    create_validation_failure,
    create_validation_report,
)


def failure(
    *,
    failure_type="text_detected",
    severity="high",
    retry_relevant=True
):
    return create_validation_failure(
        failure_type=failure_type,
        severity=severity,
        confidence=0.9,
        evidence="detected issue",
        technical_message="validation issue",
        retry_relevant=retry_relevant,
    )


def report(
    *,
    status="rejected",
    failures=None,
    requires_manual_review=False,
    report_id="report-1"
):
    failures = tuple(
        failures
        if failures is not None
        else (
            failure(),
        )
    )
    return create_validation_report(
        report_id=report_id,
        asset_id="asset-1",
        scene_id="scene-001",
        status=status,
        score=1.0 if status == "accepted" else 0.1,
        checks=(
            "text_detected",
        ),
        failures=failures,
        severity="low" if status == "accepted" else "high",
        requires_manual_review=requires_manual_review,
        validator_version="validator-v1",
    )


class RegenerationPolicyTest(unittest.TestCase):

    def test_policy_config_is_frozen_dataclass(self):
        self.assertTrue(
            is_dataclass(
                RegenerationPolicyConfig
            )
        )
        self.assertTrue(
            RegenerationPolicyConfig.__dataclass_params__.frozen
        )
        config = RegenerationPolicyConfig()

        with self.assertRaises(
            FrozenInstanceError
        ):
            config.max_attempts = 4

    def test_policy_config_rejects_invalid_max_attempts(self):
        with self.assertRaises(
            ValueError
        ):
            RegenerationPolicyConfig(
                max_attempts=0
            )

    def test_policy_config_rejects_empty_version(self):
        with self.assertRaises(
            ValueError
        ):
            RegenerationPolicyConfig(
                version=""
            )

    def test_accepts_accepted_report(self):
        validation_report = report(
            status="accepted",
            failures=()
        )
        decision = RegenerationPolicy().decide(
            validation_report,
            attempt_number=1
        )

        self.assertEqual(
            decision.action,
            "accept"
        )
        self.assertEqual(
            decision.report_id,
            validation_report.report_id
        )
        self.assertFalse(
            decision.manual_review_required
        )

    def test_retries_retry_relevant_failure_before_max_attempts(self):
        validation_report = report()
        decision = RegenerationPolicy().decide(
            validation_report,
            attempt_number=1
        )

        self.assertEqual(
            decision.action,
            "retry"
        )
        self.assertEqual(
            decision.reason,
            "retry-relevant validation failure"
        )
        self.assertEqual(
            decision.failure_types,
            (
                "text_detected",
            )
        )
        self.assertIsNone(
            decision.next_seed
        )

    def test_manual_review_when_max_attempts_are_reached(self):
        validation_report = report()
        decision = RegenerationPolicy().decide(
            validation_report,
            attempt_number=3
        )

        self.assertEqual(
            decision.action,
            "manual_review"
        )
        self.assertEqual(
            decision.reason,
            "maximum attempts reached"
        )
        self.assertTrue(
            decision.manual_review_required
        )

    def test_custom_max_attempts_changes_retry_boundary(self):
        validation_report = report()
        policy = RegenerationPolicy(
            RegenerationPolicyConfig(
                max_attempts=2
            )
        )

        retry = policy.decide(
            validation_report,
            attempt_number=1
        )
        manual = policy.decide(
            validation_report,
            attempt_number=2
        )

        self.assertEqual(
            retry.action,
            "retry"
        )
        self.assertEqual(
            manual.action,
            "manual_review"
        )

    def test_manual_review_when_report_requires_manual_review(self):
        validation_report = report(
            requires_manual_review=True
        )
        decision = RegenerationPolicy().decide(
            validation_report,
            attempt_number=1
        )

        self.assertEqual(
            decision.action,
            "manual_review"
        )
        self.assertEqual(
            decision.reason,
            "validation report requires manual review"
        )

    def test_stop_for_non_regenerable_critical_failure(self):
        validation_report = report(
            failures=(
                failure(
                    severity="critical",
                    retry_relevant=False,
                ),
            )
        )
        decision = RegenerationPolicy().decide(
            validation_report,
            attempt_number=1
        )

        self.assertEqual(
            decision.action,
            "stop"
        )
        self.assertEqual(
            decision.reason,
            "critical non-regenerable validation failure"
        )

    def test_manual_review_for_non_retryable_non_critical_failure(self):
        validation_report = report(
            failures=(
                failure(
                    severity="medium",
                    retry_relevant=False,
                ),
            )
        )
        decision = RegenerationPolicy().decide(
            validation_report,
            attempt_number=1
        )

        self.assertEqual(
            decision.action,
            "manual_review"
        )
        self.assertEqual(
            decision.reason,
            "validation failure is not automatically retryable"
        )

    def test_policy_is_deterministic(self):
        validation_report = report()
        policy = RegenerationPolicy()

        first = policy.decide(
            validation_report,
            attempt_number=1
        )
        second = policy.decide(
            validation_report,
            attempt_number=1
        )

        self.assertEqual(
            first,
            second
        )
        self.assertEqual(
            first.decision_fingerprint,
            second.decision_fingerprint
        )

    def test_policy_fingerprint_changes_when_decision_changes(self):
        validation_report = report()
        policy = RegenerationPolicy()

        first = policy.decide(
            validation_report,
            attempt_number=1
        )
        second = policy.decide(
            validation_report,
            attempt_number=3
        )

        self.assertNotEqual(
            first.action,
            second.action
        )
        self.assertNotEqual(
            first.decision_fingerprint,
            second.decision_fingerprint
        )

    def test_policy_rejects_invalid_attempt_number(self):
        with self.assertRaises(
            ValueError
        ):
            RegenerationPolicy().decide(
                report(),
                attempt_number=0
            )

    def test_policy_does_not_apply_seed_policy_yet(self):
        decision = RegenerationPolicy().decide(
            report(),
            attempt_number=1
        )

        self.assertIsNone(
            decision.next_seed
        )

    def test_policy_has_no_backend_runtime_or_prompt_dependencies(self):
        source = inspect.getsource(
            __import__(
                "app.visual_quality.policy",
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
