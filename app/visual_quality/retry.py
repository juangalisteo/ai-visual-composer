from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from app.visual_quality.factory import (
    create_approved_asset,
    create_generated_asset,
    create_manual_review_marker,
    create_scene_asset_history,
)
from app.visual_quality.gate import VisualQualityGateResult
from app.visual_quality.models import (
    ApprovedAsset,
    GeneratedAsset,
    ManualReviewMarker,
    SceneAssetHistory,
)


AttemptGenerator = Callable[[int, int], Path]
AttemptEvaluator = Callable[[GeneratedAsset], VisualQualityGateResult]


@dataclass(frozen=True)
class RetryResult:
    retry_executed: bool
    generated_asset: GeneratedAsset
    attempt_number: int
    seed: int | None
    status: str
    history: SceneAssetHistory
    approved_asset: ApprovedAsset | None = None
    manual_review_marker: ManualReviewMarker | None = None
    result_fingerprint: str = ""


class SeedPolicy:
    def next_seed(
        self,
        *,
        scene_id: str,
        generation_attempt_id: str,
        attempt_number: int,
        base_seed: int = 0
    ) -> int:
        if attempt_number < 1:
            raise ValueError(
                "attempt_number must be at least 1"
            )
        canonical = {
            "base_seed": base_seed,
            "generation_attempt_id": generation_attempt_id,
            "attempt_number": attempt_number,
            "scene_id": scene_id,
        }
        digest = hashlib.sha256(
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
        return int(
            digest[:16],
            16
        ) % 2147483647


class RetryCoordinator:
    def __init__(
        self,
        max_attempts: int = 3,
        seed_policy: SeedPolicy | None = None
    ) -> None:
        if max_attempts < 1:
            raise ValueError(
                "max_attempts must be at least 1"
            )
        self.max_attempts = max_attempts
        self.seed_policy = seed_policy or SeedPolicy()

    def run(
        self,
        *,
        initial_history: SceneAssetHistory,
        width: int,
        height: int,
        generate_attempt: AttemptGenerator,
        evaluate_attempt: AttemptEvaluator,
        base_seed: int = 0,
        max_attempts: int | None = None,
    ) -> RetryResult:
        history = initial_history
        latest_asset = history.generated_assets[-1]
        latest_decision = history.regeneration_decisions[-1]
        latest_seed = None
        retry_executed = False

        effective_max_attempts = (
            self.max_attempts
            if max_attempts is None
            else max_attempts
        )
        while (
            latest_decision.action == "retry"
            and latest_asset.attempt_number < effective_max_attempts
        ):
            next_attempt = latest_asset.attempt_number + 1
            latest_seed = self.seed_policy.next_seed(
                scene_id=latest_asset.scene_id,
                generation_attempt_id=latest_asset.generation_attempt_id,
                attempt_number=next_attempt,
                base_seed=base_seed,
            )
            image_path = generate_attempt(
                next_attempt,
                latest_seed
            )
            next_asset = create_generated_asset(
                asset_id=(
                    f"{latest_asset.scene_id}:attempt-{next_attempt}"
                ),
                scene_id=latest_asset.scene_id,
                sequence_id=latest_asset.sequence_id,
                asset_type=latest_asset.asset_type,
                path=str(
                    image_path
                ),
                attempt_number=next_attempt,
                generation_attempt_id=(
                    f"{latest_asset.scene_id}:attempt-{next_attempt}"
                ),
                width=width,
                height=height,
                local_artifact_path=str(
                    image_path
                ),
                metadata=(
                    (
                        "seed",
                        str(
                            latest_seed
                        ),
                    ),
                ),
            )
            gate_result = evaluate_attempt(
                next_asset
            )
            history = _updated_history(
                history=history,
                asset=next_asset,
                gate_result=gate_result,
                max_attempts=effective_max_attempts,
            )
            latest_asset = next_asset
            latest_decision = gate_result.regeneration_decision
            retry_executed = True

        return _retry_result(
            retry_executed=retry_executed,
            generated_asset=latest_asset,
            seed=latest_seed,
            history=history,
        )


def _updated_history(
    *,
    history: SceneAssetHistory,
    asset: GeneratedAsset,
    gate_result: VisualQualityGateResult,
    max_attempts: int
) -> SceneAssetHistory:
    decision = gate_result.regeneration_decision
    approved_asset = None
    manual_review_marker = None
    status = "generating"
    generated_assets = (
        *history.generated_assets,
        asset,
    )
    validation_reports = (
        *history.validation_reports,
        gate_result.validation_report,
    )
    regeneration_decisions = (
        *history.regeneration_decisions,
        decision,
    )
    if decision.action == "accept":
        status = "accepted"
        approved_asset = create_approved_asset(
            approved_asset_id=(
                f"{asset.asset_id}:approved"
            ),
            generated_asset=asset,
            final_validation_report=gate_result.validation_report,
            acceptance_decision=decision,
            total_attempts=asset.attempt_number,
        )
    elif decision.action == "manual_review":
        status = "manual_review"
        manual_review_marker = create_manual_review_marker(
            marker_id=(
                f"{asset.asset_id}:manual-review"
            ),
            scene_id=asset.scene_id,
            sequence_id=asset.sequence_id,
            latest_asset=asset,
            latest_report=gate_result.validation_report,
            attempts=generated_assets,
            reasons=(
                decision.reason,
            ),
            attempt_artifact_paths=tuple(
                item.path
                for item in generated_assets
            ),
        )
    elif decision.action == "stop":
        status = "stopped"
    elif (
        decision.action == "retry"
        and asset.attempt_number >= max_attempts
    ):
        status = "manual_review"
        manual_review_marker = create_manual_review_marker(
            marker_id=(
                f"{asset.asset_id}:manual-review"
            ),
            scene_id=asset.scene_id,
            sequence_id=asset.sequence_id,
            latest_asset=asset,
            latest_report=gate_result.validation_report,
            attempts=generated_assets,
            reasons=(
                "maximum attempts reached",
            ),
            attempt_artifact_paths=tuple(
                item.path
                for item in generated_assets
            ),
        )

    return create_scene_asset_history(
        scene_id=history.scene_id,
        sequence_id=history.sequence_id,
        generated_assets=generated_assets,
        validation_reports=validation_reports,
        regeneration_decisions=regeneration_decisions,
        approved_asset=approved_asset,
        manual_review_marker=manual_review_marker,
        status=status,
    )


def _retry_result(
    *,
    retry_executed: bool,
    generated_asset: GeneratedAsset,
    seed: int | None,
    history: SceneAssetHistory
) -> RetryResult:
    approved_asset = history.approved_asset
    manual_review_marker = history.manual_review_marker
    status = _status_from_history(
        history
    )
    result = RetryResult(
        retry_executed=retry_executed,
        generated_asset=generated_asset,
        attempt_number=generated_asset.attempt_number,
        seed=seed,
        status=status,
        history=history,
        approved_asset=approved_asset,
        manual_review_marker=manual_review_marker,
    )
    return RetryResult(
        retry_executed=retry_executed,
        generated_asset=generated_asset,
        attempt_number=generated_asset.attempt_number,
        seed=seed,
        status=status,
        history=history,
        approved_asset=approved_asset,
        manual_review_marker=manual_review_marker,
        result_fingerprint=_fingerprint(
            result
        ),
    )


def _status_from_history(
    history: SceneAssetHistory
) -> str:
    if history.status == "accepted":
        return "approved"
    if history.status == "manual_review":
        return "manual_review"
    if history.status == "stopped":
        return "stopped"
    return "retry_requested"


def _fingerprint(
    result: RetryResult
) -> str:
    canonical = {
        "RetryResult": _canonical_mapping(
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
