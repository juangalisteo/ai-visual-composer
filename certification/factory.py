import hashlib
import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from certification.models import (
    CAMPAIGN_RESULTS,
    CERTIFICATION_STATUSES,
    CampaignReport,
    CertificationCriteria,
    CertificationMetrics,
    CertificationReport,
    CertificationResult,
    CertificationScenario,
    CertificationSummary,
)


def create_certification_scenario(
    *,
    scenario_id: str,
    name: str,
    component: str,
    objective: str,
    tags: tuple[str, ...] = (),
    enabled: bool = True,
    metadata: tuple[tuple[str, str], ...] = (),
) -> CertificationScenario:
    _require(
        scenario_id,
        "scenario_id is required"
    )
    _require(
        name,
        "name is required"
    )
    _require(
        component,
        "component is required"
    )
    _require(
        objective,
        "objective is required"
    )
    return CertificationScenario(
        scenario_id=scenario_id,
        name=name,
        component=component,
        objective=objective,
        tags=tuple(
            tags
        ),
        enabled=enabled,
        metadata=_sorted_metadata(
            metadata
        ),
    )


def create_certification_result(
    *,
    scenario_id: str,
    status: str,
    attempts: int = 1,
    approved: bool = False,
    retry_count: int = 0,
    manual_review: bool = False,
    stopped: bool = False,
    execution_time: float = 0.0,
    details: str = "",
    errors: tuple[str, ...] = (),
    metadata: tuple[tuple[str, str], ...] = (),
) -> CertificationResult:
    _require(
        scenario_id,
        "scenario_id is required"
    )
    _require_status(
        status
    )
    if attempts < 0:
        raise ValueError(
            "attempts cannot be negative"
        )
    if retry_count < 0:
        raise ValueError(
            "retry_count cannot be negative"
        )
    result = CertificationResult(
        scenario_id=scenario_id,
        status=status,
        attempts=attempts,
        approved=approved,
        retry_count=retry_count,
        manual_review=manual_review,
        stopped=stopped,
        execution_time=execution_time,
        details=details,
        errors=tuple(
            errors
        ),
        metadata=_sorted_metadata(
            metadata
        ),
    )
    return CertificationResult(
        **{
            **asdict(
                result
            ),
            "result_fingerprint": _fingerprint(
                "CertificationResult",
                result
            ),
        }
    )


def create_certification_metrics(
    results: tuple[CertificationResult, ...]
) -> CertificationMetrics:
    total = len(
        results
    )
    passed = _count_status(
        results,
        "PASS"
    )
    failed = _count_status(
        results,
        "FAIL"
    )
    warnings = _count_status(
        results,
        "WARNING"
    )
    skipped = _count_status(
        results,
        "SKIPPED"
    )
    approved = sum(
        1
        for result in results
        if result.approved
    )
    retry = sum(
        result.retry_count
        for result in results
    )
    manual_review = sum(
        1
        for result in results
        if result.manual_review
    )
    stopped = sum(
        1
        for result in results
        if result.stopped
    )
    retried_results = tuple(
        result
        for result in results
        if result.retry_count > 0
    )
    retry_success = sum(
        1
        for result in retried_results
        if result.approved
    )
    first_attempt_success = sum(
        1
        for result in results
        if result.approved
        and result.attempts <= 1
    )
    attempts = sum(
        result.attempts
        for result in results
    )
    execution_time = round(
        sum(
            result.execution_time
            for result in results
        ),
        4
    )
    metrics = CertificationMetrics(
        total=total,
        passed=passed,
        failed=failed,
        warnings=warnings,
        skipped=skipped,
        approved=approved,
        retry=retry,
        manual_review=manual_review,
        stopped=stopped,
        average_attempts=_rate(
            attempts,
            total
        ),
        retry_rate=_rate(
            retry,
            total
        ),
        approval_rate=_rate(
            approved,
            total
        ),
        manual_review_rate=_rate(
            manual_review,
            total
        ),
        stopped_rate=_rate(
            stopped,
            total
        ),
        retry_success_rate=_rate(
            retry_success,
            len(
                retried_results
            )
        ),
        first_attempt_success_rate=_rate(
            first_attempt_success,
            total
        ),
        execution_time=execution_time,
    )
    return CertificationMetrics(
        **{
            **asdict(
                metrics
            ),
            "metrics_fingerprint": _fingerprint(
                "CertificationMetrics",
                metrics
            ),
        }
    )


def create_certification_summary(
    *,
    title: str,
    version: str,
    backend: str,
    metrics: CertificationMetrics,
    determinism: str = "not_evaluated",
    rollback: str = "not_evaluated",
) -> CertificationSummary:
    _require(
        title,
        "title is required"
    )
    _require(
        version,
        "version is required"
    )
    final_result = _final_result(
        metrics
    )
    summary = CertificationSummary(
        title=title,
        version=version,
        backend=backend,
        approval_rate=metrics.approval_rate,
        retry_rate=metrics.retry_rate,
        manual_review_rate=metrics.manual_review_rate,
        stopped=metrics.stopped,
        determinism=determinism,
        rollback=rollback,
        final_result=final_result,
    )
    return CertificationSummary(
        **{
            **asdict(
                summary
            ),
            "summary_fingerprint": _fingerprint(
                "CertificationSummary",
                summary
            ),
        }
    )


def create_certification_report(
    *,
    version: str,
    generated_at: str,
    suite: str,
    backend: str,
    model: str,
    scenarios: tuple[CertificationScenario, ...],
    results: tuple[CertificationResult, ...],
) -> CertificationReport:
    _require(
        version,
        "version is required"
    )
    _require(
        suite,
        "suite is required"
    )
    metrics = create_certification_metrics(
        results
    )
    summary = create_certification_summary(
        title="Visual Component Certification",
        version=version,
        backend=backend,
        metrics=metrics,
    )
    report = CertificationReport(
        version=version,
        generated_at=generated_at,
        suite=suite,
        backend=backend,
        model=model,
        scenarios=tuple(
            scenarios
        ),
        metrics=metrics,
        results=tuple(
            results
        ),
        summary=summary,
    )
    return CertificationReport(
        **{
            **asdict(
                report
            ),
            "scenarios": report.scenarios,
            "metrics": report.metrics,
            "results": report.results,
            "summary": report.summary,
            "report_fingerprint": _fingerprint(
                "CertificationReport",
                report
            ),
        }
    )


def create_campaign_report(
    *,
    version: str,
    generated_at: str,
    backend: str,
    model: str,
    profile_id: str,
    profile_name: str,
    target_scenario_count: int,
    criteria: CertificationCriteria,
    certification_report: CertificationReport,
    storage_used: int = 0,
) -> CampaignReport:
    _require(
        version,
        "version is required"
    )
    _require(
        profile_id,
        "profile_id is required"
    )
    _require(
        profile_name,
        "profile_name is required"
    )
    if target_scenario_count < 0:
        raise ValueError(
            "target_scenario_count cannot be negative"
        )
    if storage_used < 0:
        raise ValueError(
            "storage_used cannot be negative"
        )
    warning_scenarios = _scenario_ids_by_status(
        certification_report.results,
        "WARNING"
    )
    failed_scenarios = _scenario_ids_by_status(
        certification_report.results,
        "FAIL"
    )
    skipped_scenarios = _scenario_ids_by_status(
        certification_report.results,
        "SKIPPED"
    )
    final_result = _campaign_result(
        certification_report,
        criteria
    )
    report = CampaignReport(
        version=version,
        generated_at=generated_at,
        backend=backend,
        model=model,
        profile_id=profile_id,
        profile_name=profile_name,
        target_scenario_count=target_scenario_count,
        executed_scenarios=certification_report.metrics.total,
        criteria=criteria,
        certification_report=certification_report,
        warning_scenarios=warning_scenarios,
        failed_scenarios=failed_scenarios,
        skipped_scenarios=skipped_scenarios,
        total_execution_time=certification_report.metrics.execution_time,
        storage_used=storage_used,
        final_result=final_result,
    )
    return CampaignReport(
        **{
            **asdict(
                report
            ),
            "criteria": report.criteria,
            "certification_report": report.certification_report,
            "report_fingerprint": _fingerprint(
                "CampaignReport",
                report
            ),
        }
    )


def _final_result(
    metrics: CertificationMetrics
) -> str:
    if metrics.total == 0:
        return "SKIPPED"
    if metrics.failed:
        return "FAIL"
    if metrics.warnings or metrics.manual_review or metrics.stopped:
        return "WARNING"
    return "PASS"


def _campaign_result(
    report: CertificationReport,
    criteria: CertificationCriteria
) -> str:
    _require_campaign_result_support()
    metrics = report.metrics
    if metrics.failed > criteria.max_critical_failures:
        return "NOT_CERTIFIED"
    if (
        criteria.minimum_approval_rate is not None
        and metrics.approval_rate < criteria.minimum_approval_rate
    ):
        return "NOT_CERTIFIED"
    if (
        criteria.maximum_manual_review_rate is not None
        and metrics.manual_review_rate > criteria.maximum_manual_review_rate
    ):
        return "NOT_CERTIFIED"
    if (
        criteria.maximum_stopped_rate is not None
        and metrics.stopped_rate > criteria.maximum_stopped_rate
    ):
        return "NOT_CERTIFIED"
    if _required_tags_failed(
        report,
        criteria.required_pass_tags
    ):
        return "NOT_CERTIFIED"
    if (
        metrics.warnings
        or metrics.manual_review
        or metrics.skipped
        or report.scenarios
        and metrics.total < len(
            report.scenarios
        )
    ):
        return "CONDITIONALLY_CERTIFIED"
    return "CERTIFIED"


def _required_tags_failed(
    report: CertificationReport,
    required_tags: tuple[str, ...]
) -> bool:
    if not required_tags:
        return False
    result_by_id = {
        result.scenario_id: result
        for result in report.results
    }
    for scenario in report.scenarios:
        if not set(
            scenario.tags
        ).intersection(
            required_tags
        ):
            continue
        result = result_by_id.get(
            scenario.scenario_id
        )
        if result is None or result.status != "PASS":
            return True
    return False


def _scenario_ids_by_status(
    results: tuple[CertificationResult, ...],
    status: str
) -> tuple[str, ...]:
    return tuple(
        result.scenario_id
        for result in results
        if result.status == status
    )


def _require_campaign_result_support(
) -> None:
    expected = (
        "CERTIFIED",
        "CONDITIONALLY_CERTIFIED",
        "NOT_CERTIFIED",
    )
    if CAMPAIGN_RESULTS != expected:
        raise ValueError(
            "unsupported campaign results"
        )


def _count_status(
    results: tuple[CertificationResult, ...],
    status: str
) -> int:
    return sum(
        1
        for result in results
        if result.status == status
    )


def _rate(
    numerator: float,
    denominator: int
) -> float:
    if denominator == 0:
        return 0.0
    return round(
        numerator / denominator,
        4
    )


def _require(
    value: str,
    message: str
) -> None:
    if not value:
        raise ValueError(
            message
        )


def _require_status(
    status: str
) -> None:
    if status not in CERTIFICATION_STATUSES:
        raise ValueError(
            f"status must be one of {CERTIFICATION_STATUSES}"
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


def _fingerprint(
    label: str,
    value: object
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
