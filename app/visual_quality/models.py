from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GeneratedAsset:
    asset_id: str
    scene_id: str
    asset_type: str
    path: str
    attempt_number: int
    generation_attempt_id: str
    width: int
    height: int
    sequence_id: str = ""
    duration: float | None = None
    fps: float | None = None
    generation_fingerprint: str = ""
    local_artifact_path: str = ""
    metadata: tuple[tuple[str, str], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ValidationContext:
    scene_id: str
    validation_profile: str
    sequence_id: str = ""
    expected_identity_markers: tuple[str, ...] = field(default_factory=tuple)
    expected_wardrobe_markers: tuple[str, ...] = field(default_factory=tuple)
    expected_environment_markers: tuple[str, ...] = field(default_factory=tuple)
    previous_accepted_assets: tuple[str, ...] = field(default_factory=tuple)
    restrictions: tuple[str, ...] = field(default_factory=tuple)
    required_checks: tuple[str, ...] = field(default_factory=tuple)
    context_fingerprint: str = ""


@dataclass(frozen=True)
class ValidationFailure:
    failure_type: str
    severity: str
    confidence: float
    evidence: str
    technical_message: str
    retry_relevant: bool
    region: tuple[int, int, int, int] | None = None
    failure_fingerprint: str = ""


@dataclass(frozen=True)
class SeverityDefinition:
    severity: str
    blocks_acceptance: bool
    score_penalty: float
    retry_relevant_by_default: bool
    description: str
    definition_fingerprint: str = ""


@dataclass(frozen=True)
class ConfidenceBand:
    band_id: str
    minimum: float
    maximum: float
    review_recommended: bool
    description: str
    band_fingerprint: str = ""


@dataclass(frozen=True)
class FailureClassification:
    failure_type: str
    category: str
    default_severity: str
    retry_relevant_by_default: bool
    description: str
    classification_fingerprint: str = ""


@dataclass(frozen=True)
class ValidationThresholds:
    thresholds_id: str
    blocking_confidence: float
    manual_review_confidence: float
    high_confidence: float
    version: str = "1.0.0"
    thresholds_fingerprint: str = ""


@dataclass(frozen=True)
class ValidationProfileConfig:
    profile_id: str
    enabled_checks: tuple[str, ...]
    failure_classifications: tuple[FailureClassification, ...]
    severity_definitions: tuple[SeverityDefinition, ...]
    confidence_bands: tuple[ConfidenceBand, ...]
    thresholds: ValidationThresholds
    version: str = "1.0.0"
    profile_fingerprint: str = ""


@dataclass(frozen=True)
class ValidationReport:
    report_id: str
    asset_id: str
    scene_id: str
    status: str
    score: float
    checks: tuple[str, ...] = field(default_factory=tuple)
    failures: tuple[ValidationFailure, ...] = field(default_factory=tuple)
    severity: str = "low"
    requires_manual_review: bool = False
    validator_version: str = "1.0.0"
    validation_fingerprint: str = ""


@dataclass(frozen=True)
class RegenerationDecision:
    decision_id: str
    report_id: str
    action: str
    attempt_number: int
    reason: str
    failure_types: tuple[str, ...] = field(default_factory=tuple)
    next_seed: int | None = None
    manual_review_required: bool = False
    decision_fingerprint: str = ""


@dataclass(frozen=True)
class ApprovedAsset:
    approved_asset_id: str
    generated_asset: GeneratedAsset
    final_validation_report: ValidationReport
    acceptance_decision: RegenerationDecision
    total_attempts: int
    quality_gate_version: str = "1.0.0"
    approval_fingerprint: str = ""


@dataclass(frozen=True)
class ManualReviewMarker:
    marker_id: str
    scene_id: str
    latest_asset: GeneratedAsset
    latest_report: ValidationReport
    attempts: tuple[GeneratedAsset, ...]
    reasons: tuple[str, ...]
    status: str = "pending"
    sequence_id: str = ""
    attempt_artifact_paths: tuple[str, ...] = field(default_factory=tuple)
    marker_fingerprint: str = ""


@dataclass(frozen=True)
class SceneAssetHistory:
    scene_id: str
    generated_assets: tuple[GeneratedAsset, ...]
    validation_reports: tuple[ValidationReport, ...]
    regeneration_decisions: tuple[RegenerationDecision, ...]
    status: str
    sequence_id: str = ""
    approved_asset: ApprovedAsset | None = None
    manual_review_marker: ManualReviewMarker | None = None
    history_fingerprint: str = ""
