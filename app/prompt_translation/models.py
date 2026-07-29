from dataclasses import dataclass, field


@dataclass(frozen=True)
class PromptBudgetPolicy:
    policy_id: str = "flux-safe-v1"
    model_id: str = "flux"
    encoder_id: str = "flux-text-encoder"
    encoder_token_limit: int = 512
    safety_margin_tokens: int = 128
    target_prompt_tokens: int = 220
    warning_prompt_tokens: int = 320
    hard_prompt_tokens: int = 384
    token_count_method: str = "conservative_estimate"
    overflow_behavior: str = "semantic_compaction"
    critical_categories: tuple[str, ...] = (
        "subject",
        "action",
        "environment",
        "composition",
        "constraints",
    )


@dataclass(frozen=True)
class PromptCompilationMetrics:
    prompt_char_count: int = 0
    prompt_word_count: int = 0
    prompt_line_count: int = 0
    prompt_token_count: int = 0
    token_count_method: str = "conservative_estimate"
    target_budget: int = 0
    warning_threshold: int = 0
    hard_limit: int = 0
    compactation_applied: bool = False
    compactation_stages: tuple[str, ...] = field(default_factory=tuple)
    duplicate_fragments_removed: int = 0
    non_visual_fields_removed: int = 0
    semantic_duplicates_removed: int = 0


@dataclass(frozen=True)
class BackendPromptInstruction:
    id: str
    category: str
    source_field: str
    value: str


@dataclass(frozen=True)
class BackendPromptTraceItem:
    instruction_id: str
    source_fields: tuple[str, ...]
    transformation: str


@dataclass(frozen=True)
class BackendPromptTrace:
    source_effective_brief_fingerprint: str = ""
    items: tuple[BackendPromptTraceItem, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class BackendPrompt:
    instructions: tuple[BackendPromptInstruction, ...]
    trace: BackendPromptTrace
    compiled_prompt: str = ""
    budget_policy: PromptBudgetPolicy = field(default_factory=PromptBudgetPolicy)
    metrics: PromptCompilationMetrics = field(default_factory=PromptCompilationMetrics)
    fingerprint: str = ""
