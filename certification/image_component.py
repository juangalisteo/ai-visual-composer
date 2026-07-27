from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from certification.factory import (
    create_certification_result,
    create_certification_scenario,
)
from certification.models import CertificationResult, CertificationScenario
from certification.suite import ScenarioExecutor


ImageComponentRunner = Callable[
    [CertificationScenario],
    "ImageCertificationObservation",
]


@dataclass(frozen=True)
class ArtifactRetentionPolicy:
    keep_pass_approved_asset: bool = True
    keep_retry_rejected_metadata: bool = True
    keep_retry_rejected_heavy_artifacts: bool = False
    keep_manual_review_latest_asset: bool = True
    keep_manual_review_metadata: bool = True


@dataclass(frozen=True)
class ImageCertificationObservation:
    status: str = ""
    attempts: int = 1
    approved: bool = False
    retry_count: int = 0
    manual_review: bool = False
    stopped: bool = False
    execution_time: float = 0.0
    details: str = ""
    errors: tuple[str, ...] = field(default_factory=tuple)
    metadata: tuple[tuple[str, str], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CertificationProfile:
    profile_id: str
    name: str
    target_scenario_count: int
    scenarios: tuple[CertificationScenario, ...]


class ImageCertificationExecutor(ScenarioExecutor):
    def __init__(
        self,
        *,
        runner: ImageComponentRunner,
        artifact_retention_policy: ArtifactRetentionPolicy | None = None
    ) -> None:
        self.runner = runner
        self.artifact_retention_policy = (
            artifact_retention_policy
            or ArtifactRetentionPolicy()
        )

    def execute(
        self,
        scenario: CertificationScenario
    ) -> CertificationResult:
        try:
            observation = self.runner(
                scenario
            )
        except Exception as error:
            return create_certification_result(
                scenario_id=scenario.scenario_id,
                status="FAIL",
                attempts=0,
                details="image component execution failed",
                errors=(
                    str(
                        error
                    ),
                ),
            )
        return create_certification_result(
            scenario_id=scenario.scenario_id,
            status=_status_from_observation(
                observation
            ),
            attempts=observation.attempts,
            approved=observation.approved,
            retry_count=observation.retry_count,
            manual_review=observation.manual_review,
            stopped=observation.stopped,
            execution_time=observation.execution_time,
            details=observation.details,
            errors=observation.errors,
            metadata=observation.metadata,
        )


class ImageCertificationScenarioLibrary:
    @staticmethod
    def base_scenarios(
    ) -> tuple[CertificationScenario, ...]:
        return tuple(
            _scenario(
                scenario_id=scenario_id,
                name=name,
                objective=objective,
                tags=tags,
                acceptance_criteria=criteria,
            )
            for scenario_id, name, objective, tags, criteria in (
                (
                    "portrait",
                    "Portrait",
                    "Certify a simple human portrait.",
                    (
                        "image",
                        "portrait",
                    ),
                    "approved image or deterministic manual review",
                ),
                (
                    "hospital",
                    "Hospital",
                    "Certify medical-context image behavior.",
                    (
                        "image",
                        "context",
                    ),
                    "no runtime failure and traceable result",
                ),
                (
                    "fantasy",
                    "Fantasy",
                    "Certify stylized scene behavior.",
                    (
                        "image",
                        "fantasy",
                    ),
                    "status reported without changing runtime",
                ),
                (
                    "forest",
                    "Forest",
                    "Certify natural environment behavior.",
                    (
                        "image",
                        "nature",
                    ),
                    "stable certification result",
                ),
                (
                    "animals",
                    "Animals",
                    "Certify non-human subject behavior.",
                    (
                        "image",
                        "animals",
                    ),
                    "scenario result is measurable",
                ),
                (
                    "hands",
                    "Hands",
                    "Certify hand-focused scenario behavior.",
                    (
                        "image",
                        "anatomy",
                    ),
                    "attempts and result are recorded",
                ),
                (
                    "wardrobe",
                    "Wardrobe",
                    "Certify wardrobe restriction behavior.",
                    (
                        "image",
                        "wardrobe",
                    ),
                    "approval or review is explicit",
                ),
                (
                    "identity",
                    "Identity",
                    "Certify identity consistency behavior.",
                    (
                        "image",
                        "identity",
                    ),
                    "identity scenario remains traceable",
                ),
                (
                    "continuity",
                    "Continuity",
                    "Certify sequence continuity behavior.",
                    (
                        "image",
                        "continuity",
                    ),
                    "continuity outcome is recorded",
                ),
                (
                    "retry",
                    "Retry",
                    "Certify controlled retry behavior.",
                    (
                        "image",
                        "retry",
                    ),
                    "retry count and final status are measured",
                ),
                (
                    "rollback",
                    "Rollback",
                    "Certify validation-disabled behavior.",
                    (
                        "image",
                        "rollback",
                    ),
                    "single-runtime rollback readiness remains measurable",
                ),
                (
                    "history",
                    "History",
                    "Certify scene asset history behavior.",
                    (
                        "image",
                        "history",
                    ),
                    "attempt history is represented",
                ),
            )
        )

    @classmethod
    def quick_profile(
        cls
    ) -> CertificationProfile:
        return CertificationProfile(
            profile_id="quick",
            name="Quick",
            target_scenario_count=25,
            scenarios=cls.base_scenarios(),
        )

    @classmethod
    def standard_profile(
        cls
    ) -> CertificationProfile:
        return CertificationProfile(
            profile_id="standard",
            name="Standard",
            target_scenario_count=100,
            scenarios=cls.base_scenarios(),
        )

    @classmethod
    def full_profile(
        cls
    ) -> CertificationProfile:
        return CertificationProfile(
            profile_id="full",
            name="Full",
            target_scenario_count=200,
            scenarios=cls.base_scenarios(),
        )


def _scenario(
    *,
    scenario_id: str,
    name: str,
    objective: str,
    tags: tuple[str, ...],
    acceptance_criteria: str
) -> CertificationScenario:
    return create_certification_scenario(
        scenario_id=scenario_id,
        name=name,
        component="image",
        objective=objective,
        tags=tags,
        metadata=(
            (
                "acceptance_criteria",
                acceptance_criteria,
            ),
        ),
    )


def _status_from_observation(
    observation: ImageCertificationObservation
) -> str:
    if observation.status:
        return observation.status
    if observation.stopped:
        return "FAIL"
    if observation.manual_review:
        return "WARNING"
    if observation.approved:
        return "PASS"
    return "WARNING"
