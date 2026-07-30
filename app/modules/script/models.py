from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScriptGenerationMetadata:
    model: str = ""
    prompt_id: str = ""
    parser_id: str = "script_generation_contract_v1"
    attempt: int = 1
    raw_response: str = ""


@dataclass(frozen=True)
class ScriptGenerationResult:
    script: str
    word_count: int
    metadata: ScriptGenerationMetadata


@dataclass(frozen=True)
class ScriptValidationIssue:
    reason: str
    field: str
    value: str = ""


@dataclass(frozen=True)
class ScriptValidationReport:
    valid: bool
    issues: tuple[ScriptValidationIssue, ...] = field(default_factory=tuple)


class InvalidScriptOutputError(ValueError):
    code = "INVALID_SCRIPT_OUTPUT"

    def __init__(
        self,
        *,
        reason: str,
        field: str,
        original_response: str,
        parser_id: str,
        model: str,
        prompt_id: str,
    ) -> None:
        self.reason = reason
        self.field = field
        self.original_response = original_response
        self.parser_id = parser_id
        self.model = model
        self.prompt_id = prompt_id
        super().__init__(
            "INVALID_SCRIPT_OUTPUT: "
            f"{field}: {reason}"
        )
