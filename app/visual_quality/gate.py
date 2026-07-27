import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
from typing import Any

from app.visual_quality.models import (
    GeneratedAsset,
    RegenerationDecision,
    ValidationContext,
    ValidationReport,
)
from app.visual_quality.policy import RegenerationPolicy


class AssetValidator(ABC):
    @abstractmethod
    def validate(
        self,
        asset: GeneratedAsset,
        context: ValidationContext
    ) -> ValidationReport:
        raise NotImplementedError


@dataclass(frozen=True)
class VisualQualityGateResult:
    generated_asset: GeneratedAsset
    validation_report: ValidationReport
    regeneration_decision: RegenerationDecision
    result_fingerprint: str = ""


class VisualQualityGate:
    def __init__(
        self,
        validator: AssetValidator,
        policy: RegenerationPolicy
    ) -> None:
        self.validator = validator
        self.policy = policy

    def evaluate(
        self,
        asset: GeneratedAsset,
        context: ValidationContext
    ) -> VisualQualityGateResult:
        report = self.validator.validate(
            asset,
            context
        )
        _ensure_report_matches_asset(
            report,
            asset
        )
        decision = self.policy.decide(
            report,
            attempt_number=asset.attempt_number
        )
        _ensure_decision_matches_report(
            decision,
            report
        )
        result = VisualQualityGateResult(
            generated_asset=asset,
            validation_report=report,
            regeneration_decision=decision,
        )
        return VisualQualityGateResult(
            generated_asset=asset,
            validation_report=report,
            regeneration_decision=decision,
            result_fingerprint=_fingerprint(
                result
            ),
        )


def _ensure_report_matches_asset(
    report: ValidationReport,
    asset: GeneratedAsset
) -> None:
    if report.asset_id != asset.asset_id:
        raise ValueError(
            "ValidationReport must belong to GeneratedAsset"
        )
    if report.scene_id != asset.scene_id:
        raise ValueError(
            "ValidationReport scene_id must match GeneratedAsset"
        )


def _ensure_decision_matches_report(
    decision: RegenerationDecision,
    report: ValidationReport
) -> None:
    if decision.report_id != report.report_id:
        raise ValueError(
            "RegenerationDecision must belong to ValidationReport"
        )


def _fingerprint(
    result: VisualQualityGateResult
) -> str:
    canonical = {
        "VisualQualityGateResult": _canonical_mapping(
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
            if key != "result_fingerprint"
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
