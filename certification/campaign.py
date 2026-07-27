from dataclasses import dataclass, field

from certification.factory import (
    create_campaign_report,
    create_certification_scenario,
)
from certification.image_component import (
    CertificationProfile,
    ImageCertificationScenarioLibrary,
)
from certification.models import (
    CampaignReport,
    CertificationCriteria,
    CertificationScenario,
)
from certification.suite import (
    ScenarioExecutor,
    VisualCertificationSuite,
)


@dataclass(frozen=True)
class CampaignRunConfig:
    version: str = "rc0"
    generated_at: str = ""
    backend: str = ""
    model: str = ""
    storage_used: int = 0
    criteria: CertificationCriteria = field(
        default_factory=CertificationCriteria
    )


class RC0CampaignProfiles:
    @classmethod
    def quick(
        cls
    ) -> CertificationProfile:
        return _profile(
            profile_id="rc0_quick",
            name="RC0 Quick",
            target_scenario_count=25,
        )

    @classmethod
    def standard(
        cls
    ) -> CertificationProfile:
        return _profile(
            profile_id="rc0_standard",
            name="RC0 Standard",
            target_scenario_count=100,
        )

    @classmethod
    def full(
        cls
    ) -> CertificationProfile:
        return _profile(
            profile_id="rc0_full",
            name="RC0 Full",
            target_scenario_count=200,
        )


class RealCertificationCampaign:
    def __init__(
        self,
        *,
        profile: CertificationProfile,
        executor: ScenarioExecutor,
        config: CampaignRunConfig | None = None,
    ) -> None:
        if profile.target_scenario_count < 1:
            raise ValueError(
                "profile target_scenario_count must be positive"
            )
        self.profile = profile
        self.executor = executor
        self.config = config or CampaignRunConfig()

    def run(
        self
    ) -> CampaignReport:
        suite = VisualCertificationSuite(
            suite_name="real_certification_campaign",
            version=self.config.version,
            backend=self.config.backend,
            model=self.config.model,
            executor=self.executor,
        )
        for scenario in self.profile.scenarios:
            suite.register_scenario(
                scenario
            )
        certification_report = suite.run(
            generated_at=self.config.generated_at
        )
        return create_campaign_report(
            version=self.config.version,
            generated_at=self.config.generated_at,
            backend=self.config.backend,
            model=self.config.model,
            profile_id=self.profile.profile_id,
            profile_name=self.profile.name,
            target_scenario_count=self.profile.target_scenario_count,
            criteria=self.config.criteria,
            certification_report=certification_report,
            storage_used=self.config.storage_used,
        )


def _profile(
    *,
    profile_id: str,
    name: str,
    target_scenario_count: int,
) -> CertificationProfile:
    return CertificationProfile(
        profile_id=profile_id,
        name=name,
        target_scenario_count=target_scenario_count,
        scenarios=_expand_scenarios(
            target_scenario_count
        ),
    )


def _expand_scenarios(
    target_scenario_count: int
) -> tuple[CertificationScenario, ...]:
    base = ImageCertificationScenarioLibrary.base_scenarios()
    scenarios = []
    for index in range(
        target_scenario_count
    ):
        source = base[
            index % len(
                base
            )
        ]
        variant = index // len(
            base
        ) + 1
        metadata = (
            *source.metadata,
            (
                "base_scenario_id",
                source.scenario_id,
            ),
            (
                "variant",
                str(
                    variant
                ),
            ),
        )
        scenario_id = (
            source.scenario_id
            if variant == 1
            else f"{source.scenario_id}_{variant:03d}"
        )
        scenarios.append(
            create_certification_scenario(
                scenario_id=scenario_id,
                name=(
                    source.name
                    if variant == 1
                    else f"{source.name} {variant:03d}"
                ),
                component=source.component,
                objective=source.objective,
                tags=source.tags,
                enabled=source.enabled,
                metadata=metadata,
            )
        )
    return tuple(
        scenarios
    )
