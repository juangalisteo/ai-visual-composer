import hashlib
from dataclasses import dataclass, field

from app.prompt_translation.models import PromptBudgetPolicy
from app.shared.prompt_metrics import estimate_conservative_tokens
from app.shared.screen_number import screen_decimal


def prompt_fingerprint(
    value: str,
) -> str:
    return hashlib.sha256(
        value.encode(
            "utf-8"
        )
    ).hexdigest()


@dataclass(frozen=True)
class PromptTextMetrics:
    char_count: int
    word_count: int
    line_count: int
    token_count: int
    fingerprint: str
    token_count_method: str = "conservative_estimate"


@dataclass(frozen=True)
class PromptMetricDifference:
    char_count: int
    word_count: int
    line_count: int
    token_count: int
    char_percent: float | None
    word_percent: float | None
    line_percent: float | None
    token_percent: float | None


@dataclass(frozen=True)
class OperationalPromptContribution:
    category: str
    metrics: PromptTextMetrics


@dataclass(frozen=True)
class OperationalPromptObservation:
    compiled_prompt: PromptTextMetrics
    operational_prompt: PromptTextMetrics
    operational_expansion: PromptMetricDifference
    budget_policy_id: str
    model_id: str
    encoder_id: str
    encoder_token_limit: int
    compiled_hard_limit: int
    dominant_categories: tuple[OperationalPromptContribution, ...] = (
        field(default_factory=tuple)
    )


class OperationalPromptBudgetExceededError(ValueError):
    """Raised before ComfyUI receives an over-limit final FLUX prompt."""

    code = "OPERATIONAL_PROMPT_BUDGET_EXCEEDED"

    def __init__(
        self,
        observation: OperationalPromptObservation,
    ) -> None:
        self.observation = observation
        self.final_prompt_tokens = observation.operational_prompt.token_count
        self.encoder_token_limit = observation.encoder_token_limit
        self.compiled_prompt_tokens = observation.compiled_prompt.token_count
        self.compiled_hard_limit = observation.compiled_hard_limit
        self.operational_expansion_tokens = (
            observation.operational_expansion.token_count
        )
        self.operational_expansion_percent = (
            observation.operational_expansion.token_percent
        )
        self.dominant_categories = tuple(
            contribution.category
            for contribution in observation.dominant_categories
        )
        self.details = {
            "final_prompt_tokens": self.final_prompt_tokens,
            "encoder_token_limit": self.encoder_token_limit,
            "compiled_prompt_tokens": self.compiled_prompt_tokens,
            "compiled_hard_limit": self.compiled_hard_limit,
            "operational_expansion_tokens": (
                self.operational_expansion_tokens
            ),
            "operational_expansion_percent": (
                self.operational_expansion_percent
            ),
            "dominant_categories": self.dominant_categories,
        }
        categories = ", ".join(
            self.dominant_categories
        ) or "sin categorías de expansión"
        percent = (
            "n/a"
            if self.operational_expansion_percent is None
            else f"{screen_decimal(self.operational_expansion_percent, 1)} %"
        )
        super().__init__(
            f"{self.code}: el prompt operativo final de FLUX "
            f"({self.final_prompt_tokens} tokens estimados) supera el límite "
            f"del encoder ({self.encoder_token_limit}). Prompt compilado: "
            f"{self.compiled_prompt_tokens}/{self.compiled_hard_limit}; "
            f"expansión operativa: {self.operational_expansion_tokens} "
            f"tokens ({percent}); categorías dominantes: {categories}. "
            "No se enviará a ComfyUI y el prompt no se ha truncado."
        )


def measure_prompt_text(
    value: str,
    token_count_method: str = "conservative_estimate",
) -> PromptTextMetrics:
    if token_count_method != "conservative_estimate":
        raise ValueError(
            "Unsupported prompt token count method: "
            f"{token_count_method}"
        )
    return PromptTextMetrics(
        char_count=len(value),
        word_count=len(value.split()),
        line_count=value.count("\n") + (1 if value else 0),
        token_count=estimate_conservative_tokens(value),
        fingerprint=prompt_fingerprint(value),
        token_count_method=token_count_method,
    )


def build_operational_prompt_observation(
    compiled_prompt: str,
    operational_prompt: str,
    budget_policy: PromptBudgetPolicy,
    composition_parts: tuple[tuple[str, str], ...] = (),
) -> OperationalPromptObservation:
    compiled_metrics = measure_prompt_text(
        compiled_prompt,
        budget_policy.token_count_method,
    )
    operational_metrics = measure_prompt_text(
        operational_prompt,
        budget_policy.token_count_method,
    )
    contributions = tuple(
        OperationalPromptContribution(
            category=category,
            metrics=measure_prompt_text(
                value,
                budget_policy.token_count_method,
            ),
        )
        for category, value in composition_parts
        if category != "compiled_prompt" and value
    )
    return OperationalPromptObservation(
        compiled_prompt=compiled_metrics,
        operational_prompt=operational_metrics,
        operational_expansion=_metric_difference(
            compiled_metrics,
            operational_metrics,
        ),
        budget_policy_id=budget_policy.policy_id,
        model_id=budget_policy.model_id,
        encoder_id=budget_policy.encoder_id,
        encoder_token_limit=budget_policy.encoder_token_limit,
        compiled_hard_limit=budget_policy.hard_prompt_tokens,
        dominant_categories=tuple(
            sorted(
                contributions,
                key=lambda contribution: (
                    contribution.metrics.token_count,
                    contribution.category,
                ),
                reverse=True,
            )[:3]
        ),
    )


def validate_operational_prompt(
    observation: OperationalPromptObservation,
) -> None:
    if (
        observation.operational_prompt.token_count
        > observation.encoder_token_limit
    ):
        raise OperationalPromptBudgetExceededError(
            observation
        )


def _metric_difference(
    compiled: PromptTextMetrics,
    operational: PromptTextMetrics,
) -> PromptMetricDifference:
    return PromptMetricDifference(
        char_count=operational.char_count - compiled.char_count,
        word_count=operational.word_count - compiled.word_count,
        line_count=operational.line_count - compiled.line_count,
        token_count=operational.token_count - compiled.token_count,
        char_percent=_percent_difference(
            compiled.char_count,
            operational.char_count,
        ),
        word_percent=_percent_difference(
            compiled.word_count,
            operational.word_count,
        ),
        line_percent=_percent_difference(
            compiled.line_count,
            operational.line_count,
        ),
        token_percent=_percent_difference(
            compiled.token_count,
            operational.token_count,
        ),
    )


def _percent_difference(
    compiled_value: int,
    operational_value: int,
) -> float | None:
    if not compiled_value:
        return None
    return round(
        (
            (operational_value - compiled_value)
            / compiled_value
        ) * 100,
        3,
    )
