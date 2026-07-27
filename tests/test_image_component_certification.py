import inspect
import unittest
from dataclasses import FrozenInstanceError, asdict, is_dataclass

from certification import (
    ArtifactRetentionPolicy,
    CertificationProfile,
    ImageCertificationExecutor,
    ImageCertificationObservation,
    ImageCertificationScenarioLibrary,
    VisualCertificationSuite,
)


class ImageComponentCertificationTest(unittest.TestCase):

    def test_image_certification_models_are_frozen(self):
        for model in (
            ArtifactRetentionPolicy,
            CertificationProfile,
            ImageCertificationObservation,
        ):
            with self.subTest(
                model=model.__name__
            ):
                self.assertTrue(
                    is_dataclass(
                        model
                    )
                )
                self.assertTrue(
                    model.__dataclass_params__.frozen
                )

    def test_artifact_retention_policy_defaults(self):
        policy = ArtifactRetentionPolicy()

        self.assertTrue(
            policy.keep_pass_approved_asset
        )
        self.assertTrue(
            policy.keep_retry_rejected_metadata
        )
        self.assertFalse(
            policy.keep_retry_rejected_heavy_artifacts
        )
        self.assertTrue(
            policy.keep_manual_review_latest_asset
        )
        self.assertTrue(
            policy.keep_manual_review_metadata
        )

    def test_artifact_retention_policy_is_configurable_and_immutable(self):
        policy = ArtifactRetentionPolicy(
            keep_retry_rejected_heavy_artifacts=True
        )

        self.assertTrue(
            policy.keep_retry_rejected_heavy_artifacts
        )
        with self.assertRaises(
            FrozenInstanceError
        ):
            policy.keep_pass_approved_asset = False

    def test_scenario_library_contains_initial_image_scenarios(self):
        scenarios = ImageCertificationScenarioLibrary.base_scenarios()
        scenario_ids = {
            scenario.scenario_id
            for scenario in scenarios
        }

        self.assertTrue(
            {
                "portrait",
                "hospital",
                "fantasy",
                "forest",
                "animals",
                "hands",
                "wardrobe",
                "identity",
                "continuity",
                "retry",
                "rollback",
                "history",
            }.issubset(
                scenario_ids
            )
        )
        for scenario in scenarios:
            self.assertEqual(
                scenario.component,
                "image"
            )
            self.assertIn(
                "acceptance_criteria",
                dict(
                    scenario.metadata
                )
            )

    def test_quick_standard_and_full_profiles_are_prepared(self):
        quick = ImageCertificationScenarioLibrary.quick_profile()
        standard = ImageCertificationScenarioLibrary.standard_profile()
        full = ImageCertificationScenarioLibrary.full_profile()

        self.assertEqual(
            quick.target_scenario_count,
            25
        )
        self.assertEqual(
            standard.target_scenario_count,
            100
        )
        self.assertEqual(
            full.target_scenario_count,
            200
        )
        self.assertGreater(
            len(
                quick.scenarios
            ),
            0
        )

    def test_executor_converts_approved_observation_to_pass_result(self):
        executor = ImageCertificationExecutor(
            runner=lambda scenario: ImageCertificationObservation(
                approved=True,
                attempts=1,
                execution_time=0.5,
                details="approved"
            )
        )
        result = executor.execute(
            ImageCertificationScenarioLibrary.base_scenarios()[0]
        )

        self.assertEqual(
            result.status,
            "PASS"
        )
        self.assertTrue(
            result.approved
        )
        self.assertEqual(
            result.attempts,
            1
        )

    def test_executor_converts_manual_review_observation_to_warning(self):
        executor = ImageCertificationExecutor(
            runner=lambda scenario: ImageCertificationObservation(
                manual_review=True,
                attempts=3,
                retry_count=2,
            )
        )
        result = executor.execute(
            ImageCertificationScenarioLibrary.base_scenarios()[0]
        )

        self.assertEqual(
            result.status,
            "WARNING"
        )
        self.assertTrue(
            result.manual_review
        )
        self.assertEqual(
            result.retry_count,
            2
        )

    def test_executor_converts_stopped_observation_to_fail(self):
        executor = ImageCertificationExecutor(
            runner=lambda scenario: ImageCertificationObservation(
                stopped=True
            )
        )
        result = executor.execute(
            ImageCertificationScenarioLibrary.base_scenarios()[0]
        )

        self.assertEqual(
            result.status,
            "FAIL"
        )
        self.assertTrue(
            result.stopped
        )

    def test_executor_preserves_explicit_status(self):
        executor = ImageCertificationExecutor(
            runner=lambda scenario: ImageCertificationObservation(
                status="SKIPPED",
                details="external skip"
            )
        )
        result = executor.execute(
            ImageCertificationScenarioLibrary.base_scenarios()[0]
        )

        self.assertEqual(
            result.status,
            "SKIPPED"
        )
        self.assertEqual(
            result.details,
            "external skip"
        )

    def test_executor_converts_runner_exception_to_fail(self):
        def failing_runner(
            scenario
        ):
            raise RuntimeError(
                "boom"
            )

        executor = ImageCertificationExecutor(
            runner=failing_runner
        )
        result = executor.execute(
            ImageCertificationScenarioLibrary.base_scenarios()[0]
        )

        self.assertEqual(
            result.status,
            "FAIL"
        )
        self.assertEqual(
            result.attempts,
            0
        )
        self.assertIn(
            "boom",
            result.errors
        )

    def test_suite_runs_image_certification_profile(self):
        profile = ImageCertificationScenarioLibrary.quick_profile()
        executor = ImageCertificationExecutor(
            runner=lambda scenario: ImageCertificationObservation(
                approved=True,
                attempts=1,
            )
        )
        suite = VisualCertificationSuite(
            suite_name="image_component_certification",
            version="v5b",
            backend="external",
            model="test-model",
            executor=executor
        )
        for scenario in profile.scenarios:
            suite.register_scenario(
                scenario
            )

        report = suite.run(
            generated_at="2026-07-25"
        )

        self.assertEqual(
            report.metrics.total,
            len(
                profile.scenarios
            )
        )
        self.assertEqual(
            report.metrics.approval_rate,
            1.0
        )
        self.assertEqual(
            report.summary.final_result,
            "PASS"
        )

    def test_metrics_include_retry_success_first_attempt_and_stopped_rates(self):
        scenarios = ImageCertificationScenarioLibrary.base_scenarios()[:3]
        observations = {
            scenarios[0].scenario_id: ImageCertificationObservation(
                approved=True,
                attempts=1,
            ),
            scenarios[1].scenario_id: ImageCertificationObservation(
                approved=True,
                attempts=3,
                retry_count=2,
            ),
            scenarios[2].scenario_id: ImageCertificationObservation(
                stopped=True,
                attempts=1,
            ),
        }
        suite = VisualCertificationSuite(
            executor=ImageCertificationExecutor(
                runner=lambda scenario: observations[
                    scenario.scenario_id
                ]
            )
        )
        for scenario in scenarios:
            suite.register_scenario(
                scenario
            )

        report = suite.run()

        self.assertEqual(
            report.metrics.stopped_rate,
            0.3333
        )
        self.assertEqual(
            report.metrics.retry_success_rate,
            1.0
        )
        self.assertEqual(
            report.metrics.first_attempt_success_rate,
            0.3333
        )

    def test_image_certification_is_deterministic(self):
        profile = ImageCertificationScenarioLibrary.quick_profile()
        executor = ImageCertificationExecutor(
            runner=lambda scenario: ImageCertificationObservation(
                approved=True,
                attempts=1,
            )
        )

        first = _run_profile(
            profile,
            executor
        )
        second = _run_profile(
            profile,
            executor
        )

        self.assertEqual(
            first,
            second
        )
        self.assertEqual(
            first.report_fingerprint,
            second.report_fingerprint
        )

    def test_report_is_serializable(self):
        report = _run_profile(
            ImageCertificationScenarioLibrary.quick_profile(),
            ImageCertificationExecutor(
                runner=lambda scenario: ImageCertificationObservation(
                    approved=True
                )
            )
        )
        serialized = asdict(
            report
        )

        self.assertEqual(
            serialized["suite"],
            "image_component_certification"
        )
        self.assertEqual(
            serialized["results"][0]["status"],
            "PASS"
        )

    def test_image_certification_package_has_no_runtime_dependencies(self):
        source = inspect.getsource(
            __import__(
                "certification.image_component",
                fromlist=[
                    "x"
                ]
            )
        )
        forbidden = (
            "ImageBuilder",
            "VisualQualityGate",
            "RetryCoordinator",
            "ImageValidator",
            "PromptTranslator",
            "ComfyUI",
            "workflow",
            "manifest",
            "requests",
            "urllib",
        )

        for item in forbidden:
            with self.subTest(
                item=item
            ):
                self.assertNotIn(
                    item,
                    source
                )


def _run_profile(
    profile,
    executor
):
    suite = VisualCertificationSuite(
        suite_name="image_component_certification",
        version="v5b",
        backend="external",
        model="test-model",
        executor=executor
    )
    for scenario in profile.scenarios:
        suite.register_scenario(
            scenario
        )
    return suite.run(
        generated_at="2026-07-25"
    )


if __name__ == "__main__":
    unittest.main()
