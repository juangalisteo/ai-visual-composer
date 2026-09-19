from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from app.visual_quality.factory import (
    create_approved_asset,
    create_generated_asset,
    create_manual_review_marker,
    create_scene_asset_history,
    create_validation_context,
)
from app.visual_quality.gate import VisualQualityGate
from app.visual_quality.image_validator import (
    ImageValidator,
    default_product_quality_checks,
)
from app.visual_quality.models import (
    ApprovedAsset,
    GeneratedAsset,
    ManualReviewMarker,
    SceneAssetHistory,
)
from app.visual_quality.policy import RegenerationPolicy
from app.visual_quality.retry import RetryCoordinator, RetryResult
from app.visual_quality.nudity_safety import NUDITY_FAILURE_TYPE


@dataclass(frozen=True)
class ImageQualityFlowResult:
    status: str
    generated_asset: GeneratedAsset
    history: SceneAssetHistory
    approved_asset: ApprovedAsset | None = None
    manual_review_marker: ManualReviewMarker | None = None
    retry_result: RetryResult | None = None
    result_fingerprint: str = ""


class ImageQualityFlowCoordinator:
    def __init__(
        self,
        gate: VisualQualityGate | None = None,
        validator: ImageValidator | None = None,
        policy: RegenerationPolicy | None = None,
        retry_coordinator: RetryCoordinator | None = None,
        validation_profile: str = "image-v1",
        quality_gate_version: str = "1.0.0"
    ) -> None:
        if not validation_profile:
            raise ValueError(
                "validation_profile is required"
            )
        if not quality_gate_version:
            raise ValueError(
                "quality_gate_version is required"
            )
        self.validator = validator or ImageValidator(
            checks=default_product_quality_checks()
        )
        self.policy = policy or RegenerationPolicy()
        self.gate = gate or VisualQualityGate(
            validator=self.validator,
            policy=self.policy
        )
        self.retry_coordinator = (
            retry_coordinator
            or RetryCoordinator()
        )
        self.validation_profile = validation_profile
        self.quality_gate_version = quality_gate_version

    def evaluate(
        self,
        *,
        image_path: Path,
        scene_number: int,
        width: int,
        height: int,
        sequence_id: str = "",
        attempt_number: int = 1,
        generate_attempt=None,
        base_seed: int = 0
    ) -> ImageQualityFlowResult:
        scene_id = (
            f"scene_{scene_number:03d}"
        )
        asset = create_generated_asset(
            asset_id=(
                f"{scene_id}:attempt-{attempt_number}"
            ),
            scene_id=scene_id,
            sequence_id=sequence_id,
            asset_type="image",
            path=str(
                image_path
            ),
            attempt_number=attempt_number,
            generation_attempt_id=(
                f"{scene_id}:attempt-{attempt_number}"
            ),
            width=width,
            height=height,
            local_artifact_path=str(
                image_path
            ),
        )
        context = create_validation_context(
            scene_id=scene_id,
            sequence_id=sequence_id,
            validation_profile=self.validation_profile,
            required_checks=self._required_checks(),
        )
        gate_result = self.gate.evaluate(
            asset,
            context
        )
        decision = gate_result.regeneration_decision
        approved_asset = None
        manual_review_marker = None
        status = _flow_status(
            decision.action
        )
        history_status = _history_status(
            status
        )
        if decision.action == "accept":
            approved_asset = create_approved_asset(
                approved_asset_id=(
                    f"{asset.asset_id}:approved"
                ),
                generated_asset=asset,
                final_validation_report=gate_result.validation_report,
                acceptance_decision=decision,
                total_attempts=attempt_number,
                quality_gate_version=self.quality_gate_version,
            )
        elif decision.action == "manual_review":
            manual_review_marker = create_manual_review_marker(
                marker_id=(
                    f"{asset.asset_id}:manual-review"
                ),
                scene_id=asset.scene_id,
                sequence_id=asset.sequence_id,
                latest_asset=asset,
                latest_report=gate_result.validation_report,
                attempts=(
                    asset,
                ),
                reasons=(
                    decision.reason,
                ),
                attempt_artifact_paths=(
                    asset.path,
                ),
            )
        history = create_scene_asset_history(
            scene_id=asset.scene_id,
            sequence_id=asset.sequence_id,
            generated_assets=(
                asset,
            ),
            validation_reports=(
                gate_result.validation_report,
            ),
            regeneration_decisions=(
                decision,
            ),
            approved_asset=approved_asset,
            manual_review_marker=manual_review_marker,
            status=history_status,
        )
        retry_result = None
        if (
            status == "retry_requested"
            and generate_attempt is not None
        ):
            retry_result = self.retry_coordinator.run(
                initial_history=history,
                width=width,
                height=height,
                generate_attempt=generate_attempt,
                evaluate_attempt=lambda next_asset: self.gate.evaluate(
                    next_asset,
                    context
                ),
                base_seed=base_seed,
                max_attempts=self._retry_max_attempts(
                    gate_result.validation_report,
                ),
            )
            status = retry_result.status
            history = retry_result.history
            asset = retry_result.generated_asset
            approved_asset = retry_result.approved_asset
            manual_review_marker = retry_result.manual_review_marker
        result = ImageQualityFlowResult(
            status=status,
            generated_asset=asset,
            history=history,
            approved_asset=approved_asset,
            manual_review_marker=manual_review_marker,
            retry_result=retry_result,
        )
        return ImageQualityFlowResult(
            status=status,
            generated_asset=asset,
            history=history,
            approved_asset=approved_asset,
            manual_review_marker=manual_review_marker,
            retry_result=retry_result,
            result_fingerprint=_fingerprint(
                result
            ),
        )

    def _required_checks(
        self
    ) -> tuple[str, ...]:
        return tuple(
            check.name
            for check in self.validator.checks
        )

    def _retry_max_attempts(
        self,
        report,
    ) -> int:
        if any(
            failure.failure_type == NUDITY_FAILURE_TYPE
            for failure in report.failures
        ):
            return self.policy.config.max_nudity_candidates
        return self.retry_coordinator.max_attempts


def _flow_status(
    action: str
) -> str:
    if action == "accept":
        return "approved"
    if action == "retry":
        return "retry_requested"
    if action == "manual_review":
        return "manual_review"
    if action == "stop":
        return "stopped"
    raise ValueError(
        f"Unsupported regeneration action: {action}"
    )


def _history_status(
    flow_status: str
) -> str:
    if flow_status == "approved":
        return "accepted"
    if flow_status == "manual_review":
        return "manual_review"
    if flow_status == "stopped":
        return "stopped"
    return "generating"


def _fingerprint(
    result: ImageQualityFlowResult
) -> str:
    canonical = {
        "ImageQualityFlowResult": _canonical_mapping(
            result
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
            if key not in (
                "result_fingerprint",
                "local_artifact_path",
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
            if key != "local_artifact_path"
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
