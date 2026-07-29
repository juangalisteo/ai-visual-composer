from dataclasses import dataclass, field


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
    fingerprint: str = ""
