from dataclasses import dataclass, field


CERTIFICATION_STATUSES = (
    "PASS",
    "FAIL",
    "WARNING",
    "SKIPPED",
)


@dataclass(frozen=True)
class CertificationScenario:
    scenario_id: str
    name: str
    component: str
    objective: str
    tags: tuple[str, ...] = field(default_factory=tuple)
    enabled: bool = True
    metadata: tuple[tuple[str, str], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CertificationResult:
    scenario_id: str
    status: str
    attempts: int = 1
    approved: bool = False
    retry_count: int = 0
    manual_review: bool = False
    stopped: bool = False
    execution_time: float = 0.0
    details: str = ""
    errors: tuple[str, ...] = field(default_factory=tuple)
    metadata: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    result_fingerprint: str = ""


@dataclass(frozen=True)
class CertificationMetrics:
    total: int = 0
    passed: int = 0
    failed: int = 0
    warnings: int = 0
    skipped: int = 0
    approved: int = 0
    retry: int = 0
    manual_review: int = 0
    stopped: int = 0
    average_attempts: float = 0.0
    retry_rate: float = 0.0
    approval_rate: float = 0.0
    manual_review_rate: float = 0.0
    stopped_rate: float = 0.0
    retry_success_rate: float = 0.0
    first_attempt_success_rate: float = 0.0
    execution_time: float = 0.0
    metrics_fingerprint: str = ""


@dataclass(frozen=True)
class CertificationSummary:
    title: str
    version: str
    backend: str = ""
    approval_rate: float = 0.0
    retry_rate: float = 0.0
    manual_review_rate: float = 0.0
    stopped: int = 0
    determinism: str = "not_evaluated"
    rollback: str = "not_evaluated"
    final_result: str = "SKIPPED"
    summary_fingerprint: str = ""


@dataclass(frozen=True)
class CertificationReport:
    version: str
    generated_at: str
    suite: str
    backend: str
    model: str
    scenarios: tuple[CertificationScenario, ...]
    metrics: CertificationMetrics
    results: tuple[CertificationResult, ...]
    summary: CertificationSummary
    report_fingerprint: str = ""


CAMPAIGN_RESULTS = (
    "CERTIFIED",
    "CONDITIONALLY_CERTIFIED",
    "NOT_CERTIFIED",
)


@dataclass(frozen=True)
class CertificationCriteria:
    max_critical_failures: int = 0
    minimum_approval_rate: float | None = None
    maximum_manual_review_rate: float | None = None
    maximum_stopped_rate: float | None = None
    required_pass_tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CampaignReport:
    version: str
    generated_at: str
    backend: str
    model: str
    profile_id: str
    profile_name: str
    target_scenario_count: int
    executed_scenarios: int
    criteria: CertificationCriteria
    certification_report: CertificationReport
    warning_scenarios: tuple[str, ...] = field(default_factory=tuple)
    failed_scenarios: tuple[str, ...] = field(default_factory=tuple)
    skipped_scenarios: tuple[str, ...] = field(default_factory=tuple)
    total_execution_time: float = 0.0
    storage_used: int = 0
    final_result: str = "NOT_CERTIFIED"
    report_fingerprint: str = ""
