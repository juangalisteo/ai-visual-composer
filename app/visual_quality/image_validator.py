from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
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
from app.visual_quality.nudity_safety import NuditySafetyCheck


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


class ProductValidationCheck(ValidationCheck):
    failure_type: str
    severity: str = "high"
    confidence: float = 0.85
    retry_relevant: bool = True
    evidence_label: str = "deterministic product validation signal"

    def check(
        self,
        asset: GeneratedAsset,
        context: ValidationContext
    ) -> tuple[ValidationFailure, ...]:
        if not _has_failure_signal(
            asset,
            context,
            self.failure_type,
            self.name
        ):
            return ()
        return (
            create_validation_failure(
                failure_type=self.failure_type,
                severity=self.severity,
                confidence=self.confidence,
                evidence=self.evidence_label,
                technical_message=(
                    f"{self.name} rejected an explicit "
                    "product-quality signal"
                ),
                retry_relevant=self.retry_relevant,
            ),
        )


class ArtifactIntegrityCheck(ProductValidationCheck):
    name = "scene_mismatch"
    failure_type = "scene_mismatch"
    check_category = "artifact"
    severity = "critical"
    confidence = 1.0
    retry_relevant = False
    evidence_label = "generated asset file is missing or empty"

    def check(
        self,
        asset: GeneratedAsset,
        context: ValidationContext
    ) -> tuple[ValidationFailure, ...]:
        asset_path = _resolvable_asset_path(
            asset
        )
        if asset_path is None:
            return ()
        if (
            not asset_path.exists()
            or asset_path.is_dir()
            or asset_path.stat().st_size <= 0
        ):
            return (
                create_validation_failure(
                    failure_type=self.failure_type,
                    severity=self.severity,
                    confidence=self.confidence,
                    evidence=str(
                        asset_path
                    ),
                    technical_message="Generated asset file is not readable.",
                    retry_relevant=self.retry_relevant,
                ),
            )
        return ()


class EmptyValidationCheck(ValidationCheck):
    def check(
        self,
        asset: GeneratedAsset,
        context: ValidationContext
    ) -> tuple[ValidationFailure, ...]:
        return ()


class TextCheck(ProductValidationCheck):
    name = "text_detected"
    check_category = "semantic"
    failure_type = "text_detected"


class PseudotextCheck(ProductValidationCheck):
    name = "pseudotext_detected"
    failure_type = "pseudotext_detected"
    check_category = "semantic"


class LogoCheck(ProductValidationCheck):
    name = "logo_detected"
    check_category = "semantic"
    failure_type = "logo_detected"


class BadgeCheck(ProductValidationCheck):
    name = "badge_detected"
    failure_type = "badge_detected"
    check_category = "semantic"


class WatermarkCheck(ProductValidationCheck):
    name = "watermark_detected"
    failure_type = "watermark_detected"
    check_category = "artifact"


class AnatomyCheck(ProductValidationCheck):
    name = "anatomy_error"
    check_category = "visual"
    failure_type = "anatomy_error"


class HandsCheck(ProductValidationCheck):
    name = "hands_error"
    failure_type = "hands_error"
    check_category = "visual"


class FaceCheck(ProductValidationCheck):
    name = "face_error"
    failure_type = "face_error"
    check_category = "visual"


class WardrobeCheck(ProductValidationCheck):
    name = "unsafe_wardrobe"
    check_category = "semantic"
    failure_type = "unsafe_wardrobe"


class IdentityCheck(ProductValidationCheck):
    name = "identity_consistency"
    check_category = "semantic"
    failure_type = "continuity_break"


class ObjectPresenceCheck(ProductValidationCheck):
    name = "object_missing"
    failure_type = "object_missing"
    check_category = "continuity"


class UnexpectedObjectCheck(ProductValidationCheck):
    name = "unexpected_object"
    failure_type = "unexpected_object"
    check_category = "continuity"


class CompositionCheck(ProductValidationCheck):
    name = "composition_failure"
    failure_type = "composition_failure"
    check_category = "composition"


class CroppingCheck(ProductValidationCheck):
    name = "cropping_error"
    failure_type = "cropping_error"
    check_category = "composition"


class ReadabilityCheck(ProductValidationCheck):
    name = "readability_failure"
    failure_type = "readability_failure"
    check_category = "composition"


class BackgroundArtifactCheck(ProductValidationCheck):
    name = "background_artifact"
    failure_type = "background_artifact"
    check_category = "artifact"


class StyleConsistencyCheck(ProductValidationCheck):
    name = "style_drift"
    failure_type = "style_drift"
    check_category = "style"


class LightingCheck(ProductValidationCheck):
    name = "lighting_mismatch"
    failure_type = "lighting_mismatch"
    check_category = "lighting"


class ContinuityCheck(ProductValidationCheck):
    name = "continuity_break"
    failure_type = "continuity_break"
    check_category = "continuity"


def default_product_quality_checks(
) -> tuple[ValidationCheck, ...]:
    return (
        ArtifactIntegrityCheck(),
        TextCheck(),
        PseudotextCheck(),
        LogoCheck(),
        BadgeCheck(),
        WatermarkCheck(),
        AnatomyCheck(),
        HandsCheck(),
        FaceCheck(),
        WardrobeCheck(),
        NuditySafetyCheck(),
        IdentityCheck(),
        ObjectPresenceCheck(),
        UnexpectedObjectCheck(),
        CompositionCheck(),
        CroppingCheck(),
        ReadabilityCheck(),
        BackgroundArtifactCheck(),
        StyleConsistencyCheck(),
        LightingCheck(),
        ContinuityCheck(),
    )


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


def _has_failure_signal(
    asset: GeneratedAsset,
    context: ValidationContext,
    failure_type: str,
    check_name: str
) -> bool:
    aliases = {
        failure_type.lower(),
        check_name.lower(),
        f"quality_failure:{failure_type}".lower(),
        f"visual_quality_failure:{failure_type}".lower(),
    }
    for value in _signal_values(
        asset,
        context
    ):
        normalized = value.lower()
        if normalized in aliases:
            return True
        if normalized in (
            f"{failure_type}:true",
            f"{check_name}:true",
            f"fail:{failure_type}",
            f"reject:{failure_type}",
        ):
            return True
    return False


def _signal_values(
    asset: GeneratedAsset,
    context: ValidationContext
) -> tuple[str, ...]:
    values: list[str] = []
    for key, value in asset.metadata:
        values.append(
            str(
                key
            )
        )
        values.append(
            str(
                value
            )
        )
        values.append(
            f"{key}:{value}"
        )
    values.extend(
        context.restrictions
    )
    values.extend(
        context.expected_identity_markers
    )
    values.extend(
        context.expected_wardrobe_markers
    )
    values.extend(
        context.expected_environment_markers
    )
    return tuple(
        str(
            value
            or ""
        ).strip()
        for value in values
        if str(
            value
            or ""
        ).strip()
    )


def _resolvable_asset_path(
    asset: GeneratedAsset
) -> Path | None:
    path_value = (
        str(
            asset.local_artifact_path
            or ""
        ).strip()
        or str(
            asset.path
            or ""
        ).strip()
    )
    if not path_value:
        return None
    path = Path(
        path_value
    )
    if path.is_absolute() or path.exists():
        return path
    return None
