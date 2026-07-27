from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from app.visual_quality.models import (
    ApprovedAsset,
    GeneratedAsset,
    ManualReviewMarker,
    RegenerationDecision,
    SceneAssetHistory,
    ValidationContext,
    ValidationFailure,
    ValidationReport,
)


VALID_ASSET_TYPES = (
    "image",
    "animated_image",
    "video",
    "cover",
    "sequence",
)
VALID_FAILURE_TYPES = (
    "text_detected",
    "pseudotext_detected",
    "logo_detected",
    "badge_detected",
    "unsafe_wardrobe",
    "anatomy_error",
    "continuity_break",
    "scene_mismatch",
)
VALID_SEVERITIES = (
    "low",
    "medium",
    "high",
    "critical",
)
VALID_REPORT_STATUSES = (
    "accepted",
    "rejected",
    "uncertain",
)
VALID_DECISION_ACTIONS = (
    "accept",
    "retry",
    "manual_review",
    "stop",
)
VALID_MARKER_STATUSES = (
    "pending",
    "resolved",
    "dismissed",
)
VALID_HISTORY_STATUSES = (
    "generating",
    "accepted",
    "manual_review",
    "stopped",
)
BLOCKING_SEVERITIES = (
    "high",
    "critical",
)


def create_generated_asset(
    *,
    asset_id: str,
    scene_id: str,
    asset_type: str,
    path: str,
    attempt_number: int,
    generation_attempt_id: str,
    width: int,
    height: int,
    sequence_id: str = "",
    duration: float | None = None,
    fps: float | None = None,
    metadata: tuple[tuple[str, str], ...] = (),
) -> GeneratedAsset:
    _require(
        asset_id,
        "asset_id is required"
    )
    _require(
        scene_id,
        "scene_id is required"
    )
    _require_one_of(
        asset_type,
        VALID_ASSET_TYPES,
        "asset_type"
    )
    _require(
        generation_attempt_id,
        "generation_attempt_id is required"
    )
    _require_minimum(
        attempt_number,
        1,
        "attempt_number"
    )
    _require_minimum(
        width,
        1,
        "width"
    )
    _require_minimum(
        height,
        1,
        "height"
    )
    asset = GeneratedAsset(
        asset_id=asset_id,
        scene_id=scene_id,
        asset_type=asset_type,
        path=_normalize_path(
            path
        ),
        attempt_number=attempt_number,
        generation_attempt_id=generation_attempt_id,
        width=width,
        height=height,
        sequence_id=sequence_id,
        duration=duration,
        fps=fps,
        metadata=_sorted_metadata(
            metadata
        ),
    )
    return GeneratedAsset(
        **{
            **asdict(
                asset
            ),
            "generation_fingerprint": _fingerprint(
                "GeneratedAsset",
                asset
            ),
        }
    )


def create_validation_context(
    *,
    scene_id: str,
    validation_profile: str,
    sequence_id: str = "",
    expected_identity_markers: tuple[str, ...] = (),
    expected_wardrobe_markers: tuple[str, ...] = (),
    expected_environment_markers: tuple[str, ...] = (),
    previous_accepted_assets: tuple[str, ...] = (),
    restrictions: tuple[str, ...] = (),
    required_checks: tuple[str, ...] = (),
) -> ValidationContext:
    _require(
        scene_id,
        "scene_id is required"
    )
    _require(
        validation_profile,
        "validation_profile is required"
    )
    context = ValidationContext(
        scene_id=scene_id,
        validation_profile=validation_profile,
        sequence_id=sequence_id,
        expected_identity_markers=tuple(
            expected_identity_markers
        ),
        expected_wardrobe_markers=tuple(
            expected_wardrobe_markers
        ),
        expected_environment_markers=tuple(
            expected_environment_markers
        ),
        previous_accepted_assets=tuple(
            previous_accepted_assets
        ),
        restrictions=tuple(
            restrictions
        ),
        required_checks=tuple(
            required_checks
        ),
    )
    return ValidationContext(
        **{
            **asdict(
                context
            ),
            "context_fingerprint": _fingerprint(
                "ValidationContext",
                context
            ),
        }
    )


def create_validation_failure(
    *,
    failure_type: str,
    severity: str,
    confidence: float,
    evidence: str,
    technical_message: str,
    retry_relevant: bool,
    region: tuple[int, int, int, int] | None = None,
) -> ValidationFailure:
    _require_one_of(
        failure_type,
        VALID_FAILURE_TYPES,
        "failure_type"
    )
    _require_one_of(
        severity,
        VALID_SEVERITIES,
        "severity"
    )
    if confidence < 0 or confidence > 1:
        raise ValueError(
            "confidence must be between 0 and 1"
        )
    _require(
        evidence,
        "evidence is required"
    )
    _require(
        technical_message,
        "technical_message is required"
    )
    failure = ValidationFailure(
        failure_type=failure_type,
        severity=severity,
        confidence=confidence,
        evidence=evidence,
        technical_message=technical_message,
        retry_relevant=retry_relevant,
        region=region,
    )
    return ValidationFailure(
        **{
            **asdict(
                failure
            ),
            "failure_fingerprint": _fingerprint(
                "ValidationFailure",
                failure
            ),
        }
    )


def create_validation_report(
    *,
    report_id: str,
    asset_id: str,
    scene_id: str,
    status: str,
    score: float,
    checks: tuple[str, ...] = (),
    failures: tuple[ValidationFailure, ...] = (),
    severity: str = "low",
    requires_manual_review: bool = False,
    validator_version: str = "1.0.0",
) -> ValidationReport:
    _require(
        report_id,
        "report_id is required"
    )
    _require(
        asset_id,
        "asset_id is required"
    )
    _require(
        scene_id,
        "scene_id is required"
    )
    _require_one_of(
        status,
        VALID_REPORT_STATUSES,
        "status"
    )
    _require_one_of(
        severity,
        VALID_SEVERITIES,
        "severity"
    )
    if score < 0 or score > 1:
        raise ValueError(
            "score must be between 0 and 1"
        )
    if status == "accepted" and _has_blocking_failures(
        failures
    ):
        raise ValueError(
            "accepted report cannot contain blocking failures"
        )
    if status == "rejected" and not failures:
        raise ValueError(
            "rejected report must contain at least one failure"
        )
    if status == "uncertain" and not failures:
        raise ValueError(
            "uncertain report must explain uncertainty with at least one failure"
        )
    report = ValidationReport(
        report_id=report_id,
        asset_id=asset_id,
        scene_id=scene_id,
        status=status,
        score=score,
        checks=tuple(
            checks
        ),
        failures=tuple(
            failures
        ),
        severity=severity,
        requires_manual_review=requires_manual_review,
        validator_version=validator_version,
    )
    return ValidationReport(
        **{
            **asdict(
                report
            ),
            "failures": report.failures,
            "validation_fingerprint": _fingerprint(
                "ValidationReport",
                report
            ),
        }
    )


def create_regeneration_decision(
    *,
    decision_id: str,
    report_id: str,
    action: str,
    attempt_number: int,
    reason: str,
    failure_types: tuple[str, ...] = (),
    next_seed: int | None = None,
    manual_review_required: bool = False,
    validation_report: ValidationReport | None = None,
) -> RegenerationDecision:
    _require(
        decision_id,
        "decision_id is required"
    )
    _require(
        report_id,
        "report_id is required"
    )
    _require_one_of(
        action,
        VALID_DECISION_ACTIONS,
        "action"
    )
    _require_minimum(
        attempt_number,
        1,
        "attempt_number"
    )
    _require(
        reason,
        "reason is required"
    )
    if action == "accept" and validation_report is None:
        raise ValueError(
            "accept decision requires an accepted report"
        )
    if validation_report is not None:
        if validation_report.report_id != report_id:
            raise ValueError(
                "decision report_id must match validation_report"
            )
        if action == "accept" and validation_report.status != "accepted":
            raise ValueError(
                "accept decision requires an accepted report"
            )
    if action == "accept" and manual_review_required:
        raise ValueError(
            "accept decision cannot require manual review"
        )
    if action == "manual_review" and not manual_review_required:
        raise ValueError(
            "manual_review decision must require manual review"
        )
    decision = RegenerationDecision(
        decision_id=decision_id,
        report_id=report_id,
        action=action,
        attempt_number=attempt_number,
        reason=reason,
        failure_types=tuple(
            failure_types
        ),
        next_seed=next_seed,
        manual_review_required=manual_review_required,
    )
    return RegenerationDecision(
        **{
            **asdict(
                decision
            ),
            "decision_fingerprint": _fingerprint(
                "RegenerationDecision",
                decision
            ),
        }
    )


def create_approved_asset(
    *,
    approved_asset_id: str,
    generated_asset: GeneratedAsset,
    final_validation_report: ValidationReport,
    acceptance_decision: RegenerationDecision,
    total_attempts: int,
    quality_gate_version: str = "1.0.0",
) -> ApprovedAsset:
    _require(
        approved_asset_id,
        "approved_asset_id is required"
    )
    _require_minimum(
        total_attempts,
        1,
        "total_attempts"
    )
    if final_validation_report.asset_id != generated_asset.asset_id:
        raise ValueError(
            "final_validation_report must belong to generated_asset"
        )
    if final_validation_report.status != "accepted":
        raise ValueError(
            "ApprovedAsset requires an accepted validation report"
        )
    if acceptance_decision.report_id != final_validation_report.report_id:
        raise ValueError(
            "acceptance_decision must belong to final_validation_report"
        )
    if acceptance_decision.action != "accept":
        raise ValueError(
            "ApprovedAsset requires an accept decision"
        )
    approved = ApprovedAsset(
        approved_asset_id=approved_asset_id,
        generated_asset=generated_asset,
        final_validation_report=final_validation_report,
        acceptance_decision=acceptance_decision,
        total_attempts=total_attempts,
        quality_gate_version=quality_gate_version,
    )
    return ApprovedAsset(
        **{
            **asdict(
                approved
            ),
            "generated_asset": approved.generated_asset,
            "final_validation_report": approved.final_validation_report,
            "acceptance_decision": approved.acceptance_decision,
            "approval_fingerprint": _fingerprint(
                "ApprovedAsset",
                approved
            ),
        }
    )


def create_manual_review_marker(
    *,
    marker_id: str,
    scene_id: str,
    latest_asset: GeneratedAsset,
    latest_report: ValidationReport,
    attempts: tuple[GeneratedAsset, ...],
    reasons: tuple[str, ...],
    status: str = "pending",
    sequence_id: str = "",
    attempt_artifact_paths: tuple[str, ...] = (),
) -> ManualReviewMarker:
    _require(
        marker_id,
        "marker_id is required"
    )
    _require(
        scene_id,
        "scene_id is required"
    )
    _require_one_of(
        status,
        VALID_MARKER_STATUSES,
        "status"
    )
    if latest_asset.scene_id != scene_id:
        raise ValueError(
            "latest_asset must belong to marker scene"
        )
    if latest_report.asset_id != latest_asset.asset_id:
        raise ValueError(
            "latest_report must belong to latest_asset"
        )
    if latest_asset not in attempts:
        raise ValueError(
            "latest_asset must be included in attempts"
        )
    if not reasons:
        raise ValueError(
            "manual review marker requires at least one reason"
        )
    marker = ManualReviewMarker(
        marker_id=marker_id,
        scene_id=scene_id,
        latest_asset=latest_asset,
        latest_report=latest_report,
        attempts=tuple(
            attempts
        ),
        reasons=tuple(
            reasons
        ),
        status=status,
        sequence_id=sequence_id,
        attempt_artifact_paths=tuple(
            _normalize_path(
                path
            )
            for path in attempt_artifact_paths
        ),
    )
    return ManualReviewMarker(
        **{
            **asdict(
                marker
            ),
            "latest_asset": marker.latest_asset,
            "latest_report": marker.latest_report,
            "attempts": marker.attempts,
            "marker_fingerprint": _fingerprint(
                "ManualReviewMarker",
                marker
            ),
        }
    )


def create_scene_asset_history(
    *,
    scene_id: str,
    generated_assets: tuple[GeneratedAsset, ...],
    validation_reports: tuple[ValidationReport, ...],
    regeneration_decisions: tuple[RegenerationDecision, ...],
    status: str,
    sequence_id: str = "",
    approved_asset: ApprovedAsset | None = None,
    manual_review_marker: ManualReviewMarker | None = None,
) -> SceneAssetHistory:
    _require(
        scene_id,
        "scene_id is required"
    )
    _require_one_of(
        status,
        VALID_HISTORY_STATUSES,
        "status"
    )
    _validate_history(
        scene_id=scene_id,
        generated_assets=generated_assets,
        validation_reports=validation_reports,
        regeneration_decisions=regeneration_decisions,
        status=status,
        approved_asset=approved_asset,
        manual_review_marker=manual_review_marker,
    )
    history = SceneAssetHistory(
        scene_id=scene_id,
        generated_assets=tuple(
            generated_assets
        ),
        validation_reports=tuple(
            validation_reports
        ),
        regeneration_decisions=tuple(
            regeneration_decisions
        ),
        status=status,
        sequence_id=sequence_id,
        approved_asset=approved_asset,
        manual_review_marker=manual_review_marker,
    )
    return SceneAssetHistory(
        **{
            **asdict(
                history
            ),
            "generated_assets": history.generated_assets,
            "validation_reports": history.validation_reports,
            "regeneration_decisions": history.regeneration_decisions,
            "approved_asset": history.approved_asset,
            "manual_review_marker": history.manual_review_marker,
            "history_fingerprint": _fingerprint(
                "SceneAssetHistory",
                history
            ),
        }
    )


def _validate_history(
    *,
    scene_id: str,
    generated_assets: tuple[GeneratedAsset, ...],
    validation_reports: tuple[ValidationReport, ...],
    regeneration_decisions: tuple[RegenerationDecision, ...],
    status: str,
    approved_asset: ApprovedAsset | None,
    manual_review_marker: ManualReviewMarker | None,
) -> None:
    attempts = tuple(
        asset.attempt_number
        for asset in generated_assets
    )
    if attempts != tuple(
        sorted(
            attempts
        )
    ):
        raise ValueError(
            "generated_assets must be ordered by attempt_number"
        )
    if len(
        set(
            attempts
        )
    ) != len(
        attempts
    ):
        raise ValueError(
            "GeneratedAsset attempts cannot be overwritten"
        )
    asset_ids = {
        asset.asset_id
        for asset in generated_assets
    }
    if len(
        asset_ids
    ) != len(
        generated_assets
    ):
        raise ValueError(
            "GeneratedAsset ids must be unique"
        )
    for asset in generated_assets:
        if asset.scene_id != scene_id:
            raise ValueError(
                "GeneratedAsset must belong to history scene"
            )
    report_ids = {
        report.report_id
        for report in validation_reports
    }
    if len(
        report_ids
    ) != len(
        validation_reports
    ):
        raise ValueError(
            "ValidationReport ids must be unique"
        )
    for report in validation_reports:
        if report.asset_id not in asset_ids:
            raise ValueError(
                "ValidationReport must correspond to a registered GeneratedAsset"
            )
    for decision in regeneration_decisions:
        if decision.report_id not in report_ids:
            raise ValueError(
                "RegenerationDecision must correspond to a registered ValidationReport"
            )
    if approved_asset is not None:
        if status != "accepted":
            raise ValueError(
                "history status must be accepted when approved_asset exists"
            )
        if approved_asset.generated_asset.asset_id not in asset_ids:
            raise ValueError(
                "ApprovedAsset must reference a registered GeneratedAsset"
            )
    if manual_review_marker is not None:
        if status != "manual_review":
            raise ValueError(
                "history status must be manual_review when manual_review_marker exists"
            )
        if manual_review_marker.latest_asset.asset_id not in asset_ids:
            raise ValueError(
                "ManualReviewMarker must reference a registered GeneratedAsset"
            )
    if approved_asset is not None and manual_review_marker is not None:
        raise ValueError(
            "history cannot contain approved_asset and manual_review_marker together"
        )


def _has_blocking_failures(
    failures: tuple[ValidationFailure, ...]
) -> bool:
    return any(
        failure.severity in BLOCKING_SEVERITIES
        for failure in failures
    )


def _require(
    value: str,
    message: str
) -> None:
    if not value:
        raise ValueError(
            message
        )


def _require_minimum(
    value: int,
    minimum: int,
    name: str
) -> None:
    if value < minimum:
        raise ValueError(
            f"{name} must be at least {minimum}"
        )


def _require_one_of(
    value: str,
    options: tuple[str, ...],
    name: str
) -> None:
    if value not in options:
        raise ValueError(
            f"{name} must be one of {options}"
        )


def _sorted_metadata(
    metadata: tuple[tuple[str, str], ...]
) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(
            (
                str(
                    key
                ),
                str(
                    value
                ),
            )
            for key, value in metadata
        )
    )


def _normalize_path(
    path: str
) -> str:
    normalized = str(
        path
    ).replace(
        "\\",
        "/"
    )
    if re.match(
        r"^[A-Za-z]:/",
        normalized
    ) or normalized.startswith(
        "/"
    ):
        return normalized.rstrip(
            "/"
        ).split(
            "/"
        )[-1]
    while normalized.startswith(
        "./"
    ):
        normalized = normalized[2:]
    return normalized


def _fingerprint(
    label: str,
    value: Any
) -> str:
    canonical = {
        label: _canonical_mapping(
            value
        )
    }
    return hashlib.sha256(
        json.dumps(
            canonical,
            sort_keys=True,
            separators=(
                ",",
                ":"
            )
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def _canonical_mapping(
    value: Any
) -> Any:
    if isinstance(
        value,
        Enum
    ):
        return value.value
    if is_dataclass(
        value
    ):
        return {
            key: _canonical_mapping(
                item
            )
            for key, item in asdict(
                value
            ).items()
            if not key.endswith(
                "_fingerprint"
            )
            and key
            not in (
                "generation_fingerprint",
                "context_fingerprint",
                "validation_fingerprint",
                "decision_fingerprint",
                "approval_fingerprint",
                "marker_fingerprint",
                "history_fingerprint",
            )
        }
    if isinstance(
        value,
        dict
    ):
        return {
            key: _canonical_mapping(
                item
            )
            for key, item in sorted(
                value.items()
            )
        }
    if isinstance(
        value,
        (
            tuple,
            list,
        )
    ):
        return [
            _canonical_mapping(
                item
            )
            for item in value
        ]
    return value
