import hashlib
import json
import re
from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
from typing import Any

from app.cinematic_direction import CinematicDirectionSet
from app.prompt_translation.models import (
    BackendPrompt,
    BackendPromptInstruction,
    BackendPromptTrace,
    BackendPromptTraceItem,
    PromptBudgetPolicy,
    PromptCompilationMetrics,
)
from app.domain import EffectiveVisualBrief, VisualSynthesisResult


class PromptBudgetExceededError(ValueError):
    code = "PROMPT_BUDGET_UNSATISFIABLE"

    def __init__(
        self,
        tokens: int,
        limit: int,
        dominant_categories: tuple[str, ...],
    ) -> None:
        self.tokens = tokens
        self.limit = limit
        self.dominant_categories = dominant_categories
        super().__init__(
            "PROMPT_BUDGET_UNSATISFIABLE: "
            f"{tokens} estimated tokens exceed hard limit {limit}."
        )


@dataclass(frozen=True)
class _PromptCandidate:
    category: str
    source_field: str
    source_fields: tuple[str, ...]
    value: str
    priority: int


class PromptTranslator:
    def __init__(
        self,
        budget_policy: PromptBudgetPolicy | None = None,
    ) -> None:
        self.budget_policy = budget_policy or PromptBudgetPolicy()

    def translate_visual_synthesis_result(
        self,
        visual_synthesis_result: VisualSynthesisResult,
        cinematic_direction_set: CinematicDirectionSet | None = None,
    ) -> BackendPrompt:
        if not isinstance(
            visual_synthesis_result,
            VisualSynthesisResult
        ):
            raise TypeError(
                "PromptTranslator expects a VisualSynthesisResult."
            )
        return self._translate_effective_brief(
            visual_synthesis_result.brief,
            cinematic_direction_set=cinematic_direction_set,
            source_contract="VisualSynthesisResult",
        )

    def translate(
        self,
        effective_brief: EffectiveVisualBrief,
        cinematic_direction_set: CinematicDirectionSet | None = None,
    ) -> BackendPrompt:
        return self._translate_effective_brief(
            effective_brief,
            cinematic_direction_set=cinematic_direction_set,
            source_contract="EffectiveVisualBrief",
        )

    def _translate_effective_brief(
        self,
        effective_brief: EffectiveVisualBrief,
        cinematic_direction_set: CinematicDirectionSet | None = None,
        source_contract: str = "EffectiveVisualBrief",
    ) -> BackendPrompt:
        if not isinstance(
            effective_brief,
            EffectiveVisualBrief
        ):
            raise TypeError(
                "PromptTranslator expects an EffectiveVisualBrief."
            )

        candidates = []
        removed_non_visual = 0
        candidates.extend(
            self._effective_brief_candidates(
                effective_brief,
                source_contract,
            )
        )
        if cinematic_direction_set is not None:
            candidates.extend(
                self._cinematic_candidates(
                    cinematic_direction_set
                )
            )
        removed_non_visual += self._non_visual_field_count(
            effective_brief
        )

        compiled, selected, metrics = self._compile_candidates(
            candidates,
            removed_non_visual,
        )
        trace = BackendPromptTrace(
            source_effective_brief_fingerprint=effective_brief.fingerprint,
            items=tuple(
                BackendPromptTraceItem(
                    instruction_id=_instruction_id(
                        candidate.source_field
                    ),
                    source_fields=candidate.source_fields,
                    transformation="semantic_prompt_compilation",
                )
                for candidate in selected
            ),
        )
        instructions = tuple(
            BackendPromptInstruction(
                id=_instruction_id(
                    candidate.source_field
                ),
                category=candidate.category,
                source_field=candidate.source_field,
                value=candidate.value,
            )
            for candidate in selected
        )
        metrics = PromptCompilationMetrics(
            prompt_char_count=metrics.prompt_char_count,
            prompt_word_count=metrics.prompt_word_count,
            prompt_line_count=metrics.prompt_line_count,
            prompt_token_count=metrics.prompt_token_count,
            token_count_method=metrics.token_count_method,
            target_budget=metrics.target_budget,
            warning_threshold=metrics.warning_threshold,
            hard_limit=metrics.hard_limit,
            compactation_applied=metrics.compactation_applied,
            compactation_stages=metrics.compactation_stages,
            duplicate_fragments_removed=metrics.duplicate_fragments_removed,
            non_visual_fields_removed=metrics.non_visual_fields_removed,
            semantic_duplicates_removed=metrics.semantic_duplicates_removed,
        )
        prompt = BackendPrompt(
            instructions=instructions,
            trace=trace,
            compiled_prompt=compiled,
            budget_policy=self.budget_policy,
            metrics=metrics,
        )
        return BackendPrompt(
            instructions=prompt.instructions,
            trace=prompt.trace,
            compiled_prompt=prompt.compiled_prompt,
            budget_policy=prompt.budget_policy,
            metrics=prompt.metrics,
            fingerprint=self._fingerprint(
                prompt
            ),
        )

    def _effective_brief_candidates(
        self,
        brief: EffectiveVisualBrief,
        source_contract: str,
    ) -> list[_PromptCandidate]:
        prefix = (
            f"{source_contract}.brief"
            if source_contract == "VisualSynthesisResult"
            else source_contract
        )
        fields = (
            ("subject", "visible_subject", 100),
            ("content", "visible_content", 99),
            ("subject", "primary_identity", 98),
            ("subject", "primary_subject", 96),
            ("action", "visible_action", 95),
            ("environment", "visible_environment", 94),
            ("context", "time_context", 70),
            ("content", "filmable_interpretation", 93),
            ("composition", "attention_focus", 88),
            ("composition", "visual_priority", 86),
            ("composition", "visual_priorities", 86),
            ("composition", "narrative_composition", 85),
            ("intention", "dominant_visual_intention", 84),
            ("reading", "visual_reading", 82),
            ("atmosphere", "felt_experience", 78),
            ("continuity", "continuity_links", 82),
            ("objects", "key_objects", 80),
            ("staging", "spatial_relationships", 76),
            ("constraints", "visual_constraints", 100),
            ("style", "visual_bible_coherence", 66),
            ("coherence", "narrative_coherence", 58),
            ("coherence", "intention_coherence", 58),
            ("rhythm", "scene_rhythm", 50),
            ("symbolism", "symbolic_weight", 48),
        )
        candidates = []
        for category, field_name, priority in fields:
            value = getattr(
                brief,
                field_name,
                None
            )
            text = _normalize_value(
                value
            )
            if text:
                candidates.append(
                    _PromptCandidate(
                        category=category,
                        source_field=f"{prefix}.{field_name}",
                        source_fields=(
                            f"{prefix}.{field_name}",
                        ),
                        value=text,
                        priority=priority,
                    )
                )
        candidates.extend(
            self._nested_plan_candidates(
                brief,
                prefix,
            )
        )
        return candidates

    def _nested_plan_candidates(
        self,
        brief: EffectiveVisualBrief,
        prefix: str,
    ) -> list[_PromptCandidate]:
        plan_fields = (
            ("photography", "photography", ("point_of_view", "depth", "photographic_atmosphere"), 74),
            ("composition", "composition", ("visual_hierarchy", "framing", "frame_scale"), 82),
            ("lighting", "lighting", ("source", "quality", "atmosphere"), 82),
            ("color", "color", ("temperature", "palette", "harmony"), 74),
            ("motion", "motion", ("latent_energy", "rhythm", "stability"), 55),
            ("strategy", "visual_strategy", ("representation_approach", "realism_level", "visual_limits"), 64),
            ("staging", "staging", ("main_subject", "environment", "spatial_relationship"), 70),
        )
        candidates = []
        for category, root_field, nested_names, priority in plan_fields:
            plan = getattr(
                brief,
                root_field,
                None
            )
            if plan is None:
                continue
            for nested_name in nested_names:
                value = getattr(
                    plan,
                    nested_name,
                    None
                )
                text = _normalize_value(
                    value
                )
                if text:
                    source_field = f"{prefix}.{root_field}.{nested_name}"
                    candidates.append(
                        _PromptCandidate(
                            category=category,
                            source_field=source_field,
                            source_fields=(
                                source_field,
                            ),
                            value=text,
                            priority=priority,
                        ),
                    )
        return candidates

    def _cinematic_candidates(
        self,
        direction_set: CinematicDirectionSet,
    ) -> list[_PromptCandidate]:
        specs = (
            ("photography", "photography", ("dominant_photographic_language", "point_of_view", "predominant_framing", "perceived_depth"), 72),
            ("lighting", "lighting", ("dominant_lighting", "luminous_atmosphere", "perceived_contrast", "naturalness"), 78),
            ("composition", "composition", ("dominant_composition", "visual_balance", "compositional_depth", "visual_reading_direction"), 78),
            ("color", "color", ("dominant_palette", "color_harmony", "emotional_temperature", "naturalness"), 70),
            ("movement", "movement", ("dominant_movement", "stability", "movement_continuity"), 48),
            ("continuity", "continuity", ("identity_persistence", "wardrobe_consistency", "key_element_preservation", "global_coherence"), 84),
        )
        candidates = []
        for category, component, field_names, priority in specs:
            direction = getattr(
                direction_set,
                component
            )
            if direction is None:
                continue
            for field_name in field_names:
                text = _normalize_value(
                    getattr(
                        direction,
                        field_name,
                        None
                    )
                )
                if text:
                    source_field = f"CinematicDirectionSet.{component}.{field_name}"
                    candidates.append(
                        _PromptCandidate(
                            category=category,
                            source_field=source_field,
                            source_fields=(
                                source_field,
                                f"CinematicDirectionSet.{component}.fingerprint",
                                "CinematicDirectionSet.fingerprint",
                            ),
                            value=text,
                            priority=priority,
                        ),
                    )
        return candidates

    def _compile_candidates(
        self,
        candidates: list[_PromptCandidate],
        removed_non_visual: int,
    ) -> tuple[str, tuple[_PromptCandidate, ...], PromptCompilationMetrics]:
        stages = [
            "extract_visual_operational_fields",
            "normalize_text",
            "filter_non_visual_metadata",
        ]
        normalized = [
            _PromptCandidate(
                category=candidate.category,
                source_field=candidate.source_field,
                source_fields=candidate.source_fields,
                value=_compact_value(
                    candidate.value,
                    max_fragments=_fragment_limit(
                        candidate.priority
                    ),
                    max_words=_word_limit(
                        candidate.priority
                    ),
                ),
                priority=candidate.priority,
            )
            for candidate in candidates
            if candidate.value
        ]
        deduped, exact_removed = _dedupe_candidates(
            normalized
        )
        if exact_removed:
            stages.append(
                "dedupe_exact"
            )
        semantic, semantic_removed = _dedupe_semantic_candidates(
            deduped
        )
        if semantic_removed:
            stages.append(
                "dedupe_semantic"
            )
        selected = _stable_priority_order(
            semantic
        )
        prompt = _compose_prompt(
            selected
        )
        if _estimate_tokens(
            prompt
        ) > self.budget_policy.target_prompt_tokens:
            stages.append(
                "priority_compaction"
            )
            selected = self._fit_budget(
                selected
            )
            prompt = _compose_prompt(
                selected
            )
        tokens = _estimate_tokens(
            prompt
        )
        if tokens > self.budget_policy.hard_prompt_tokens:
            raise PromptBudgetExceededError(
                tokens=tokens,
                limit=self.budget_policy.hard_prompt_tokens,
                dominant_categories=_dominant_categories(
                    selected
                ),
            )
        return (
            prompt,
            tuple(
                selected
            ),
            PromptCompilationMetrics(
                prompt_char_count=len(
                    prompt
                ),
                prompt_word_count=len(
                    prompt.split()
                ),
                prompt_line_count=1 if prompt else 0,
                prompt_token_count=tokens,
                token_count_method=self.budget_policy.token_count_method,
                target_budget=self.budget_policy.target_prompt_tokens,
                warning_threshold=self.budget_policy.warning_prompt_tokens,
                hard_limit=self.budget_policy.hard_prompt_tokens,
                compactation_applied=len(
                    stages
                ) > 3,
                compactation_stages=tuple(
                    stages
                ),
                duplicate_fragments_removed=exact_removed,
                non_visual_fields_removed=removed_non_visual,
                semantic_duplicates_removed=semantic_removed,
            ),
        )

    def _fit_budget(
        self,
        candidates: list[_PromptCandidate],
    ) -> list[_PromptCandidate]:
        required = [
            candidate
            for candidate in candidates
            if candidate.priority >= 90
        ]
        optional = [
            candidate
            for candidate in candidates
            if candidate.priority < 90
        ]
        selected = list(
            required
        )
        for candidate in optional:
            candidate = _PromptCandidate(
                category=candidate.category,
                source_field=candidate.source_field,
                source_fields=candidate.source_fields,
                value=_compact_value(
                    candidate.value,
                    max_fragments=2,
                    max_words=_word_limit(
                        candidate.priority,
                        compact=True
                    ),
                ),
                priority=candidate.priority,
            )
            trial = selected + [
                candidate
            ]
            if _estimate_tokens(
                _compose_prompt(
                    trial
                )
            ) <= self.budget_policy.target_prompt_tokens:
                selected.append(
                    candidate
                )
        if _estimate_tokens(
            _compose_prompt(
                selected
            )
        ) > self.budget_policy.hard_prompt_tokens:
            selected = [
                _PromptCandidate(
                    category=candidate.category,
                    source_field=candidate.source_field,
                    source_fields=candidate.source_fields,
                    value=_compact_value(
                        candidate.value,
                        max_fragments=1,
                        max_words=18,
                    ),
                    priority=candidate.priority,
                )
                for candidate in required
            ]
        return selected

    def _non_visual_field_count(
        self,
        brief: EffectiveVisualBrief
    ) -> int:
        count = 0
        for field_name in NON_OPERATIONAL_EFFECTIVE_FIELDS:
            if getattr(
                brief,
                field_name,
                None
            ):
                count += 1
        return count

    def _fingerprint(
        self,
        prompt: BackendPrompt
    ) -> str:
        canonical = {
            "compiled_prompt": prompt.compiled_prompt,
            "instructions": _canonical_mapping(
                prompt.instructions
            ),
            "trace": _canonical_mapping(
                prompt.trace
            ),
            "budget_policy": _canonical_mapping(
                prompt.budget_policy
            ),
            "metrics": _canonical_mapping(
                prompt.metrics
            ),
        }
        return hashlib.sha256(
            json.dumps(
                canonical,
                sort_keys=True,
                separators=(
                    ",",
                    ":"
                )
            ).encode(
                "utf-8"
            )
        ).hexdigest()


def _normalize_value(
    value: Any
) -> str:
    if isinstance(
        value,
        Enum
    ):
        return _clean(
            value.value
        )
    if isinstance(
        value,
        (
            tuple,
            list,
        )
    ):
        return _join_fragments(
            _clean(
                item
            )
            for item in value
            if _is_scalar(
                item
            )
        )
    if not _is_scalar(
        value
    ):
        return ""
    return _clean(
        value
    )


def _compact_value(
    value: str,
    max_fragments: int,
    max_words: int,
) -> str:
    fragments = _split_fragments(
        value
    )
    deduped = _dedupe_texts(
        fragments
    )
    limited = deduped[
        :max_fragments
    ]
    text = _join_fragments(
        limited
    )
    return _limit_words(
        text,
        max_words
    )


def _split_fragments(
    value: str
) -> tuple[str, ...]:
    parts = re.split(
        r"\s*(?:\||;|\n|,)\s*",
        value
    )
    return tuple(
        _clean(
            part
        )
        for part in parts
        if _clean(
            part
        )
    )


def _limit_words(
    value: str,
    max_words: int,
) -> str:
    words = value.split()
    if len(
        words
    ) <= max_words:
        return value
    return " ".join(
        words[
            :max_words
        ]
    )


def _dedupe_candidates(
    candidates: list[_PromptCandidate]
) -> tuple[list[_PromptCandidate], int]:
    seen = {}
    result = []
    removed = 0
    for candidate in candidates:
        key = (
            candidate.category,
            _semantic_key(
                candidate.value
            ),
        )
        if key in seen:
            index = seen[
                key
            ]
            result[
                index
            ] = _merge_candidate_sources(
                result[
                    index
                ],
                candidate
            )
            removed += 1
            continue
        seen[
            key
        ] = len(
            result
        )
        result.append(
            candidate
        )
    return result, removed


def _dedupe_semantic_candidates(
    candidates: list[_PromptCandidate]
) -> tuple[list[_PromptCandidate], int]:
    seen = []
    result = []
    removed = 0
    for candidate in candidates:
        key = _semantic_key(
            candidate.value
        )
        duplicate_index = None
        for index, item in enumerate(
            seen
        ):
            if _is_semantic_duplicate(
                key,
                item
            ):
                duplicate_index = index
                break
        if duplicate_index is not None:
            result[
                duplicate_index
            ] = _merge_candidate_sources(
                result[
                    duplicate_index
                ],
                candidate
            )
            removed += 1
            continue
        seen.append(
            key
        )
        result.append(
            candidate
        )
    return result, removed


def _merge_candidate_sources(
    existing: _PromptCandidate,
    duplicate: _PromptCandidate,
) -> _PromptCandidate:
    return _PromptCandidate(
        category=existing.category,
        source_field=existing.source_field,
        source_fields=_dedupe_texts(
            existing.source_fields
            + duplicate.source_fields
        ),
        value=existing.value,
        priority=max(
            existing.priority,
            duplicate.priority,
        ),
    )


def _is_semantic_duplicate(
    value: str,
    existing: str,
) -> bool:
    if not value or not existing:
        return False
    if value in existing or existing in value:
        return True
    value_terms = set(
        value.split()
    )
    existing_terms = set(
        existing.split()
    )
    if not value_terms or not existing_terms:
        return False
    overlap = len(
        value_terms & existing_terms
    ) / min(
        len(
            value_terms
        ),
        len(
            existing_terms
        ),
    )
    return overlap >= 0.78


def _stable_priority_order(
    candidates: list[_PromptCandidate]
) -> list[_PromptCandidate]:
    indexed = list(
        enumerate(
            candidates
        )
    )
    indexed.sort(
        key=lambda item: (
            -item[1].priority,
            item[0],
        )
    )
    return [
        item
        for _, item in indexed
    ]


def _compose_prompt(
    candidates: list[_PromptCandidate]
) -> str:
    return ", ".join(
        candidate.value
        for candidate in candidates
        if candidate.value
    )


def _dominant_categories(
    candidates: list[_PromptCandidate]
) -> tuple[str, ...]:
    lengths = {}
    for candidate in candidates:
        lengths[candidate.category] = lengths.get(
            candidate.category,
            0
        ) + len(
            candidate.value
        )
    return tuple(
        category
        for category, _ in sorted(
            lengths.items(),
            key=lambda item: (
                -item[1],
                item[0],
            )
        )[
            :5
        ]
    )


def _fragment_limit(
    priority: int
) -> int:
    if priority >= 90:
        return 4
    if priority >= 75:
        return 3
    return 2


def _word_limit(
    priority: int,
    compact: bool = False,
) -> int:
    if compact:
        if priority >= 80:
            return 18
        return 12
    if priority >= 90:
        return 36
    if priority >= 75:
        return 28
    return 18


def _estimate_tokens(
    value: str
) -> int:
    if not value:
        return 0
    words = len(
        value.split()
    )
    character_estimate = len(
        value
    ) // 4
    return max(
        words,
        character_estimate,
    )


def _instruction_id(
    source_field: str
) -> str:
    return re.sub(
        r"[^a-z0-9_]+",
        "_",
        source_field.lower()
    ).strip(
        "_"
    )


def _clean(
    value: Any
) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(
            value
            or ""
        )
    ).strip()


def _join_fragments(
    values
) -> str:
    return " | ".join(
        _dedupe_texts(
            tuple(
                _clean(
                    value
                )
                for value in values
                if _clean(
                    value
                )
            )
        )
    )


def _dedupe_texts(
    values: tuple[str, ...]
) -> tuple[str, ...]:
    seen = set()
    result = []
    for value in values:
        key = _semantic_key(
            value
        )
        if key in seen:
            continue
        seen.add(
            key
        )
        result.append(
            value
        )
    return tuple(
        result
    )


def _semantic_key(
    value: str
) -> str:
    normalized = re.sub(
        r"[^\w ]+",
        " ",
        value.lower()
    )
    return re.sub(
        r"\s+",
        " ",
        normalized
    ).strip()


def _is_scalar(
    value: Any
) -> bool:
    return isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
            Enum,
        )
    )


def _canonical_mapping(
    value: Any
) -> Any:
    if isinstance(
        value,
        Enum
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
        dict
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
        )
    ):
        return [
            _canonical_mapping(
                item
            )
            for item in value
        ]
    return value


NON_OPERATIONAL_EFFECTIVE_FIELDS = {
    "conflicts",
    "findings",
    "evidences",
    "trace",
    "fingerprint",
    "visual_truth_status",
}
