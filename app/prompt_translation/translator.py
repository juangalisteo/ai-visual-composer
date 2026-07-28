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
from app.visual_direction import EffectiveVisualBrief


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
    def translate(
        self,
        effective_visual_brief: EffectiveVisualBrief,
        cinematic_direction_set: CinematicDirectionSet | None = None,
    ) -> BackendPrompt:
        visual_brief = effective_visual_brief.visual_brief
        instructions: list[BackendPromptInstruction] = []
        trace_items: list[BackendPromptTraceItem] = []

        for field in fields(
            visual_brief
        ):
            source_field = field.name
            value = getattr(
                visual_brief,
                source_field
            )
            self._collect_instructions(
                instructions,
                trace_items,
                source_field,
                value
            )
        if cinematic_direction_set is not None:
            self._collect_cinematic_instructions(
                instructions,
                trace_items,
                cinematic_direction_set
            )

        trace = BackendPromptTrace(
            source_visual_brief_fingerprint=effective_visual_brief.fingerprint,
            items=tuple(
                trace_items
            ),
        )
        prompt = BackendPrompt(
            instructions=tuple(
                instructions
            ),
            trace=trace,
            source_id=effective_visual_brief.source_id,
            source_version=effective_visual_brief.source_version,
        )
        return BackendPrompt(
            instructions=prompt.instructions,
            trace=prompt.trace,
            source_id=prompt.source_id,
            source_version=prompt.source_version,
            fingerprint=self._fingerprint(
                prompt
            ),
        )

    def _collect_instructions(
        self,
        instructions: list[BackendPromptInstruction],
        trace_items: list[BackendPromptTraceItem],
        source_field: str,
        value: Any
    ) -> None:
        if source_field in NON_OPERATIONAL_FIELDS:
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
                self._add_instruction(
                    instructions,
                    trace_items,
                    nested_source,
                    nested_value
                )
            return
        self._add_instruction(
            instructions,
            trace_items,
            source_field,
            value
        )

    def _add_instruction(
        self,
        instructions: list[BackendPromptInstruction],
        trace_items: list[BackendPromptTraceItem],
        source_field: str,
        value: Any
    ) -> None:
        normalized, transformation = _normalize_value(
            value
        )
        if not normalized:
            return
        instruction_id = _instruction_id(
            source_field
        )
        instructions.append(
            BackendPromptInstruction(
                id=instruction_id,
                category=_category(
                    source_field
                ),
                source_field=f"VisualBrief.{source_field}",
                value=normalized,
            )
        )
        trace_items.append(
            BackendPromptTraceItem(
                instruction_id=instruction_id,
                source_fields=(
                    f"VisualBrief.{source_field}",
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
                    "source_id",
                    "source_version",
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
            "source_id": prompt.source_id,
            "source_version": prompt.source_version,
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
                    if _clean(
                        item
                    )
                )
            )
        )
        return normalized, "normalize_sequence"
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
    "visual_truth_status",
}
