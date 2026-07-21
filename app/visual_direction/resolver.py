import hashlib
import json
import re
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from app.domain import Intention, NarrativeReading, VisualBible, VisualBrief
from app.visual_direction.models import (
    EffectiveVisualBrief,
    VisualBriefFieldOrigin,
    VisualBriefTrace,
    VisualDirectionConflict,
    VisualDirectionInput,
)


class VisualDirector2:
    def resolve(
        self,
        context: VisualDirectionInput
    ) -> EffectiveVisualBrief:
        visual_bible = context.visual_bible
        narrative_reading = context.narrative_reading
        intention = context.intention

        fields: dict[str, str] = {}
        origins: list[VisualBriefFieldOrigin] = []
        conflicts = self._conflicts(
            visual_bible,
            narrative_reading,
            intention
        )

        self._set(
            fields,
            origins,
            "visible_content",
            self._visible_content(
                narrative_reading
            ),
            "narrative_reading",
            "event/entities"
        )
        self._set(
            fields,
            origins,
            "felt_experience",
            self._felt_experience(
                intention
            ),
            "intention",
            "emotional/transformative"
        )
        self._set(
            fields,
            origins,
            "narrative_composition",
            self._narrative_composition(
                narrative_reading,
                intention
            ),
            "narrative_reading",
            "function/change"
        )
        self._set(
            fields,
            origins,
            "visual_priority",
            self._visual_priority(
                visual_bible,
                intention
            ),
            "intention",
            "attentional.priority"
        )
        self._set(
            fields,
            origins,
            "primary_subject",
            self._primary_subject(
                narrative_reading
            ),
            "narrative_reading",
            "event.subject"
        )
        self._set(
            fields,
            origins,
            "secondary_subject",
            self._secondary_subject(
                narrative_reading
            ),
            "narrative_reading",
            "event.object"
        )
        self._set(
            fields,
            origins,
            "attention_focus",
            self._attention_focus(
                narrative_reading,
                intention
            ),
            "intention",
            "attentional.focus"
        )
        self._set(
            fields,
            origins,
            "dominant_visual_intention",
            self._dominant_visual_intention(
                intention
            ),
            "intention",
            "narrative/emotional"
        )
        self._set(
            fields,
            origins,
            "visual_reading",
            self._visual_reading(
                narrative_reading,
                intention
            ),
            "intention",
            "symbolic"
        )
        self._set(
            fields,
            origins,
            "scene_rhythm",
            self._scene_rhythm(
                visual_bible,
                intention
            ),
            "visual_bible",
            "cinematic_language.rhythm"
        )
        self._set(
            fields,
            origins,
            "symbolic_weight",
            self._symbolic_weight(
                narrative_reading,
                intention
            ),
            "intention",
            "symbolic.meaning"
        )
        self._set(
            fields,
            origins,
            "visual_continuity",
            self._visual_continuity(
                visual_bible,
                narrative_reading
            ),
            "narrative_reading",
            "continuity"
        )
        self._set(
            fields,
            origins,
            "visual_bible_coherence",
            self._visual_bible_coherence(
                visual_bible
            ),
            "visual_bible",
            "identity/quality"
        )
        self._set(
            fields,
            origins,
            "narrative_coherence",
            self._narrative_coherence(
                narrative_reading
            ),
            "narrative_reading",
            "facts/event"
        )
        self._set(
            fields,
            origins,
            "intention_coherence",
            self._intention_coherence(
                intention
            ),
            "intention",
            "all"
        )

        visual_brief = VisualBrief(
            **fields
        )
        trace = VisualBriefTrace(
            field_origins=tuple(
                origins
            ),
            reinforced_fields=self._reinforced_fields(
                origins
            ),
            specialized_fields=self._specialized_fields(
                origins
            ),
        )
        fingerprint = self._fingerprint(
            visual_brief,
            tuple(
                conflicts
            )
        )
        return EffectiveVisualBrief(
            visual_brief=visual_brief,
            trace=trace,
            conflicts=tuple(
                conflicts
            ),
            fingerprint=fingerprint,
            source_id=context.source_id,
            source_version=context.source_version,
        )

    def _conflicts(
        self,
        visual_bible: VisualBible,
        narrative_reading: NarrativeReading,
        intention: Intention
    ) -> tuple[VisualDirectionConflict, ...]:
        conflicts: list[VisualDirectionConflict] = []

        symbolic = intention.symbolic
        if symbolic is not None:
            forbidden = set(
                visual_bible.symbolic_system.forbidden_symbols
            )
            overlap = forbidden & set(
                symbolic.allowed_readings
            )
            for item in sorted(
                overlap
            ):
                conflicts.append(
                    VisualDirectionConflict(
                        source_layers=(
                            "visual_bible",
                            "intention",
                        ),
                        conflict_type="forbidden_symbolic_reading",
                        description=f"Intention allows a reading forbidden by Visual Bible: {item}",
                        field="visual_reading",
                    )
                )

        if intention.attentional is not None and not self._visible_content(
            narrative_reading
        ):
            conflicts.append(
                VisualDirectionConflict(
                    source_layers=(
                        "narrative_reading",
                        "intention",
                    ),
                    conflict_type="missing_narrative_anchor",
                    description="Attentional intention has no visible narrative anchor.",
                    field="attention_focus",
                )
            )

        return tuple(
            conflicts
        )

    def _visible_content(
        self,
        narrative_reading: NarrativeReading
    ) -> str:
        event = narrative_reading.event
        parts = (
            event.subject,
            event.action,
            event.object,
        )
        sentence = _join_text(
            parts
        )
        if sentence:
            return sentence
        return _join_text(
            narrative_reading.entities.characters
            + narrative_reading.entities.objects
            + narrative_reading.entities.places
        )

    def _felt_experience(
        self,
        intention: Intention
    ) -> str:
        if intention.emotional is not None:
            return _join_text(
                (
                    intention.emotional.desired_effect,
                    intention.emotional.emotional_quality,
                )
            )
        if intention.transformative is not None:
            return intention.transformative.shift
        return ""

    def _narrative_composition(
        self,
        narrative_reading: NarrativeReading,
        intention: Intention
    ) -> str:
        return _join_text(
            (
                narrative_reading.function.primary,
                narrative_reading.change.change_type,
                intention.narrative.purpose if intention.narrative else "",
            )
        )

    def _visual_priority(
        self,
        visual_bible: VisualBible,
        intention: Intention
    ) -> str:
        if intention.attentional is not None:
            return _first_text(
                intention.attentional.priority,
                intention.attentional.focus
            )
        return visual_bible.composition.hierarchy

    def _primary_subject(
        self,
        narrative_reading: NarrativeReading
    ) -> str:
        return _first_text(
            narrative_reading.event.subject,
            _first(
                narrative_reading.entities.characters
            ),
            _first(
                narrative_reading.entities.objects
            )
        )

    def _secondary_subject(
        self,
        narrative_reading: NarrativeReading
    ) -> str:
        return _first_text(
            narrative_reading.event.object,
            _first(
                narrative_reading.entities.objects
            ),
            _first(
                narrative_reading.entities.places
            )
        )

    def _attention_focus(
        self,
        narrative_reading: NarrativeReading,
        intention: Intention
    ) -> str:
        if intention.attentional is not None:
            return _first_text(
                intention.attentional.focus,
                intention.attentional.priority
            )
        return _first_text(
            narrative_reading.event.object,
            narrative_reading.event.subject
        )

    def _dominant_visual_intention(
        self,
        intention: Intention
    ) -> str:
        if intention.narrative is not None:
            return _first_text(
                intention.narrative.purpose,
                intention.narrative.function
            )
        if intention.communicative is not None:
            return intention.communicative.understanding
        return ""

    def _visual_reading(
        self,
        narrative_reading: NarrativeReading,
        intention: Intention
    ) -> str:
        if intention.symbolic is not None:
            return _join_text(
                (
                    intention.symbolic.meaning,
                    _join_text(
                        intention.symbolic.allowed_readings
                    ),
                    intention.symbolic.ambiguity,
                )
            )
        return _join_text(
            narrative_reading.concepts.explicit
            + narrative_reading.concepts.contextual
        )

    def _scene_rhythm(
        self,
        visual_bible: VisualBible,
        intention: Intention
    ) -> str:
        return _join_text(
            (
                visual_bible.cinematic_language.rhythm,
                intention.emotional.intensity if intention.emotional else "",
            )
        )

    def _symbolic_weight(
        self,
        narrative_reading: NarrativeReading,
        intention: Intention
    ) -> str:
        if intention.symbolic is not None:
            return _first_text(
                intention.symbolic.meaning,
                _join_text(
                    intention.symbolic.allowed_readings
                )
            )
        return _join_text(
            narrative_reading.explicit_symbols.symbols
        )

    def _visual_continuity(
        self,
        visual_bible: VisualBible,
        narrative_reading: NarrativeReading
    ) -> str:
        return _join_text(
            (
                visual_bible.continuity.atmosphere,
                visual_bible.continuity.symbols,
                _join_text(
                    narrative_reading.continuity.prepares
                    + narrative_reading.continuity.continues
                ),
            )
        )

    def _visual_bible_coherence(
        self,
        visual_bible: VisualBible
    ) -> str:
        return _join_text(
            (
                visual_bible.identity.visual_statement,
                visual_bible.quality.coherence,
                visual_bible.quality.belonging,
            )
        )

    def _narrative_coherence(
        self,
        narrative_reading: NarrativeReading
    ) -> str:
        return _join_text(
            (
                _join_text(
                    narrative_reading.facts.stated
                ),
                self._visible_content(
                    narrative_reading
                ),
            )
        )

    def _intention_coherence(
        self,
        intention: Intention
    ) -> str:
        return _join_text(
            (
                intention.communicative.understanding if intention.communicative else "",
                intention.transformative.shift if intention.transformative else "",
                _join_text(
                    intention.negative.avoid_interpretations
                    if intention.negative else ()
                ),
            )
        )

    def _set(
        self,
        fields: dict[str, str],
        origins: list[VisualBriefFieldOrigin],
        field: str,
        value: str,
        source_layer: str,
        source_path: str
    ) -> None:
        fields[field] = value
        if value:
            origins.append(
                VisualBriefFieldOrigin(
                    field=field,
                    source_layer=source_layer,
                    source_path=source_path,
                    action="set"
                )
            )

    def _reinforced_fields(
        self,
        origins: list[VisualBriefFieldOrigin]
    ) -> tuple[str, ...]:
        by_field: dict[str, set[str]] = {}
        for origin in origins:
            by_field.setdefault(
                origin.field,
                set()
            ).add(
                origin.source_layer
            )
        return tuple(
            sorted(
                field
                for field, layers in by_field.items()
                if len(
                    layers
                ) > 1
            )
        )

    def _specialized_fields(
        self,
        origins: list[VisualBriefFieldOrigin]
    ) -> tuple[str, ...]:
        return tuple(
            sorted(
                origin.field
                for origin in origins
                if origin.source_layer == "intention"
            )
        )

    def _fingerprint(
        self,
        visual_brief: VisualBrief,
        conflicts: tuple[VisualDirectionConflict, ...]
    ) -> str:
        canonical = {
            "visual_brief": _canonical_mapping(
                visual_brief
            ),
            "conflicts": _canonical_mapping(
                conflicts
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


def _join_text(
    values: tuple[str, ...]
) -> str:
    return " | ".join(
        _dedupe(
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


def _first_text(
    *values: str
) -> str:
    for value in values:
        cleaned = _clean(
            value
        )
        if cleaned:
            return cleaned
    return ""


def _first(
    values: tuple[str, ...]
) -> str:
    if values:
        return values[0]
    return ""


def _clean(
    value: str
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
