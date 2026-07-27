from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from app.visual_quality.factory import (
    create_validation_failure,
    create_validation_report,
)
from app.visual_quality.gate import AssetValidator
from app.visual_quality.models import (
    GeneratedAsset,
    ValidationContext,
    ValidationFailure,
    ValidationReport,
)


@dataclass(frozen=True)
class VisionAnalysis:
    check_name: str
    observations: tuple[tuple[str, str], ...] = ()


class VisionEngine(ABC):
    @abstractmethod
    def analyze(
        self,
        asset: GeneratedAsset,
        context: ValidationContext,
        check_name: str
    ) -> VisionAnalysis:
        raise NotImplementedError


class ValidationCheckError(Exception):
    def __init__(
        self,
        check_name: str,
        message: str
    ) -> None:
        super().__init__(
            message
        )
        self.check_name = check_name
        self.message = message


class ValidationCheck(ABC):
    name: str
    check_category: str = "visual"

    @abstractmethod
    def check(
        self,
        asset: GeneratedAsset,
        context: ValidationContext
    ) -> tuple[ValidationFailure, ...]:
        raise NotImplementedError


class EmptyValidationCheck(ValidationCheck):
    def check(
        self,
        asset: GeneratedAsset,
        context: ValidationContext
    ) -> tuple[ValidationFailure, ...]:
        return ()


class TextCheck(EmptyValidationCheck):
    name = "text_detected"
    check_category = "semantic"


class LogoCheck(EmptyValidationCheck):
    name = "logo_detected"
    check_category = "semantic"


class AnatomyCheck(EmptyValidationCheck):
    name = "anatomy_error"
    check_category = "visual"


class WardrobeCheck(EmptyValidationCheck):
    name = "unsafe_wardrobe"
    check_category = "semantic"


class IdentityCheck(EmptyValidationCheck):
    name = "continuity_break"
    check_category = "semantic"


class ImageValidator(AssetValidator):
    def __init__(
        self,
        checks: tuple[ValidationCheck, ...],
        validator_version: str = "1.0.0"
    ) -> None:
        if not validator_version:
            raise ValueError(
                "validator_version is required"
            )
        self.checks = tuple(
            checks
        )
        self.validator_version = validator_version

    def validate(
        self,
        asset: GeneratedAsset,
        context: ValidationContext
    ) -> ValidationReport:
        failures: list[ValidationFailure] = []
        executed_checks: list[str] = []
        for check in self.checks:
            executed_checks.append(
                check.name
            )
            try:
                failures.extend(
                    check.check(
                        asset,
                        context
                    )
                )
            except ValidationCheckError as exc:
                failures.append(
                    create_validation_failure(
                        failure_type="scene_mismatch",
                        severity="medium",
                        confidence=0.0,
                        evidence=exc.check_name,
                        technical_message=exc.message,
                        retry_relevant=False,
                    )
                )
        failure_tuple = tuple(
            failures
        )
        status = (
            "accepted"
            if not failure_tuple
            else "uncertain"
            if _has_controlled_error(
                failure_tuple
            )
            else "rejected"
        )
        return create_validation_report(
            report_id=_report_id(
                asset,
                context,
                self.validator_version,
                tuple(
                    executed_checks
                )
            ),
            asset_id=asset.asset_id,
            scene_id=asset.scene_id,
            status=status,
            score=_score(
                failure_tuple
            ),
            checks=tuple(
                executed_checks
            ),
            failures=failure_tuple,
            severity=_highest_severity(
                failure_tuple
            ),
            requires_manual_review=status == "uncertain",
            validator_version=self.validator_version,
        )


def _report_id(
    asset: GeneratedAsset,
    context: ValidationContext,
    validator_version: str,
    checks: tuple[str, ...]
) -> str:
    check_part = ",".join(
        checks
    )
    return (
        f"{asset.asset_id}:"
        f"{context.context_fingerprint}:"
        f"{validator_version}:"
        f"{check_part}"
    )


def _score(
    failures: tuple[ValidationFailure, ...]
) -> float:
    if not failures:
        return 1.0
    penalties = {
        "low": 0.1,
        "medium": 0.25,
        "high": 0.5,
        "critical": 1.0,
    }
    total = sum(
        penalties.get(
            failure.severity,
            0.25
        )
        for failure in failures
    )
    return max(
        0.0,
        round(
            1.0 - total,
            4
        )
    )


def _highest_severity(
    failures: tuple[ValidationFailure, ...]
) -> str:
    order = {
        "low": 0,
        "medium": 1,
        "high": 2,
        "critical": 3,
    }
    if not failures:
        return "low"
    return max(
        (
            failure.severity
            for failure in failures
        ),
        key=lambda severity: order[severity]
    )


def _has_controlled_error(
    failures: tuple[ValidationFailure, ...]
) -> bool:
    return any(
        failure.failure_type == "scene_mismatch"
        and failure.confidence == 0.0
        for failure in failures
    )
