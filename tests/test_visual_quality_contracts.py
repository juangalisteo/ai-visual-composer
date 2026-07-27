import inspect
import unittest
from dataclasses import FrozenInstanceError, is_dataclass, replace

from app.visual_quality import (
    ApprovedAsset,
    GeneratedAsset,
    ManualReviewMarker,
    RegenerationDecision,
    SceneAssetHistory,
    ValidationContext,
    ValidationFailure,
    ValidationReport,
    create_approved_asset,
    create_generated_asset,
    create_manual_review_marker,
    create_regeneration_decision,
    create_scene_asset_history,
    create_validation_context,
    create_validation_failure,
    create_validation_report,
)


def generated_asset(
    attempt_number=1,
    asset_id="asset-1",
    path="output/images/scene_001.png"
):
    return create_generated_asset(
        asset_id=asset_id,
        scene_id="scene-001",
        sequence_id="sequence-001",
        asset_type="image",
        path=path,
        attempt_number=attempt_number,
        generation_attempt_id=f"scene-001-attempt-{attempt_number}",
        width=1024,
        height=576,
        metadata=(
            (
                "stable",
                "value",
            ),
        ),
    )


def failure(
    failure_type="text_detected",
    severity="high"
):
    return create_validation_failure(
        failure_type=failure_type,
        severity=severity,
        confidence=0.91,
        evidence="visible glyphs on board",
        technical_message="OCR-like marks detected",
        retry_relevant=True,
        region=(
            1,
            2,
            3,
            4,
        ),
    )


def accepted_report(
    asset=None
):
    asset = asset or generated_asset()
    return create_validation_report(
        report_id=f"report-{asset.asset_id}",
        asset_id=asset.asset_id,
        scene_id=asset.scene_id,
        status="accepted",
        score=1.0,
        checks=(
            "text_detected",
        ),
        validator_version="validator-v1",
    )


def rejected_report(
    asset=None
):
    asset = asset or generated_asset()
    return create_validation_report(
        report_id=f"report-{asset.asset_id}",
        asset_id=asset.asset_id,
        scene_id=asset.scene_id,
        status="rejected",
        score=0.2,
        checks=(
            "text_detected",
        ),
        failures=(
            failure(),
        ),
        severity="high",
        requires_manual_review=False,
        validator_version="validator-v1",
    )


def accept_decision(
    report=None
):
    report = report or accepted_report()
    return create_regeneration_decision(
        decision_id=f"decision-{report.report_id}",
        report_id=report.report_id,
        action="accept",
        attempt_number=1,
        reason="asset accepted",
        validation_report=report,
    )


class VisualQualityContractsTest(unittest.TestCase):

    def test_models_are_passive_frozen_dataclasses(self):
        for model in (
            GeneratedAsset,
            ApprovedAsset,
            ValidationContext,
            ValidationFailure,
            ValidationReport,
            RegenerationDecision,
            ManualReviewMarker,
            SceneAssetHistory,
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

    def test_contracts_are_immutable(self):
        asset = generated_asset()

        with self.assertRaises(
            FrozenInstanceError
        ):
            asset.width = 2048

    def test_generated_asset_requires_attempt_number_starting_at_one(self):
        with self.assertRaises(
            ValueError
        ):
            generated_asset(
                attempt_number=0
            )

    def test_generated_asset_fingerprint_is_stable(self):
        first = generated_asset()
        second = generated_asset()

        self.assertEqual(
            first.generation_fingerprint,
            second.generation_fingerprint
        )

    def test_generated_asset_fingerprint_changes_on_real_change(self):
        first = generated_asset()
        second = generated_asset(
            asset_id="asset-2"
        )

        self.assertNotEqual(
            first.generation_fingerprint,
            second.generation_fingerprint
        )

    def test_generated_asset_normalizes_absolute_paths_for_fingerprint_stability(self):
        asset = generated_asset(
            path="C:\\Users\\someone\\output\\scene_001.png"
        )

        self.assertEqual(
            "scene_001.png",
            asset.path
        )

    def test_validation_context_has_deterministic_fingerprint(self):
        first = create_validation_context(
            scene_id="scene-001",
            sequence_id="sequence-001",
            validation_profile="image-v1",
            expected_identity_markers=(
                "same detective",
            ),
            restrictions=(
                "no text",
            ),
            required_checks=(
                "text_detected",
            ),
        )
        second = create_validation_context(
            scene_id="scene-001",
            sequence_id="sequence-001",
            validation_profile="image-v1",
            expected_identity_markers=(
                "same detective",
            ),
            restrictions=(
                "no text",
            ),
            required_checks=(
                "text_detected",
            ),
        )

        self.assertEqual(
            first.context_fingerprint,
            second.context_fingerprint
        )

    def test_validation_failure_accepts_only_v3_failure_types(self):
        with self.assertRaises(
            ValueError
        ):
            create_validation_failure(
                failure_type="beauty_preference",
                severity="low",
                confidence=0.5,
                evidence="subjective",
                technical_message="subjective",
                retry_relevant=False,
            )

    def test_validation_failure_fingerprint_changes_when_failure_changes(self):
        first = failure()
        second = failure(
            failure_type="logo_detected"
        )

        self.assertNotEqual(
            first.failure_fingerprint,
            second.failure_fingerprint
        )

    def test_accepted_validation_report_cannot_contain_blocking_failures(self):
        with self.assertRaises(
            ValueError
        ):
            create_validation_report(
                report_id="report-1",
                asset_id="asset-1",
                scene_id="scene-001",
                status="accepted",
                score=1.0,
                failures=(
                    failure(
                        severity="critical"
                    ),
                ),
            )

    def test_rejected_validation_report_requires_failure(self):
        with self.assertRaises(
            ValueError
        ):
            create_validation_report(
                report_id="report-1",
                asset_id="asset-1",
                scene_id="scene-001",
                status="rejected",
                score=0.1,
            )

    def test_uncertain_validation_report_requires_failure(self):
        with self.assertRaises(
            ValueError
        ):
            create_validation_report(
                report_id="report-1",
                asset_id="asset-1",
                scene_id="scene-001",
                status="uncertain",
                score=0.5,
            )

    def test_regeneration_decision_accept_requires_accepted_report(self):
        report = rejected_report()

        with self.assertRaises(
            ValueError
        ):
            create_regeneration_decision(
                decision_id="decision-1",
                report_id=report.report_id,
                action="accept",
                attempt_number=1,
                reason="not valid",
                validation_report=report,
            )

    def test_regeneration_decision_accept_requires_report_context(self):
        with self.assertRaises(
            ValueError
        ):
            create_regeneration_decision(
                decision_id="decision-1",
                report_id="report-1",
                action="accept",
                attempt_number=1,
                reason="asset accepted",
            )

    def test_manual_review_decision_requires_manual_review_flag(self):
        with self.assertRaises(
            ValueError
        ):
            create_regeneration_decision(
                decision_id="decision-1",
                report_id="report-1",
                action="manual_review",
                attempt_number=3,
                reason="max attempts reached",
            )

    def test_approved_asset_requires_accept_decision(self):
        asset = generated_asset()
        report = accepted_report(
            asset
        )
        decision = create_regeneration_decision(
            decision_id="decision-1",
            report_id=report.report_id,
            action="retry",
            attempt_number=1,
            reason="try again",
            failure_types=(
                "text_detected",
            ),
            next_seed=42,
            validation_report=report,
        )

        with self.assertRaises(
            ValueError
        ):
            create_approved_asset(
                approved_asset_id="approved-1",
                generated_asset=asset,
                final_validation_report=report,
                acceptance_decision=decision,
                total_attempts=1,
            )

    def test_approved_asset_preserves_generated_asset_without_duplication(self):
        asset = generated_asset()
        report = accepted_report(
            asset
        )
        decision = accept_decision(
            report
        )
        approved = create_approved_asset(
            approved_asset_id="approved-1",
            generated_asset=asset,
            final_validation_report=report,
            acceptance_decision=decision,
            total_attempts=1,
        )

        self.assertIs(
            approved.generated_asset,
            asset
        )
        self.assertEqual(
            approved.final_validation_report,
            report
        )
        self.assertTrue(
            approved.approval_fingerprint
        )

    def test_manual_review_marker_preserves_attempts_and_reasons(self):
        asset = generated_asset()
        report = rejected_report(
            asset
        )
        marker = create_manual_review_marker(
            marker_id="marker-1",
            scene_id="scene-001",
            latest_asset=asset,
            latest_report=report,
            attempts=(
                asset,
            ),
            reasons=(
                "max attempts reached",
            ),
            attempt_artifact_paths=(
                "C:\\tmp\\attempt.png",
            ),
        )

        self.assertEqual(
            marker.status,
            "pending"
        )
        self.assertEqual(
            marker.attempt_artifact_paths,
            (
                "attempt.png",
            )
        )
        self.assertTrue(
            marker.marker_fingerprint
        )

    def test_scene_asset_history_requires_chronological_attempts(self):
        first = generated_asset(
            attempt_number=1,
            asset_id="asset-1"
        )
        second = generated_asset(
            attempt_number=2,
            asset_id="asset-2"
        )

        with self.assertRaises(
            ValueError
        ):
            create_scene_asset_history(
                scene_id="scene-001",
                generated_assets=(
                    second,
                    first,
                ),
                validation_reports=(),
                regeneration_decisions=(),
                status="generating",
            )

    def test_scene_asset_history_prevents_overwritten_attempts(self):
        first = generated_asset(
            attempt_number=1,
            asset_id="asset-1"
        )
        duplicate_attempt = generated_asset(
            attempt_number=1,
            asset_id="asset-2"
        )

        with self.assertRaises(
            ValueError
        ):
            create_scene_asset_history(
                scene_id="scene-001",
                generated_assets=(
                    first,
                    duplicate_attempt,
                ),
                validation_reports=(),
                regeneration_decisions=(),
                status="generating",
            )

    def test_scene_asset_history_requires_reports_to_match_registered_assets(self):
        asset = generated_asset()
        report = create_validation_report(
            report_id="report-missing",
            asset_id="missing-asset",
            scene_id="scene-001",
            status="accepted",
            score=1.0,
        )

        with self.assertRaises(
            ValueError
        ):
            create_scene_asset_history(
                scene_id="scene-001",
                generated_assets=(
                    asset,
                ),
                validation_reports=(
                    report,
                ),
                regeneration_decisions=(),
                status="generating",
            )

    def test_scene_asset_history_requires_decisions_to_match_registered_reports(self):
        asset = generated_asset()
        decision = create_regeneration_decision(
            decision_id="decision-1",
            report_id="missing-report",
            action="retry",
            attempt_number=1,
            reason="retry",
            failure_types=(
                "text_detected",
            ),
            next_seed=42,
        )

        with self.assertRaises(
            ValueError
        ):
            create_scene_asset_history(
                scene_id="scene-001",
                generated_assets=(
                    asset,
                ),
                validation_reports=(),
                regeneration_decisions=(
                    decision,
                ),
                status="generating",
            )

    def test_scene_asset_history_status_is_accepted_when_approved_asset_exists(self):
        asset = generated_asset()
        report = accepted_report(
            asset
        )
        decision = accept_decision(
            report
        )
        approved = create_approved_asset(
            approved_asset_id="approved-1",
            generated_asset=asset,
            final_validation_report=report,
            acceptance_decision=decision,
            total_attempts=1,
        )

        with self.assertRaises(
            ValueError
        ):
            create_scene_asset_history(
                scene_id="scene-001",
                generated_assets=(
                    asset,
                ),
                validation_reports=(
                    report,
                ),
                regeneration_decisions=(
                    decision,
                ),
                approved_asset=approved,
                status="generating",
            )

    def test_scene_asset_history_accepts_single_approved_asset(self):
        asset = generated_asset()
        report = accepted_report(
            asset
        )
        decision = accept_decision(
            report
        )
        approved = create_approved_asset(
            approved_asset_id="approved-1",
            generated_asset=asset,
            final_validation_report=report,
            acceptance_decision=decision,
            total_attempts=1,
        )
        history = create_scene_asset_history(
            scene_id="scene-001",
            generated_assets=(
                asset,
            ),
            validation_reports=(
                report,
            ),
            regeneration_decisions=(
                decision,
            ),
            approved_asset=approved,
            status="accepted",
        )

        self.assertIs(
            history.approved_asset,
            approved
        )
        self.assertEqual(
            history.status,
            "accepted"
        )

    def test_scene_asset_history_status_is_manual_review_when_marker_exists(self):
        asset = generated_asset()
        report = rejected_report(
            asset
        )
        decision = create_regeneration_decision(
            decision_id="decision-1",
            report_id=report.report_id,
            action="manual_review",
            attempt_number=1,
            reason="max attempts reached",
            failure_types=(
                "text_detected",
            ),
            manual_review_required=True,
            validation_report=report,
        )
        marker = create_manual_review_marker(
            marker_id="marker-1",
            scene_id="scene-001",
            latest_asset=asset,
            latest_report=report,
            attempts=(
                asset,
            ),
            reasons=(
                "max attempts reached",
            ),
        )
        history = create_scene_asset_history(
            scene_id="scene-001",
            generated_assets=(
                asset,
            ),
            validation_reports=(
                report,
            ),
            regeneration_decisions=(
                decision,
            ),
            manual_review_marker=marker,
            status="manual_review",
        )

        self.assertIs(
            history.manual_review_marker,
            marker
        )
        self.assertEqual(
            history.status,
            "manual_review"
        )

    def test_scene_asset_history_fingerprint_changes_when_attempt_changes(self):
        first = generated_asset()
        report = accepted_report(
            first
        )
        decision = accept_decision(
            report
        )
        approved = create_approved_asset(
            approved_asset_id="approved-1",
            generated_asset=first,
            final_validation_report=report,
            acceptance_decision=decision,
            total_attempts=1,
        )
        history = create_scene_asset_history(
            scene_id="scene-001",
            generated_assets=(
                first,
            ),
            validation_reports=(
                report,
            ),
            regeneration_decisions=(
                decision,
            ),
            approved_asset=approved,
            status="accepted",
        )
        changed_asset = replace(
            first,
            generation_attempt_id="changed"
        )
        changed_history = create_scene_asset_history(
            scene_id="scene-001",
            generated_assets=(
                changed_asset,
            ),
            validation_reports=(),
            regeneration_decisions=(),
            status="generating",
        )

        self.assertNotEqual(
            history.history_fingerprint,
            changed_history.history_fingerprint
        )

    def test_visual_quality_contracts_do_not_expose_backend_runtime_or_prompt_fields(self):
        for model in (
            GeneratedAsset,
            ApprovedAsset,
            ValidationContext,
            ValidationFailure,
            ValidationReport,
            RegenerationDecision,
            ManualReviewMarker,
            SceneAssetHistory,
        ):
            with self.subTest(
                model=model.__name__
            ):
                field_names = {
                    field.lower()
                    for field in model.__dataclass_fields__
                }
                forbidden = {
                    "prompt",
                    "payload",
                    "workflow",
                    "backend",
                    "runtime",
                    "manifest",
                    "timestamp",
                    "log",
                }
                self.assertTrue(
                    forbidden.isdisjoint(
                        field_names
                    )
                )

    def test_visual_quality_package_has_no_runtime_backend_or_prompt_dependencies(self):
        source = inspect.getsource(
            __import__(
                "app.visual_quality",
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
