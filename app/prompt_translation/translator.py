import hashlib
import json
import re
from dataclasses import asdict, fields, is_dataclass
from enum import Enum
from typing import Any

from app.cinematic_direction import CinematicDirectionSet
from app.prompt_translation.models import (
    BackendPrompt,
    BackendPromptInstruction,
    BackendPromptTrace,
    BackendPromptTraceItem,
)
from app.domain import EffectiveVisualBrief, VisualSynthesisResult


FIELD_CATEGORIES = {
    "visible_content": "content",
    "visible_subject": "content",
    "visible_action": "content",
    "visible_environment": "content",
    "time_context": "context",
    "key_objects": "content",
    "spatial_relationships": "staging",
    "continuity_links": "continuity",
    "abstract_source": "source",
    "filmable_interpretation": "content",
    "visual_constraints": "constraints",
    "felt_experience": "experience",
    "narrative_composition": "composition",
    "visual_priority": "priority",
    "primary_subject": "content",
    "secondary_subject": "content",
    "attention_focus": "attention",
    "dominant_visual_intention": "intention",
    "visual_reading": "reading",
    "scene_rhythm": "rhythm",
    "symbolic_weight": "symbolic",
    "visual_continuity": "continuity",
    "visual_bible_coherence": "coherence",
    "narrative_coherence": "coherence",
    "intention_coherence": "coherence",
    "visual_strategy": "strategy",
    "staging": "staging",
    "photography": "photography",
    "composition": "composition",
    "lighting": "lighting",
    "color": "color",
    "motion": "motion",
    "continuity_relationship": "continuity",
}


class PromptTranslator:
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
        instructions: list[BackendPromptInstruction] = []
        trace_items: list[BackendPromptTraceItem] = []

        self._collect_effective_brief_instructions(
            instructions,
            trace_items,
            effective_brief,
            source_contract,
        )
        if cinematic_direction_set is not None:
            self._collect_cinematic_instructions(
                instructions,
                trace_items,
                cinematic_direction_set
            )

        trace = BackendPromptTrace(
            source_effective_brief_fingerprint=effective_brief.fingerprint,
            items=tuple(
                trace_items
            ),
        )
        prompt = BackendPrompt(
            instructions=tuple(
                instructions
            ),
            trace=trace,
        )
        return BackendPrompt(
            instructions=prompt.instructions,
            trace=prompt.trace,
            fingerprint=self._fingerprint(
                prompt
            ),
        )

    def _collect_effective_brief_instructions(
        self,
        instructions: list[BackendPromptInstruction],
        trace_items: list[BackendPromptTraceItem],
        effective_brief: EffectiveVisualBrief,
        source_contract: str,
    ) -> None:
        for field in fields(
            effective_brief
        ):
            if field.name in NON_OPERATIONAL_EFFECTIVE_FIELDS:
                continue
            source_field = field.name
            value = getattr(
                effective_brief,
                source_field
            )
            source_prefix = (
                f"{source_contract}.brief"
                if source_contract == "VisualSynthesisResult"
                else source_contract
            )
            self._collect_instructions(
                instructions,
                trace_items,
                source_field,
                value,
                source_prefix=source_prefix,
            )

    def _collect_instructions(
        self,
        instructions: list[BackendPromptInstruction],
        trace_items: list[BackendPromptTraceItem],
        source_field: str,
        value: Any,
        source_prefix: str = "VisualBrief",
    ) -> None:
        if _field_name(
            source_field
        ) in NON_OPERATIONAL_FIELDS:
            return
        if value is None:
            return
        if is_dataclass(
            value
        ):
            for nested_field in fields(
                value
            ):
                nested_source = f"{source_field}.{nested_field.name}"
                nested_value = getattr(
                    value,
                    nested_field.name
                )
                self._collect_instructions(
                    instructions,
                    trace_items,
                    nested_source,
                    nested_value,
                    source_prefix=source_prefix,
                )
            return
        self._add_instruction(
            instructions,
            trace_items,
            source_field,
            value,
            source_prefix=source_prefix,
        )

    def _add_instruction(
        self,
        instructions: list[BackendPromptInstruction],
        trace_items: list[BackendPromptTraceItem],
        source_field: str,
        value: Any,
        source_prefix: str = "VisualBrief",
    ) -> None:
        normalized, transformation = _normalize_value(
            value
        )
        if not normalized:
            return
        instruction_id = _instruction_id(
            source_field
        )
        if source_prefix:
            source_path = f"{source_prefix}.{source_field}"
        else:
            source_path = source_field
        instructions.append(
            BackendPromptInstruction(
                id=instruction_id,
                category=_category(
                    source_field
                ),
                source_field=source_path,
                value=normalized,
            )
        )
        trace_items.append(
            BackendPromptTraceItem(
                instruction_id=instruction_id,
                source_fields=(
                    source_path,
                ),
                transformation=transformation,
            )
        )

    def _collect_cinematic_instructions(
        self,
        instructions: list[BackendPromptInstruction],
        trace_items: list[BackendPromptTraceItem],
        cinematic_direction_set: CinematicDirectionSet,
    ) -> None:
        for component in (
            "photography",
            "lighting",
            "composition",
            "color",
            "movement",
            "continuity",
        ):
            direction = getattr(
                cinematic_direction_set,
                component
            )
            if direction is None:
                continue
            for field in fields(
                direction
            ):
                if field.name in (
                    "trace",
                    "fingerprint",
                ):
                    continue
                source_field = f"{component}.{field.name}"
                value = getattr(
                    direction,
                    field.name
                )
                self._add_cinematic_instruction(
                    instructions,
                    trace_items,
                    cinematic_direction_set,
                    component,
                    source_field,
                    value
                )

    def _add_cinematic_instruction(
        self,
        instructions: list[BackendPromptInstruction],
        trace_items: list[BackendPromptTraceItem],
        cinematic_direction_set: CinematicDirectionSet,
        component: str,
        source_field: str,
        value: Any
    ) -> None:
        normalized, _ = _normalize_value(
            value
        )
        if not normalized:
            return
        instruction_id = _instruction_id(
            f"cinematic.{source_field}"
        )
        instructions.append(
            BackendPromptInstruction(
                id=instruction_id,
                category=f"cinematic_{component}",
                source_field=f"CinematicDirectionSet.{source_field}",
                value=normalized,
            )
        )
        trace_items.append(
            BackendPromptTraceItem(
                instruction_id=instruction_id,
                source_fields=(
                    f"CinematicDirectionSet.{source_field}",
                    f"CinematicDirectionSet.{component}.fingerprint",
                    "CinematicDirectionSet.fingerprint",
                ),
                transformation="translate_cinematic_direction_field",
            )
        )

    def _fingerprint(
        self,
        prompt: BackendPrompt
    ) -> str:
        canonical = {
            "instructions": _canonical_mapping(
                prompt.instructions
            ),
            "trace": _canonical_mapping(
                prompt.trace
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
) -> tuple[str, str]:
    if isinstance(
        value,
        Enum
    ):
        return _clean(
            value.value
        ), "normalize_enum"
    if isinstance(
        value,
        (
            tuple,
            list,
        )
    ):
        normalized = " | ".join(
            _dedupe(
                tuple(
                    _clean(
                        item
                    )
                    for item in value
                    if _is_scalar(
                        item
                    )
                    and _clean(
                        item
                    )
                )
            )
        )
        return normalized, "normalize_sequence"
    if not _is_scalar(
        value
    ):
        return "", "skip_non_scalar"
    return _clean(
        value
    ), "normalize_text"


def _category(
    source_field: str
) -> str:
    root = source_field.split(
        ".",
        1
    )[0]
    return FIELD_CATEGORIES.get(
        root,
        "general"
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


def _dedupe(
    values: tuple[str, ...]
) -> tuple[str, ...]:
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(
                value
            )
            result.append(
                value
            )
    return tuple(
        result
    )


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


NON_OPERATIONAL_FIELDS = {
    "conflicts",
    "evidences",
    "findings",
    "fingerprint",
    "trace",
    "visual_truth_status",
}

NON_OPERATIONAL_EFFECTIVE_FIELDS = {
    "conflicts",
    "findings",
    "evidences",
    "trace",
    "fingerprint",
}


def _field_name(
    source_field: str
) -> str:
    return source_field.rsplit(
        ".",
        1
    )[-1]
