from abc import ABC, abstractmethod

from certification.factory import (
    create_certification_report,
    create_certification_result,
    create_certification_scenario,
)
from certification.models import (
    CertificationReport,
    CertificationResult,
    CertificationScenario,
)


class ScenarioExecutor(ABC):
    @abstractmethod
    def execute(
        self,
        scenario: CertificationScenario
    ) -> CertificationResult:
        raise NotImplementedError


class VisualCertificationSuite:
    def __init__(
        self,
        *,
        suite_name: str = "visual_certification",
        version: str = "1.0.0",
        backend: str = "",
        model: str = "",
        executor: ScenarioExecutor | None = None
    ) -> None:
        if not suite_name:
            raise ValueError(
                "suite_name is required"
            )
        if not version:
            raise ValueError(
                "version is required"
            )
        self.suite_name = suite_name
        self.version = version
        self.backend = backend
        self.model = model
        self.executor = executor
        self._scenarios: tuple[CertificationScenario, ...] = ()

    @property
    def scenarios(
        self
    ) -> tuple[CertificationScenario, ...]:
        return self._scenarios

    def register_scenario(
        self,
        scenario: CertificationScenario
    ) -> None:
        if any(
            item.scenario_id == scenario.scenario_id
            for item in self._scenarios
        ):
            raise ValueError(
                f"duplicated scenario_id: {scenario.scenario_id}"
            )
        self._scenarios = (
            *self._scenarios,
            scenario,
        )

    def register(
        self,
        *,
        scenario_id: str,
        name: str,
        component: str,
        objective: str,
        tags: tuple[str, ...] = (),
        enabled: bool = True,
        metadata: tuple[tuple[str, str], ...] = (),
    ) -> CertificationScenario:
        scenario = create_certification_scenario(
            scenario_id=scenario_id,
            name=name,
            component=component,
            objective=objective,
            tags=tags,
            enabled=enabled,
            metadata=metadata,
        )
        self.register_scenario(
            scenario
        )
        return scenario

    def run(
        self,
        *,
        generated_at: str = "",
        executor: ScenarioExecutor | None = None
    ) -> CertificationReport:
        scenario_executor = executor or self.executor
        if scenario_executor is None:
            raise ValueError(
                "ScenarioExecutor is required"
            )
        results = tuple(
            self._execute_scenario(
                scenario,
                scenario_executor
            )
            for scenario in self._scenarios
        )
        return create_certification_report(
            version=self.version,
            generated_at=generated_at,
            suite=self.suite_name,
            backend=self.backend,
            model=self.model,
            scenarios=self._scenarios,
            results=results,
        )

    def _execute_scenario(
        self,
        scenario: CertificationScenario,
        executor: ScenarioExecutor
    ) -> CertificationResult:
        if not scenario.enabled:
            return create_certification_result(
                scenario_id=scenario.scenario_id,
                status="SKIPPED",
                attempts=0,
                details="scenario disabled",
            )
        return executor.execute(
            scenario
        )
