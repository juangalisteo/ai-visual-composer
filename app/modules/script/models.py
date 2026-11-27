from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ScriptGenerationMetadata:
    model: str = ""
    prompt_id: str = ""
    parser_id: str = "script_generation_contract_v1"
    attempt: int = 1
    raw_response: str = ""
    target_words: int = 0
    recommended_min_words: int = 0
    recommended_max_words: int = 0
    actual_words: int = 0
    deviation_percentage: float = 0.0
    # True when Ollama was already asked once to fix the length (before the
    # voice): the single length adjustment of a topic script is spent.
    length_corrected: bool = False


@dataclass(frozen=True)
class ScriptGenerationResult:
    script: str
    word_count: int
    metadata: ScriptGenerationMetadata


@dataclass(frozen=True)
class PreparedScript:
    text: str
    source: str
    path: Path
    word_count: int
    metadata: ScriptGenerationMetadata | None = None
    preparation_status: str = "prepared"


@dataclass(frozen=True)
class ScriptAdjustment:
    """Request to rewrite a topic script whose voice missed the requested duration."""

    previous_script: str
    measured_seconds: float


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
