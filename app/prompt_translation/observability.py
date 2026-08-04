import hashlib
import json
from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any


@dataclass(frozen=True)
class PromptCandidateObservation:
    category: str
    source_field: str
    source_fields: tuple[str, ...]
    value: str
    priority: int
    semantic_unit: str = ""
    protected: bool = False
    protection_reasons: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PromptCandidateMergeObservation:
    merge_kind: str
    retained_candidate: PromptCandidateObservation
    merged_candidate: PromptCandidateObservation
    output_candidate: PromptCandidateObservation
    reason: str


@dataclass(frozen=True)
class PromptSemanticSurvivalObservation:
    source_field: str
    category: str
    semantic_unit: str
    protected: bool
    input_value: str
    final_source_field: str = ""
    final_value: str = ""
    status: str = ""
    reason: str = ""


@dataclass(frozen=True)
class PromptCandidateUtilizationObservation:
    source_field: str
    category: str
    semantic_unit: str
    protected: bool
    candidate_count: int = 0
    selected_count: int = 0
    exact_merged_count: int = 0
    semantic_merged_count: int = 0
    protected_merge_blocked_count: int = 0
    prompt_visible_count: int = 0
    provenance_only_count: int = 0
    not_preserved_count: int = 0


@dataclass(frozen=True)
class PromptCompilationStageObservation:
    stage_id: str
    description: str
    candidates: tuple[PromptCandidateObservation, ...] = field(default_factory=tuple)
    merge_pairs: tuple[PromptCandidateMergeObservation, ...] = field(default_factory=tuple)
    blocked_merge_pairs: tuple[PromptCandidateMergeObservation, ...] = field(default_factory=tuple)
    semantic_survival: tuple[PromptSemanticSurvivalObservation, ...] = field(default_factory=tuple)
    candidate_utilization: tuple[PromptCandidateUtilizationObservation, ...] = field(default_factory=tuple)
    prompt: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PromptTranslationObservation:
    source_contract: str
    source_effective_brief_fingerprint: str
    source_cinematic_direction_set_fingerprint: str = ""
    stages: tuple[PromptCompilationStageObservation, ...] = field(default_factory=tuple)
    compiled_prompt: str = ""
    backend_prompt_fingerprint: str = ""
    fingerprint: str = ""

    def __post_init__(
        self
    ) -> None:
        if self.fingerprint:
            return
        object.__setattr__(
            self,
            "fingerprint",
            _fingerprint(
                "PromptTranslationObservation",
                {
                    "source_contract": self.source_contract,
                    "source_effective_brief_fingerprint": (
                        self.source_effective_brief_fingerprint
                    ),
                    "source_cinematic_direction_set_fingerprint": (
                        self.source_cinematic_direction_set_fingerprint
                    ),
                    "stages": _canonical_mapping(
                        self.stages
                    ),
                    "compiled_prompt": self.compiled_prompt,
                    "backend_prompt_fingerprint": (
                        self.backend_prompt_fingerprint
                    ),
                },
            ),
        )


def _fingerprint(
    label: str,
    payload: Any,
) -> str:
    return hashlib.sha256(
        json.dumps(
            {
                "label": label,
                "payload": _canonical_mapping(
                    payload
                ),
            },
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def _canonical_mapping(
    value: Any
) -> Any:
    if isinstance(
        value,
        Enum,
    ):
        return value.value
    if is_dataclass(
        value
    ):
        return {
            key: _canonical_mapping(
                item
            )
            for key, item in asdict(
                value
            ).items()
        }
    if isinstance(
        value,
        dict,
    ):
        return {
            key: _canonical_mapping(
                item
            )
            for key, item in sorted(
                value.items()
            )
        }
    if isinstance(
        value,
        (
            tuple,
            list,
        ),
    ):
        return [
            _canonical_mapping(
                item
            )
            for item in value
        ]
    return value
