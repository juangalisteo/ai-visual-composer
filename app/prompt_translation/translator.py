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
from app.prompt_translation.observability import (
    PromptCandidateUtilizationObservation,
    PromptCandidateObservation,
    PromptCandidateMergeObservation,
    PromptCompilationStageObservation,
    PromptSemanticSurvivalObservation,
    PromptTranslationObservation,
)
from app.shared.prompt_metrics import (
    estimate_conservative_tokens,
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
    semantic_unit: str = ""
    protected: bool = False
    protection_reasons: tuple[str, ...] = ()


class PromptTranslator:
    def __init__(
        self,
        budget_policy: PromptBudgetPolicy | None = None,
        capture_observation: bool = True,
    ) -> None:
        self.budget_policy = budget_policy or PromptBudgetPolicy()
        self.capture_observation = capture_observation
        self.last_observation: PromptTranslationObservation | None = None

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

        self.last_observation = None
        observation_stages: list[PromptCompilationStageObservation] = []
        if self.capture_observation:
            observation_stages.append(
                PromptCompilationStageObservation(
                    stage_id="input_effective_visual_brief",
                    description="Input EffectiveVisualBrief received by PromptTranslator.",
                    metadata={
                        "source_contract": source_contract,
                        "source_effective_brief_fingerprint": (
                            effective_brief.fingerprint
                        ),
                        "field_count": len(
                            EffectiveVisualBrief.__dataclass_fields__
                        ),
                        "input_effective_visual_brief": _canonical_mapping(
                            effective_brief
                        ),
                    },
                )
            )
        candidates = []
        removed_non_visual = 0
        effective_candidates = self._effective_brief_candidates(
            effective_brief,
            source_contract,
        )
        candidates.extend(
            effective_candidates
        )
        cinematic_candidates = []
        if cinematic_direction_set is not None:
            cinematic_candidates = self._cinematic_candidates(
                cinematic_direction_set
            )
            candidates.extend(
                cinematic_candidates
            )
        if self.capture_observation:
            observation_stages.append(
                PromptCompilationStageObservation(
                    stage_id="candidate_selection",
                    description="Candidate prompt fragments selected from available source contracts.",
                    candidates=_candidate_observations(
                        candidates
                    ),
                    metadata={
                        "effective_brief_candidate_count": len(
                            effective_candidates
                        ),
                        "cinematic_candidate_count": len(
                            cinematic_candidates
                        ),
                        "total_candidate_count": len(
                            candidates
                        ),
                    },
                )
            )
        removed_non_visual += self._non_visual_field_count(
            effective_brief
        )

        compiled, selected, metrics, merge_pairs, blocked_merge_pairs = self._compile_candidates(
            candidates,
            removed_non_visual,
            observation_stages=(
                observation_stages
                if self.capture_observation
                else None
            ),
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
        final_prompt = BackendPrompt(
            instructions=prompt.instructions,
            trace=prompt.trace,
            compiled_prompt=prompt.compiled_prompt,
            budget_policy=prompt.budget_policy,
            metrics=prompt.metrics,
            fingerprint=self._fingerprint(
                prompt
            ),
        )
        if self.capture_observation:
            semantic_survival = _semantic_survival_observations(
                candidates,
                selected,
            )
            candidate_utilization = _candidate_utilization_observations(
                candidates,
                selected,
                merge_pairs,
                blocked_merge_pairs,
                semantic_survival,
            )
            observation_stages.append(
                PromptCompilationStageObservation(
                    stage_id="semantic_survival_metrics",
                    description="Semantic source fields compared against final selected prompt instructions.",
                    semantic_survival=semantic_survival,
                    metadata=_semantic_survival_metadata(
                        semantic_survival
                    ),
                )
            )
            observation_stages.append(
                PromptCompilationStageObservation(
                    stage_id="candidate_utilisation_report",
                    description="Candidate utilisation by source field, category, semantic unit and preservation status.",
                    candidate_utilization=candidate_utilization,
                    metadata=_candidate_utilization_metadata(
                        candidate_utilization
                    ),
                )
            )
            observation_stages.append(
                PromptCompilationStageObservation(
                    stage_id="compiled_prompt",
                    description="Final BackendPrompt compiled by PromptTranslator.",
                    candidates=_candidate_observations(
                        selected
                    ),
                    prompt=final_prompt.compiled_prompt,
                    metadata={
                        "backend_prompt_fingerprint": final_prompt.fingerprint,
                        "instruction_count": len(
                            final_prompt.instructions
                        ),
                        "trace_item_count": len(
                            final_prompt.trace.items
                        ),
                        "metrics": _canonical_mapping(
                            final_prompt.metrics
                        ),
                    },
                )
            )
            self.last_observation = PromptTranslationObservation(
                source_contract=source_contract,
                source_effective_brief_fingerprint=effective_brief.fingerprint,
                source_cinematic_direction_set_fingerprint=(
                    cinematic_direction_set.fingerprint
                    if cinematic_direction_set is not None
                    else ""
                ),
                stages=tuple(
                    observation_stages
                ),
                compiled_prompt=final_prompt.compiled_prompt,
                backend_prompt_fingerprint=final_prompt.fingerprint,
            )
        return final_prompt

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
                    _prompt_candidate(
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
            _abstract_intent_operational_candidates(
                brief,
                prefix,
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
                        _prompt_candidate(
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
                        _prompt_candidate(
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
        observation_stages: list[PromptCompilationStageObservation] | None = None,
    ) -> tuple[
        str,
        tuple[_PromptCandidate, ...],
        PromptCompilationMetrics,
        tuple[PromptCandidateMergeObservation, ...],
        tuple[PromptCandidateMergeObservation, ...],
    ]:
        stages = [
            "extract_visual_operational_fields",
            "normalize_text",
            "filter_non_visual_metadata",
        ]
        if observation_stages is not None:
            observation_stages.append(
                PromptCompilationStageObservation(
                    stage_id="compilation_start",
                    description="Prompt compilation started with selected candidates.",
                    candidates=_candidate_observations(
                        candidates
                    ),
                    metadata={
                        "candidate_count": len(
                            candidates
                        ),
                        "removed_non_visual_field_count": removed_non_visual,
                        "target_budget": self.budget_policy.target_prompt_tokens,
                        "hard_limit": self.budget_policy.hard_prompt_tokens,
                    },
                )
            )
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
                semantic_unit=candidate.semantic_unit,
                protected=candidate.protected,
                protection_reasons=candidate.protection_reasons,
            )
            for candidate in candidates
            if candidate.value
        ]
        merge_pairs = []
        blocked_merge_pairs = []
        deduped, exact_removed = _dedupe_candidates(
            normalized,
            merge_pairs=merge_pairs
            if observation_stages is not None
            else None,
        )
        if exact_removed:
            stages.append(
                "dedupe_exact"
            )
        semantic, semantic_removed, semantic_blocked = _dedupe_semantic_candidates(
            deduped,
            merge_pairs=merge_pairs
            if observation_stages is not None
            else None,
            blocked_merge_pairs=blocked_merge_pairs
            if observation_stages is not None
            else None,
        )
        if semantic_removed:
            stages.append(
                "dedupe_semantic"
            )
        if observation_stages is not None:
            observation_stages.append(
                PromptCompilationStageObservation(
                    stage_id="deduplication",
                    description="Exact and semantic duplicate prompt fragments removed.",
                    candidates=_candidate_observations(
                        semantic
                    ),
                    merge_pairs=tuple(
                        merge_pairs
                    ),
                    blocked_merge_pairs=tuple(
                        blocked_merge_pairs
                    ),
                    metadata={
                        "normalized_candidate_count": len(
                            normalized
                        ),
                        "exact_duplicates_removed": exact_removed,
                        "semantic_duplicates_removed": semantic_removed,
                        "semantic_merges_blocked_by_protection": semantic_blocked,
                        "remaining_candidate_count": len(
                            semantic
                        ),
                        "protected_candidate_count": _protected_candidate_count(
                            semantic
                        ),
                    },
                )
            )
        selected = _stable_priority_order(
            semantic
        )
        if observation_stages is not None:
            observation_stages.append(
                PromptCompilationStageObservation(
                    stage_id="fragment_prioritisation",
                    description="Prompt fragments ordered by stable priority.",
                    candidates=_candidate_observations(
                        selected
                    ),
                    metadata={
                        "selected_candidate_count": len(
                            selected
                        ),
                        "priority_order": tuple(
                            candidate.priority
                            for candidate in selected
                        ),
                    },
                )
            )
        prompt = _compose_prompt(
            selected
        )
        budget_prompt_before = prompt
        budget_candidates_before = tuple(
            selected
        )
        budget_reduction_applied = False
        if _estimate_tokens(
            prompt
        ) > self.budget_policy.target_prompt_tokens:
            stages.append(
                "priority_compaction"
            )
            budget_reduction_applied = True
            selected = self._fit_budget(
                selected
            )
            prompt = _compose_prompt(
                selected
            )
        if observation_stages is not None:
            observation_stages.append(
                PromptCompilationStageObservation(
                    stage_id="budget_reduction",
                    description="Budget reduction evaluated and applied only when required.",
                    candidates=_candidate_observations(
                        selected
                    ),
                    prompt=prompt,
                    metadata={
                        "applied": budget_reduction_applied,
                        "candidate_count_before": len(
                            budget_candidates_before
                        ),
                        "candidate_count_after": len(
                            selected
                        ),
                        "token_count_before": _estimate_tokens(
                            budget_prompt_before
                        ),
                        "token_count_after": _estimate_tokens(
                            prompt
                        ),
                        "target_budget": self.budget_policy.target_prompt_tokens,
                        "hard_limit": self.budget_policy.hard_prompt_tokens,
                    },
                )
            )
            observation_stages.append(
                PromptCompilationStageObservation(
                    stage_id="prompt_assembly",
                    description="Prompt assembled from selected fragments.",
                    candidates=_candidate_observations(
                        selected
                    ),
                    prompt=prompt,
                    metadata={
                        "assembled_fragment_count": len(
                            selected
                        ),
                        "estimated_tokens": _estimate_tokens(
                            prompt
                        ),
                    },
                )
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
            tuple(
                merge_pairs
            ),
            tuple(
                blocked_merge_pairs
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
                semantic_unit=candidate.semantic_unit,
                protected=candidate.protected,
                protection_reasons=candidate.protection_reasons,
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
                    semantic_unit=candidate.semantic_unit,
                    protected=candidate.protected,
                    protection_reasons=candidate.protection_reasons,
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


PROTECTED_SEMANTIC_FIELD_UNITS = {
    "visible_subject": "visual_truth.subject",
    "primary_identity": "visual_truth.subject",
    "visible_action": "visual_truth.action",
    "visible_environment": "visual_truth.environment",
    "filmable_interpretation": "visual_truth.filmable_interpretation",
    "key_objects": "visual_truth.key_objects",
    "spatial_relationships": "visual_truth.spatial_relationships",
    "continuity_links": "visual_truth.continuity",
    "visual_constraints": "visual_truth.constraints",
    "attention_focus": "visual_truth.attention_focus",
    "visual_priority": "visual_truth.visual_priority",
    "visual_priorities": "visual_truth.visual_priority",
}

PROTECTED_CINEMATIC_COMPONENTS = {
    "continuity": "cinematic.continuity",
}


def _prompt_candidate(
    category: str,
    source_field: str,
    source_fields: tuple[str, ...],
    value: str,
    priority: int,
) -> _PromptCandidate:
    semantic_unit, reasons = _protection_for_source(
        source_field,
        category,
    )
    return _PromptCandidate(
        category=category,
        source_field=source_field,
        source_fields=source_fields,
        value=value,
        priority=priority,
        semantic_unit=semantic_unit,
        protected=bool(
            reasons
        ),
        protection_reasons=reasons,
    )


def _protection_for_source(
    source_field: str,
    category: str,
) -> tuple[str, tuple[str, ...]]:
    parts = tuple(
        part
        for part in source_field.split(
            "."
        )
        if part
    )
    field_name = parts[
        -1
    ] if parts else source_field
    component = parts[
        1
    ] if len(
        parts
    ) > 2 and parts[
        0
    ] == "CinematicDirectionSet" else ""
    if field_name in PROTECTED_SEMANTIC_FIELD_UNITS:
        return (
            PROTECTED_SEMANTIC_FIELD_UNITS[
                field_name
            ],
            (
                "protected_visual_truth_unit",
            ),
        )
    if component in PROTECTED_CINEMATIC_COMPONENTS:
        return (
            PROTECTED_CINEMATIC_COMPONENTS[
                component
            ],
            (
                "protected_continuity_provenance",
            ),
        )
    if category == "continuity":
        return (
            "continuity",
            (
                "protected_continuity_provenance",
            ),
        )
    return "", ()


def _abstract_intent_operational_candidates(
    brief: EffectiveVisualBrief,
    prefix: str,
) -> list[_PromptCandidate]:
    if not _normalize_value(
        getattr(
            brief,
            "abstract_source",
            "",
        )
    ):
        return []
    fragments = _abstract_operational_fragments(
        brief
    )
    if not fragments:
        return []
    source_field = f"{prefix}.abstract_source.operational_equivalent"
    return [
        _PromptCandidate(
            category="intention",
            source_field=source_field,
            source_fields=(
                f"{prefix}.abstract_source",
                *(
                    f"{prefix}.{field_name}"
                    for field_name in _abstract_supporting_fields(
                        brief
                    )
                ),
            ),
            value=_join_fragments(
                fragments
            ),
            priority=87,
            semantic_unit="operational.abstract_intent",
            protected=False,
            protection_reasons=(),
        )
    ]


def _abstract_operational_fragments(
    brief: EffectiveVisualBrief,
) -> tuple[str, ...]:
    fragments = []
    for field_name in (
        "filmable_interpretation",
        "attention_focus",
        "felt_experience",
    ):
        text = _normalize_value(
            getattr(
                brief,
                field_name,
                "",
            )
        )
        if text:
            fragments.append(
                text
            )
    for field_name in (
        "key_objects",
        "spatial_relationships",
    ):
        text = _normalize_value(
            getattr(
                brief,
                field_name,
                (),
            )
        )
        if text:
            fragments.append(
                text
            )
    return tuple(
        fragments
    )


def _abstract_supporting_fields(
    brief: EffectiveVisualBrief,
) -> tuple[str, ...]:
    return tuple(
        field_name
        for field_name in (
            "filmable_interpretation",
            "attention_focus",
            "felt_experience",
            "key_objects",
            "spatial_relationships",
        )
        if _normalize_value(
            getattr(
                brief,
                field_name,
                (),
            )
        )
    )


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
    candidates: list[_PromptCandidate],
    merge_pairs: list[PromptCandidateMergeObservation] | None = None,
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
            retained = result[
                index
            ]
            merged = _merge_candidate_sources(
                retained,
                candidate
            )
            if merge_pairs is not None:
                merge_pairs.append(
                    PromptCandidateMergeObservation(
                        merge_kind="exact",
                        retained_candidate=_candidate_observation(
                            retained
                        ),
                        merged_candidate=_candidate_observation(
                            candidate
                        ),
                        output_candidate=_candidate_observation(
                            merged
                        ),
                        reason="same_category_and_same_semantic_key",
                    )
                )
            result[
                index
            ] = merged
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
    candidates: list[_PromptCandidate],
    merge_pairs: list[PromptCandidateMergeObservation] | None = None,
    blocked_merge_pairs: list[PromptCandidateMergeObservation] | None = None,
) -> tuple[list[_PromptCandidate], int, int]:
    seen = []
    result = []
    removed = 0
    blocked = 0
    for candidate in candidates:
        key = _semantic_key(
            candidate.value
        )
        duplicate_index = None
        for index, item in enumerate(
            seen
        ):
            if not _is_semantic_duplicate(
                key,
                item
            ):
                continue
            if not _semantic_merge_allowed(
                candidate,
                result[
                    index
                ],
            ):
                if blocked_merge_pairs is not None:
                    blocked_merge_pairs.append(
                        PromptCandidateMergeObservation(
                            merge_kind="semantic_blocked",
                            retained_candidate=_candidate_observation(
                                result[
                                    index
                                ]
                            ),
                            merged_candidate=_candidate_observation(
                                candidate
                            ),
                            output_candidate=_candidate_observation(
                                result[
                                    index
                                ]
                            ),
                            reason="protected_semantic_unit_boundary",
                        )
                    )
                blocked += 1
                continue
            else:
                duplicate_index = index
                break
        if duplicate_index is not None:
            retained = result[
                duplicate_index
            ]
            merged = _merge_semantic_candidate_sources(
                retained,
                candidate
            )
            if merge_pairs is not None:
                merge_pairs.append(
                    PromptCandidateMergeObservation(
                        merge_kind="semantic",
                        retained_candidate=_candidate_observation(
                            retained
                        ),
                        merged_candidate=_candidate_observation(
                            candidate
                        ),
                        output_candidate=_candidate_observation(
                            merged
                        ),
                        reason="semantic_key_overlap",
                    )
                )
            result[
                duplicate_index
            ] = merged
            removed += 1
            continue
        seen.append(
            key
        )
        result.append(
            candidate
        )
    return result, removed, blocked


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
        semantic_unit=existing.semantic_unit or duplicate.semantic_unit,
        protected=existing.protected or duplicate.protected,
        protection_reasons=_dedupe_texts(
            existing.protection_reasons
            + duplicate.protection_reasons
        ),
    )


def _merge_semantic_candidate_sources(
    existing: _PromptCandidate,
    duplicate: _PromptCandidate,
) -> _PromptCandidate:
    if duplicate.protected and not existing.protected:
        return _PromptCandidate(
            category=duplicate.category,
            source_field=duplicate.source_field,
            source_fields=_dedupe_texts(
                duplicate.source_fields
                + existing.source_fields
            ),
            value=duplicate.value,
            priority=max(
                existing.priority,
                duplicate.priority,
            ),
            semantic_unit=duplicate.semantic_unit,
            protected=True,
            protection_reasons=_dedupe_texts(
                duplicate.protection_reasons
                + existing.protection_reasons
            ),
        )
    return _merge_candidate_sources(
        existing,
        duplicate,
    )


def _semantic_merge_allowed(
    candidate: _PromptCandidate,
    retained: _PromptCandidate,
) -> bool:
    return not (
        candidate.protected
        and retained.protected
        and candidate.semantic_unit != retained.semantic_unit
    )


def _protected_candidate_count(
    candidates: list[_PromptCandidate]
) -> int:
    return sum(
        1
        for candidate in candidates
        if candidate.protected
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
    fragments = []
    for candidate in candidates:
        fragments.extend(
            _split_fragments(
                candidate.value
            )
        )
    return ", ".join(
        _dedupe_texts(
            tuple(
                fragments
            )
        )
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


def _candidate_observations(
    candidates
) -> tuple[PromptCandidateObservation, ...]:
    return tuple(
        _candidate_observation(
            candidate
        )
        for candidate in candidates
    )


def _candidate_observation(
    candidate
) -> PromptCandidateObservation:
    return PromptCandidateObservation(
        category=candidate.category,
        source_field=candidate.source_field,
        source_fields=candidate.source_fields,
        value=candidate.value,
        priority=candidate.priority,
        semantic_unit=candidate.semantic_unit,
        protected=candidate.protected,
        protection_reasons=candidate.protection_reasons,
    )


def _semantic_survival_observations(
    input_candidates: list[_PromptCandidate],
    selected_candidates: tuple[_PromptCandidate, ...],
) -> tuple[PromptSemanticSurvivalObservation, ...]:
    observations = []
    for candidate in input_candidates:
        final_candidate = _selected_candidate_for_source(
            candidate.source_field,
            selected_candidates,
        )
        if final_candidate is None:
            if (
                candidate.semantic_unit == "operational.abstract_intent"
                and _value_fragments_visible(
                    candidate.value,
                    selected_candidates,
                )
            ):
                observations.append(
                    PromptSemanticSurvivalObservation(
                        source_field=candidate.source_field,
                        category=candidate.category,
                        semantic_unit=candidate.semantic_unit,
                        protected=candidate.protected,
                        input_value=candidate.value,
                        final_value=candidate.value,
                        status="operational_equivalent_visible",
                        reason="abstract_intent_equivalent_already_visible_through_concrete_fields",
                    )
                )
                continue
            observations.append(
                PromptSemanticSurvivalObservation(
                    source_field=candidate.source_field,
                    category=candidate.category,
                    semantic_unit=candidate.semantic_unit,
                    protected=candidate.protected,
                    input_value=candidate.value,
                    status="not_preserved",
                    reason="source_field_absent_from_final_prompt_trace",
                )
            )
            continue
        if _semantic_key(
            candidate.value
        ) == _semantic_key(
            final_candidate.value
        ):
            status = "fully_preserved"
            reason = "source_field_selected_as_final_prompt_instruction"
        else:
            status = "provenance_preserved"
            reason = "source_field_merged_into_final_prompt_instruction"
        observations.append(
            PromptSemanticSurvivalObservation(
                source_field=candidate.source_field,
                category=candidate.category,
                semantic_unit=candidate.semantic_unit,
                protected=candidate.protected,
                input_value=candidate.value,
                final_source_field=final_candidate.source_field,
                final_value=final_candidate.value,
                status=status,
                reason=reason,
            )
        )
    return tuple(
        observations
    )


def _selected_candidate_for_source(
    source_field: str,
    selected_candidates: tuple[_PromptCandidate, ...],
) -> _PromptCandidate | None:
    for candidate in selected_candidates:
        if source_field in candidate.source_fields:
            return candidate
    return None


def _value_fragments_visible(
    value: str,
    selected_candidates: tuple[_PromptCandidate, ...],
) -> bool:
    fragments = _split_fragments(
        value
    )
    if not fragments:
        return False
    prompt = _compose_prompt(
        list(
            selected_candidates
        )
    )
    prompt_key = _semantic_key(
        prompt
    )
    return any(
        _semantic_key(
            fragment
        ) in prompt_key
        for fragment in fragments
    )


def _semantic_survival_metadata(
    observations: tuple[PromptSemanticSurvivalObservation, ...],
) -> dict[str, Any]:
    status_counts = {}
    protected_status_counts = {}
    for observation in observations:
        status_counts[
            observation.status
        ] = status_counts.get(
            observation.status,
            0,
        ) + 1
        if observation.protected:
            protected_status_counts[
                observation.status
            ] = protected_status_counts.get(
                observation.status,
                0,
            ) + 1
    return {
        "input_semantic_field_count": len(
            observations
        ),
        "status_counts": status_counts,
        "protected_status_counts": protected_status_counts,
        "fully_preserved_count": status_counts.get(
            "fully_preserved",
            0,
        ),
        "provenance_preserved_count": status_counts.get(
            "provenance_preserved",
            0,
        ),
        "not_preserved_count": status_counts.get(
            "not_preserved",
            0,
        ),
        "operational_equivalent_visible_count": status_counts.get(
            "operational_equivalent_visible",
            0,
        ),
        "protected_not_preserved_count": protected_status_counts.get(
            "not_preserved",
            0,
        ),
    }


def _candidate_utilization_observations(
    input_candidates: list[_PromptCandidate],
    selected_candidates: tuple[_PromptCandidate, ...],
    merge_pairs: tuple[PromptCandidateMergeObservation, ...],
    blocked_merge_pairs: tuple[PromptCandidateMergeObservation, ...],
    semantic_survival: tuple[PromptSemanticSurvivalObservation, ...],
) -> tuple[PromptCandidateUtilizationObservation, ...]:
    utilization = []
    source_fields = _dedupe_texts(
        tuple(
            candidate.source_field
            for candidate in input_candidates
        )
    )
    for source_field in source_fields:
        candidates = tuple(
            candidate
            for candidate in input_candidates
            if candidate.source_field == source_field
        )
        survival_items = tuple(
            item
            for item in semantic_survival
            if item.source_field == source_field
        )
        selected_count = sum(
            1
            for candidate in selected_candidates
            if source_field == candidate.source_field
        )
        prompt_visible_count = sum(
            1
            for item in survival_items
            if item.status == "fully_preserved"
        )
        provenance_only_count = sum(
            1
            for item in survival_items
            if item.status == "provenance_preserved"
        )
        not_preserved_count = sum(
            1
            for item in survival_items
            if item.status == "not_preserved"
        )
        sample = candidates[
            0
        ]
        utilization.append(
            PromptCandidateUtilizationObservation(
                source_field=source_field,
                category=sample.category,
                semantic_unit=sample.semantic_unit,
                protected=sample.protected,
                candidate_count=len(
                    candidates
                ),
                selected_count=selected_count,
                exact_merged_count=_merge_count_for_source(
                    source_field,
                    merge_pairs,
                    "exact",
                ),
                semantic_merged_count=_merge_count_for_source(
                    source_field,
                    merge_pairs,
                    "semantic",
                ),
                protected_merge_blocked_count=_merge_count_for_source(
                    source_field,
                    blocked_merge_pairs,
                    "semantic_blocked",
                ),
                prompt_visible_count=prompt_visible_count,
                provenance_only_count=provenance_only_count,
                not_preserved_count=not_preserved_count,
            )
        )
    return tuple(
        utilization
    )


def _candidate_utilization_metadata(
    observations: tuple[PromptCandidateUtilizationObservation, ...],
) -> dict[str, Any]:
    by_category = {}
    for observation in observations:
        category = by_category.setdefault(
            observation.category,
            {
                "candidate_count": 0,
                "selected_count": 0,
                "prompt_visible_count": 0,
                "provenance_only_count": 0,
                "not_preserved_count": 0,
            },
        )
        category[
            "candidate_count"
        ] += observation.candidate_count
        category[
            "selected_count"
        ] += observation.selected_count
        category[
            "prompt_visible_count"
        ] += observation.prompt_visible_count
        category[
            "provenance_only_count"
        ] += observation.provenance_only_count
        category[
            "not_preserved_count"
        ] += observation.not_preserved_count
    return {
        "source_field_count": len(
            observations
        ),
        "protected_source_field_count": sum(
            1
            for observation in observations
            if observation.protected
        ),
        "candidate_count": sum(
            observation.candidate_count
            for observation in observations
        ),
        "selected_count": sum(
            observation.selected_count
            for observation in observations
        ),
        "prompt_visible_count": sum(
            observation.prompt_visible_count
            for observation in observations
        ),
        "provenance_only_count": sum(
            observation.provenance_only_count
            for observation in observations
        ),
        "not_preserved_count": sum(
            observation.not_preserved_count
            for observation in observations
        ),
        "by_category": by_category,
    }


def _merge_count_for_source(
    source_field: str,
    merge_pairs: tuple[PromptCandidateMergeObservation, ...],
    merge_kind: str,
) -> int:
    return sum(
        1
        for merge in merge_pairs
        if merge.merge_kind == merge_kind
        and source_field in merge.merged_candidate.source_fields
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
    return estimate_conservative_tokens(
        value
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
