import inspect
import unittest
from dataclasses import FrozenInstanceError, asdict, is_dataclass

from certification import (
    CertificationMetrics,
    CertificationReport,
    CertificationResult,
    CertificationScenario,
    CertificationSummary,
    ScenarioExecutor,
    VisualCertificationSuite,
)
from certification.factory import (
    create_certification_result,
    create_certification_scenario,
)


class RecordingExecutor(ScenarioExecutor):
    def __init__(
        self,
        results
    ):
        self.results = dict(
            results
        )
        self.calls = []

    def execute(
        self,
        scenario
    ):
        self.calls.append(
            scenario.scenario_id
        )
        return self.results[
            scenario.scenario_id
        ]


class VisualCertificationSuiteTest(unittest.TestCase):

    def test_models_are_frozen_dataclasses(self):
        for model in (
            CertificationScenario,
            CertificationResult,
            CertificationMetrics,
            CertificationSummary,
            CertificationReport,
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

    def test_result_is_immutable(self):
        result = create_certification_result(
            scenario_id="portrait",
            status="PASS"
        )

        with self.assertRaises(
            FrozenInstanceError
        ):
            result.status = "FAIL"

    def test_registers_scenarios_in_order(self):
        suite = VisualCertificationSuite()
        suite.register(
            scenario_id="portrait",
            name="Portrait",
            component="image",
            objective="validate portraits"
        )
        suite.register(
            scenario_id="hospital",
            name="Hospital",
            component="image",
            objective="validate hospital context"
        )

        self.assertEqual(
            tuple(
                scenario.scenario_id
                for scenario in suite.scenarios
            ),
            (
                "portrait",
                "hospital",
            )
        )

    def test_rejects_duplicate_scenarios(self):
        suite = VisualCertificationSuite()
        scenario = create_certification_scenario(
            scenario_id="portrait",
            name="Portrait",
            component="image",
            objective="validate portraits"
        )
        suite.register_scenario(
            scenario
        )

        with self.assertRaises(
            ValueError
        ):
            suite.register_scenario(
                scenario
            )

    def test_executes_enabled_scenarios(self):
        suite = VisualCertificationSuite(
            executor=RecordingExecutor({
                "portrait": create_certification_result(
                    scenario_id="portrait",
                    status="PASS",
                    approved=True,
                    attempts=1,
                )
            })
        )
        suite.register(
            scenario_id="portrait",
            name="Portrait",
            component="image",
            objective="validate portraits"
        )
        report = suite.run(
            generated_at="2026-07-25"
        )

        self.assertEqual(
            report.results[0].status,
            "PASS"
        )
        self.assertEqual(
            report.metrics.passed,
            1
        )

    def test_skips_disabled_scenarios_without_executor_call(self):
        executor = RecordingExecutor({})
        suite = VisualCertificationSuite(
            executor=executor
        )
        suite.register(
            scenario_id="disabled",
            name="Disabled",
            component="image",
            objective="disabled scenario",
            enabled=False
        )
        report = suite.run()

        self.assertEqual(
            executor.calls,
            []
        )
        self.assertEqual(
            report.results[0].status,
            "SKIPPED"
        )
        self.assertEqual(
            report.metrics.skipped,
            1
        )

    def test_metrics_include_approval_retry_manual_review_and_stopped(self):
        suite = VisualCertificationSuite(
            executor=RecordingExecutor({
                "pass": create_certification_result(
                    scenario_id="pass",
                    status="PASS",
                    approved=True,
                    attempts=1,
                ),
                "warn": create_certification_result(
                    scenario_id="warn",
                    status="WARNING",
                    retry_count=2,
                    manual_review=True,
                    attempts=3,
                ),
                "fail": create_certification_result(
                    scenario_id="fail",
                    status="FAIL",
                    stopped=True,
                    attempts=1,
                ),
            })
        )
        for scenario_id in (
            "pass",
            "warn",
            "fail",
        ):
            suite.register(
                scenario_id=scenario_id,
                name=scenario_id,
                component="image",
                objective=scenario_id,
            )

        report = suite.run()

        self.assertEqual(
            report.metrics.total,
            3
        )
        self.assertEqual(
            report.metrics.approved,
            1
        )
        self.assertEqual(
            report.metrics.retry,
            2
        )
        self.assertEqual(
            report.metrics.manual_review,
            1
        )
        self.assertEqual(
            report.metrics.stopped,
            1
        )
        self.assertEqual(
            report.metrics.approval_rate,
            0.3333
        )

    def test_report_summary_final_result_pass(self):
        suite = VisualCertificationSuite(
            backend="local",
            executor=RecordingExecutor({
                "portrait": create_certification_result(
                    scenario_id="portrait",
                    status="PASS",
                    approved=True,
                )
            })
        )
        suite.register(
            scenario_id="portrait",
            name="Portrait",
            component="image",
            objective="validate portraits"
        )

        report = suite.run()

        self.assertEqual(
            report.summary.final_result,
            "PASS"
        )
        self.assertEqual(
            report.summary.backend,
            "local"
        )

    def test_report_summary_final_result_warning(self):
        suite = VisualCertificationSuite(
            executor=RecordingExecutor({
                "warn": create_certification_result(
                    scenario_id="warn",
                    status="WARNING",
                    manual_review=True,
                )
            })
        )
        suite.register(
            scenario_id="warn",
            name="Warning",
            component="image",
            objective="warning scenario"
        )

        report = suite.run()

        self.assertEqual(
            report.summary.final_result,
            "WARNING"
        )

    def test_report_summary_final_result_fail(self):
        suite = VisualCertificationSuite(
            executor=RecordingExecutor({
                "fail": create_certification_result(
                    scenario_id="fail",
                    status="FAIL",
                )
            })
        )
        suite.register(
            scenario_id="fail",
            name="Fail",
            component="image",
            objective="fail scenario"
        )

        report = suite.run()

        self.assertEqual(
            report.summary.final_result,
            "FAIL"
        )

    def test_supports_all_result_statuses(self):
        for status in (
            "PASS",
            "FAIL",
            "WARNING",
            "SKIPPED",
        ):
            with self.subTest(
                status=status
            ):
                result = create_certification_result(
                    scenario_id=status.lower(),
                    status=status
                )
                self.assertEqual(
                    result.status,
                    status
                )

    def test_rejects_boolean_like_status(self):
        with self.assertRaises(
            ValueError
        ):
            create_certification_result(
                scenario_id="bad",
                status="True"
            )

    def test_report_is_deterministic(self):
        suite = _sample_suite()

        first = suite.run(
            generated_at="2026-07-25"
        )
        second = suite.run(
            generated_at="2026-07-25"
        )

        self.assertEqual(
            first,
            second
        )
        self.assertEqual(
            first.report_fingerprint,
            second.report_fingerprint
        )

    def test_fingerprint_changes_when_result_changes(self):
        first = _sample_suite(
            status="PASS"
        ).run()
        second = _sample_suite(
            status="FAIL"
        ).run()

        self.assertNotEqual(
            first.report_fingerprint,
            second.report_fingerprint
        )

    def test_report_is_serializable_with_asdict(self):
        report = _sample_suite().run()
        serialized = asdict(
            report
        )

        self.assertEqual(
            serialized["suite"],
            "visual_certification"
        )
        self.assertEqual(
            serialized["results"][0]["status"],
            "PASS"
        )

    def test_requires_executor(self):
        suite = VisualCertificationSuite()
        suite.register(
            scenario_id="portrait",
            name="Portrait",
            component="image",
            objective="validate portraits"
        )

        with self.assertRaises(
            ValueError
        ):
            suite.run()

    def test_certification_package_has_no_runtime_dependencies(self):
        source = inspect.getsource(
            __import__(
                "certification",
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


def _sample_suite(
    status="PASS"
):
    suite = VisualCertificationSuite(
        executor=RecordingExecutor({
            "portrait": create_certification_result(
                scenario_id="portrait",
                status=status,
                approved=status == "PASS",
            )
        })
    )
    suite.register(
        scenario_id="portrait",
        name="Portrait",
        component="image",
        objective="validate portraits"
    )
    return suite


if __name__ == "__main__":
    unittest.main()
