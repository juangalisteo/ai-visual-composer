from dataclasses import dataclass

from app.visual_quality.factory import create_regeneration_decision
from app.visual_quality.models import RegenerationDecision, ValidationReport


@dataclass(frozen=True)
class RegenerationPolicyConfig:
    max_attempts: int = 3
    version: str = "1.0.0"

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError(
                "max_attempts must be at least 1"
            )
        if not self.version:
            raise ValueError(
                "version is required"
            )


class RegenerationPolicy:
    def __init__(
        self,
        config: RegenerationPolicyConfig | None = None
    ) -> None:
        self.config = config or RegenerationPolicyConfig()

    def decide(
        self,
        report: ValidationReport,
        attempt_number: int
    ) -> RegenerationDecision:
        if attempt_number < 1:
            raise ValueError(
                "attempt_number must be at least 1"
            )
        failure_types = tuple(
            failure.failure_type
            for failure in report.failures
        )
        if report.status == "accepted":
            return create_regeneration_decision(
                decision_id=self._decision_id(
                    report,
                    "accept",
                    attempt_number
                ),
                report_id=report.report_id,
                action="accept",
                attempt_number=attempt_number,
                reason="validation accepted",
                failure_types=failure_types,
                validation_report=report,
            )
        if self._has_non_regenerable_critical_failure(
            report
        ):
            return create_regeneration_decision(
                decision_id=self._decision_id(
                    report,
                    "stop",
                    attempt_number
                ),
                report_id=report.report_id,
                action="stop",
                attempt_number=attempt_number,
                reason="critical non-regenerable validation failure",
                failure_types=failure_types,
                validation_report=report,
            )
        if report.requires_manual_review:
            return create_regeneration_decision(
                decision_id=self._decision_id(
                    report,
                    "manual_review",
                    attempt_number
                ),
                report_id=report.report_id,
                action="manual_review",
                attempt_number=attempt_number,
                reason="validation report requires manual review",
                failure_types=failure_types,
                manual_review_required=True,
                validation_report=report,
            )
        if attempt_number >= self.config.max_attempts:
            return create_regeneration_decision(
                decision_id=self._decision_id(
                    report,
                    "manual_review",
                    attempt_number
                ),
                report_id=report.report_id,
                action="manual_review",
                attempt_number=attempt_number,
                reason="maximum attempts reached",
                failure_types=failure_types,
                manual_review_required=True,
                validation_report=report,
            )
        if self._has_retry_relevant_failure(
            report
        ):
            return create_regeneration_decision(
                decision_id=self._decision_id(
                    report,
                    "retry",
                    attempt_number
                ),
                report_id=report.report_id,
                action="retry",
                attempt_number=attempt_number,
                reason="retry-relevant validation failure",
                failure_types=failure_types,
                validation_report=report,
            )
        return create_regeneration_decision(
            decision_id=self._decision_id(
                report,
                "manual_review",
                attempt_number
            ),
            report_id=report.report_id,
            action="manual_review",
            attempt_number=attempt_number,
            reason="validation failure is not automatically retryable",
            failure_types=failure_types,
            manual_review_required=True,
            validation_report=report,
        )

    def _decision_id(
        self,
        report: ValidationReport,
        action: str,
        attempt_number: int
    ) -> str:
        return (
            f"{report.report_id}:"
            f"{self.config.version}:"
            f"attempt-{attempt_number}:"
            f"{action}"
        )

    def _has_retry_relevant_failure(
        self,
        report: ValidationReport
    ) -> bool:
        return any(
            failure.retry_relevant
            for failure in report.failures
        )

    def _has_non_regenerable_critical_failure(
        self,
        report: ValidationReport
    ) -> bool:
        return any(
            failure.severity == "critical"
            and not failure.retry_relevant
            for failure in report.failures
        )
