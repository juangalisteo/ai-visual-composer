import inspect
import tempfile
import unittest
from pathlib import Path

from app.visual_quality import (
    ImageQualityFlowCoordinator,
    ImageValidator,
    SeedPolicy,
    ValidationCheck,
    create_validation_failure,
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


class AlwaysFailCheck(ValidationCheck):
    name = "text_detected"
    check_category = "semantic"

    def check(
        self,
        asset,
        context
    ):
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


class ControlledRegenerationTest(unittest.TestCase):

    def test_seed_policy_is_deterministic(self):
        policy = SeedPolicy()

        first = policy.next_seed(
            scene_id="scene_001",
            generation_attempt_id="scene_001:attempt-1",
            attempt_number=2,
            base_seed=123
        )
        second = policy.next_seed(
            scene_id="scene_001",
            generation_attempt_id="scene_001:attempt-1",
            attempt_number=2,
            base_seed=123
        )

        self.assertEqual(
            first,
            second
        )

    def test_seed_policy_changes_by_attempt(self):
        policy = SeedPolicy()

        first = policy.next_seed(
            scene_id="scene_001",
            generation_attempt_id="scene_001:attempt-1",
            attempt_number=2,
            base_seed=123
        )
        second = policy.next_seed(
            scene_id="scene_001",
            generation_attempt_id="scene_001:attempt-2",
            attempt_number=3,
            base_seed=123
        )

        self.assertNotEqual(
            first,
            second
        )

    def test_first_retry_can_approve_second_attempt(self):
        result, calls = _run_flow(
            checks=(
                FailUntilAttemptCheck(
                    accepted_attempt=2
                ),
            )
        )

        self.assertEqual(
            result.status,
            "approved"
        )
        self.assertIsNotNone(
            result.retry_result
        )
        self.assertTrue(
            result.retry_result.retry_executed
        )
        self.assertEqual(
            result.generated_asset.attempt_number,
            2
        )
        self.assertEqual(
            len(
                calls
            ),
            1
        )
        self.assertEqual(
            calls[0][0],
            2
        )

    def test_second_retry_can_approve_third_attempt(self):
        result, calls = _run_flow(
            checks=(
                FailUntilAttemptCheck(
                    accepted_attempt=3
                ),
            )
        )

        self.assertEqual(
            result.status,
            "approved"
        )
        self.assertEqual(
            result.generated_asset.attempt_number,
            3
        )
        self.assertEqual(
            [
                call[0]
                for call in calls
            ],
            [
                2,
                3,
            ]
        )
        self.assertNotEqual(
            calls[0][1],
            calls[1][1]
        )

    def test_never_creates_fourth_attempt(self):
        result, calls = _run_flow(
            checks=(
                AlwaysFailCheck(),
            )
        )

        self.assertEqual(
            result.status,
            "manual_review"
        )
        self.assertEqual(
            result.generated_asset.attempt_number,
            3
        )
        self.assertEqual(
            [
                call[0]
                for call in calls
            ],
            [
                2,
                3,
            ]
        )
        self.assertIsNotNone(
            result.manual_review_marker
        )

    def test_scene_asset_history_records_all_attempts_without_overwrite(self):
        result, _calls = _run_flow(
            checks=(
                AlwaysFailCheck(),
            )
        )

        self.assertEqual(
            tuple(
                asset.attempt_number
                for asset in result.history.generated_assets
            ),
            (
                1,
                2,
                3,
            )
        )
        self.assertEqual(
            len(
                {
                    asset.asset_id
                    for asset in result.history.generated_assets
                }
            ),
            3
        )
        self.assertEqual(
            len(
                result.history.validation_reports
            ),
            3
        )
        self.assertEqual(
            len(
                result.history.regeneration_decisions
            ),
            3
        )

    def test_retry_result_is_deterministic(self):
        first, _first_calls = _run_flow(
            checks=(
                FailUntilAttemptCheck(
                    accepted_attempt=3
                ),
            )
        )
        second, _second_calls = _run_flow(
            checks=(
                FailUntilAttemptCheck(
                    accepted_attempt=3
                ),
            )
        )

        self.assertEqual(
            first.retry_result.result_fingerprint,
            second.retry_result.result_fingerprint
        )
        self.assertEqual(
            first.result_fingerprint,
            second.result_fingerprint
        )

    def test_retry_module_has_no_backend_runtime_or_prompt_dependencies(self):
        source = inspect.getsource(
            __import__(
                "app.visual_quality.retry",
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


def _run_flow(
    checks
):
    calls = []
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(
            temp_dir
        )
        initial_path = root / "scene_001_attempt_1.png"
        initial_path.write_bytes(
            b"attempt-1"
        )

        def generate_attempt(
            attempt_number,
            seed
        ):
            calls.append(
                (
                    attempt_number,
                    seed,
                )
            )
            path = root / f"scene_001_attempt_{attempt_number}.png"
            path.write_bytes(
                f"attempt-{attempt_number}:{seed}".encode(
                    "utf-8"
                )
            )
            return path

        result = ImageQualityFlowCoordinator(
            validator=ImageValidator(
                checks=tuple(
                    checks
                )
            )
        ).evaluate(
            image_path=initial_path,
            scene_number=1,
            width=1024,
            height=576,
            generate_attempt=generate_attempt,
            base_seed=123
        )

    return result, calls


if __name__ == "__main__":
    unittest.main()
