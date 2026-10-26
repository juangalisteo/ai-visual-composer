import inspect
import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError, asdict, is_dataclass
from pathlib import Path
from unittest.mock import patch

from certification import (
    CAMPAIGN_RESULTS,
    CampaignReport,
    CampaignRunConfig,
    CertificationCriteria,
    ImageCertificationExecutor,
    ImageCertificationObservation,
    RC0CampaignProfiles,
    RealImageComponentRunner,
    RealImageRunnerConfig,
    RealCertificationCampaign,
    CertificationScenario,
)


class RealCertificationCampaignTest(unittest.TestCase):

    def test_campaign_models_are_frozen(self):
        for model in (
            CampaignReport,
            CampaignRunConfig,
            CertificationCriteria,
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

    def test_campaign_report_is_immutable(self):
        report = _run_campaign(
            RC0CampaignProfiles.quick()
        )

        with self.assertRaises(
            FrozenInstanceError
        ):
            report.final_result = "NOT_CERTIFIED"

    def test_rc0_profiles_have_expected_targets(self):
        quick = RC0CampaignProfiles.quick()
        standard = RC0CampaignProfiles.standard()
        full = RC0CampaignProfiles.full()

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
        self.assertEqual(
            len(
                quick.scenarios
            ),
            25
        )
        self.assertEqual(
            len(
                standard.scenarios
            ),
            100
        )
        self.assertEqual(
            len(
                full.scenarios
            ),
            200
        )

    def test_rc0_profiles_keep_scenario_categories(self):
        profile = RC0CampaignProfiles.quick()
        tags = {
            tag
            for scenario in profile.scenarios
            for tag in scenario.tags
        }

        for expected in (
            "portrait",
            "context",
            "fantasy",
            "nature",
            "animals",
            "anatomy",
            "wardrobe",
            "identity",
            "continuity",
            "retry",
            "rollback",
            "history",
        ):
            with self.subTest(
                expected=expected
            ):
                self.assertIn(
                    expected,
                    tags
                )

    def test_runs_quick_campaign(self):
        report = _run_campaign(
            RC0CampaignProfiles.quick()
        )

        self.assertEqual(
            report.profile_id,
            "rc0_quick"
        )
        self.assertEqual(
            report.executed_scenarios,
            25
        )
        self.assertEqual(
            report.final_result,
            "CERTIFIED"
        )
        self.assertEqual(
            report.certification_report.metrics.approval_rate,
            1.0
        )

    def test_runs_standard_campaign(self):
        report = _run_campaign(
            RC0CampaignProfiles.standard()
        )

        self.assertEqual(
            report.profile_id,
            "rc0_standard"
        )
        self.assertEqual(
            report.executed_scenarios,
            100
        )

    def test_runs_full_campaign(self):
        report = _run_campaign(
            RC0CampaignProfiles.full()
        )

        self.assertEqual(
            report.profile_id,
            "rc0_full"
        )
        self.assertEqual(
            report.executed_scenarios,
            200
        )

    def test_campaign_report_contains_backend_model_and_storage(self):
        report = _run_campaign(
            RC0CampaignProfiles.quick(),
            storage_used=4096,
        )

        self.assertEqual(
            report.backend,
            "comfyui"
        )
        self.assertEqual(
            report.model,
            "flux"
        )
        self.assertEqual(
            report.storage_used,
            4096
        )

    def test_campaign_records_warning_fail_and_skipped_scenarios(self):
        observations = {
            "portrait": ImageCertificationObservation(
                approved=True
            ),
            "hospital": ImageCertificationObservation(
                manual_review=True
            ),
            "fantasy": ImageCertificationObservation(
                stopped=True
            ),
            "forest": ImageCertificationObservation(
                status="SKIPPED"
            ),
        }
        profile = RC0CampaignProfiles.quick()
        report = _run_campaign(
            profile,
            observations=observations,
        )

        self.assertIn(
            "hospital",
            report.warning_scenarios
        )
        self.assertIn(
            "fantasy",
            report.failed_scenarios
        )
        self.assertIn(
            "forest",
            report.skipped_scenarios
        )
        self.assertEqual(
            report.final_result,
            "NOT_CERTIFIED"
        )

    def test_campaign_supports_conditionally_certified(self):
        observations = {
            "portrait": ImageCertificationObservation(
                approved=True
            ),
            "hospital": ImageCertificationObservation(
                manual_review=True,
                attempts=2,
                retry_count=1,
            ),
        }
        report = _run_campaign(
            RC0CampaignProfiles.quick(),
            observations=observations,
            default_observation=ImageCertificationObservation(
                approved=True
            ),
        )

        self.assertEqual(
            report.final_result,
            "CONDITIONALLY_CERTIFIED"
        )

    def test_campaign_supports_not_certified_from_thresholds(self):
        report = _run_campaign(
            RC0CampaignProfiles.quick(),
            criteria=CertificationCriteria(
                minimum_approval_rate=1.1
            ),
        )

        self.assertEqual(
            report.final_result,
            "NOT_CERTIFIED"
        )

    def test_campaign_supports_required_pass_tags(self):
        report = _run_campaign(
            RC0CampaignProfiles.quick(),
            observations={
                "retry": ImageCertificationObservation(
                    manual_review=True
                )
            },
            criteria=CertificationCriteria(
                required_pass_tags=(
                    "retry",
                )
            ),
            default_observation=ImageCertificationObservation(
                approved=True
            ),
        )

        self.assertEqual(
            report.final_result,
            "NOT_CERTIFIED"
        )

    def test_result_metadata_records_seed_history_and_fingerprints(self):
        report = _run_campaign(
            RC0CampaignProfiles.quick()
        )
        metadata = dict(
            report.certification_report.results[0].metadata
        )

        self.assertIn(
            "seed",
            metadata
        )
        self.assertIn(
            "history_id",
            metadata
        )
        self.assertIn(
            "asset_fingerprint",
            metadata
        )

    def test_campaign_is_deterministic(self):
        profile = RC0CampaignProfiles.quick()

        first = _run_campaign(
            profile
        )
        second = _run_campaign(
            profile
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
        first = _run_campaign(
            RC0CampaignProfiles.quick()
        )
        second = _run_campaign(
            RC0CampaignProfiles.quick(),
            observations={
                "portrait": ImageCertificationObservation(
                    manual_review=True
                )
            },
            default_observation=ImageCertificationObservation(
                approved=True
            ),
        )

        self.assertNotEqual(
            first.report_fingerprint,
            second.report_fingerprint
        )

    def test_campaign_report_is_serializable(self):
        report = _run_campaign(
            RC0CampaignProfiles.quick()
        )
        serialized = asdict(
            report
        )

        self.assertEqual(
            serialized["profile_id"],
            "rc0_quick"
        )
        self.assertEqual(
            serialized["final_result"],
            "CERTIFIED"
        )

    def test_campaign_results_are_explicit_strings(self):
        self.assertEqual(
            CAMPAIGN_RESULTS,
            (
                "CERTIFIED",
                "CONDITIONALLY_CERTIFIED",
                "NOT_CERTIFIED",
            )
        )

    def test_campaign_has_no_image_component_dependencies(self):
        source = inspect.getsource(
            __import__(
                "certification.campaign",
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
            "ComfyUIBackend",
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

    def test_real_image_runner_writes_visual_truth_storyboard(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            storyboard_path = Path(
                temp_dir
            ) / "storyboard.json"
            runner = RealImageComponentRunner()

            runner._write_storyboard(
                storyboard_path,
                CertificationScenario(
                    scenario_id="portrait",
                    name="Portrait",
                    component="image",
                    objective="Certify portrait behavior.",
                    tags=(
                        "image",
                        "portrait",
                    ),
                ),
            )

            storyboard = json.loads(
                storyboard_path.read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(
            1,
            storyboard[0]["scene"],
        )
        self.assertEqual(
            "thoughtful adult person",
            storyboard[0]["visible_subject"],
        )
        self.assertEqual(
            "quiet professional studio",
            storyboard[0]["visible_environment"],
        )
        self.assertEqual(
            "structured",
            storyboard[0]["visual_truth_status"],
        )
        self.assertIn(
            "realistic anatomy",
            storyboard[0]["visual_constraints"],
        )
        self.assertNotIn(
            "visual_idea",
            storyboard[0],
        )

    def test_real_image_runner_injects_profile_without_global_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            approved_asset = root / "approved.png"
            approved_asset.write_bytes(
                b"approved"
            )
            manifest_path = root / "images_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    [
                        {
                            "scene": 1,
                            "image": str(
                                approved_asset
                            ),
                        }
                    ]
                ),
                encoding="utf-8"
            )
            config = RealImageRunnerConfig(
                campaign_id="explicit_profile",
                base_output_dir=root / "certification",
                platform="horizontal",
                image_format="horizontal",
                image_width=640,
                image_height=360,
                workflow_path=root / "workflow.json",
                image_validation_enabled=True,
            )
            runner = RealImageComponentRunner(
                config
            )
            scenario = CertificationScenario(
                scenario_id="portrait",
                name="Portrait",
                component="image",
                objective="Certify explicit profile injection.",
                tags=(
                    "image",
                    "portrait",
                ),
            )

            with patch(
                "certification.real_image_runner.ProjectManager"
            ) as project_manager, patch(
                "certification.real_image_runner.ImageBuilder"
            ) as image_builder:
                project = project_manager.return_value
                project.storyboard_path.return_value = (
                    root / "project" / "storyboard.json"
                )
                project.images_dir.return_value = (
                    root / "project" / "images"
                )
                image_builder.return_value.build.return_value = (
                    manifest_path
                )

                observation = runner(
                    scenario
                )

            self.assertTrue(
                observation.approved
            )
            project_manager.assert_called_once_with(
                project_name="explicit_profile_portrait"
            )
            self.assertIs(
                project,
                image_builder.call_args.kwargs["project"]
            )
            injected_profile = image_builder.call_args.kwargs[
                "profile"
            ]
            self.assertTrue(
                injected_profile["image_validation"]["enabled"]
            )
            self.assertTrue(
                injected_profile["visual_director"]["enabled"]
            )
            self.assertEqual("horizontal", injected_profile["platform"])
            self.assertEqual("horizontal", injected_profile["format"])
            self.assertEqual("640x360", injected_profile["resolution"])
            self.assertEqual(
                {"width": 640, "height": 360},
                injected_profile["video_style"],
            )
            persisted_profile = json.loads(
                (
                    config.base_output_dir
                    / config.campaign_id
                    / scenario.scenario_id
                    / "profile.rc0.json"
                ).read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                injected_profile,
                persisted_profile
            )
            self.assertNotIn(
                "MC_PROFILE_PATH",
                inspect.getsource(
                    __import__(
                        "certification.real_image_runner",
                        fromlist=[
                            "x"
                        ]
                    )
                )
            )
            self.assertFalse(
                hasattr(config, "profile_path")
            )

    def test_real_image_runner_default_profile_preserves_effective_contract(self):
        runner = RealImageComponentRunner()

        self.assertEqual(
            {
                "platform": "horizontal",
                "format": "horizontal",
                "resolution": "1920x1080",
                "video_style": {
                    "width": 1920,
                    "height": 1080,
                },
                "image_validation": {
                    "enabled": True,
                },
                "visual_director": {
                    "enabled": True,
                },
            },
            runner._build_campaign_profile(),
        )


def _run_campaign(
    profile,
    *,
    observations=None,
    default_observation=None,
    criteria=None,
    storage_used=1024,
):
    observations = observations or {}
    default_observation = default_observation or ImageCertificationObservation(
        approved=True,
        attempts=1,
    )

    def runner(
        scenario
    ):
        observation = observations.get(
            scenario.scenario_id,
            default_observation
        )
        if observation.metadata:
            return observation
        return ImageCertificationObservation(
            status=observation.status,
            attempts=observation.attempts,
            approved=observation.approved,
            retry_count=observation.retry_count,
            manual_review=observation.manual_review,
            stopped=observation.stopped,
            execution_time=observation.execution_time,
            details=observation.details,
            errors=observation.errors,
            metadata=(
                (
                    "seed",
                    f"seed-{scenario.scenario_id}",
                ),
                (
                    "history_id",
                    f"history-{scenario.scenario_id}",
                ),
                (
                    "asset_fingerprint",
                    f"asset-{scenario.scenario_id}",
                ),
            ),
        )

    campaign = RealCertificationCampaign(
        profile=profile,
        executor=ImageCertificationExecutor(
            runner=runner
        ),
        config=CampaignRunConfig(
            version="rc0",
            generated_at="2026-07-27",
            backend="comfyui",
            model="flux",
            storage_used=storage_used,
            criteria=criteria or CertificationCriteria(),
        ),
    )
    return campaign.run()


if __name__ == "__main__":
    unittest.main()
