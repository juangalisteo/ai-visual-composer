import hashlib
import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from app.composition_direction.models import (
    CompositionDecisionTrace,
    CompositionDirection,
    CompositionDirectionTrace,
)
from app.domain import EffectiveVisualBrief


class CompositionDirector:
    def resolve(
        self,
        effective_brief: EffectiveVisualBrief
    ) -> CompositionDirection:
        brief = effective_brief
        decisions: list[CompositionDecisionTrace] = []
        fields = {
            "dominant_composition": self._decide(
                decisions,
                "dominant_composition",
                (
                    _field(
                        "composition.visual_hierarchy",
                        _nested(
                            brief.composition,
                            "visual_hierarchy"
                        )
                    ),
                    _field(
                        "narrative_composition",
                        brief.narrative_composition
                    ),
                    _field(
                        "visual_priority",
                        brief.visual_priority
                    ),
                ),
                "Preserve the strongest resolved composition cue."
            ),
            "visual_balance": self._decide(
                decisions,
                "visual_balance",
                (
                    _field(
                        "composition.balance",
                        _nested(
                            brief.composition,
                            "balance"
                        )
                    ),
                    _field(
                        "composition.figure_ground_relationship",
                        _nested(
                            brief.composition,
                            "figure_ground_relationship"
                        )
                    ),
                ),
                "Translate resolved balance and figure-ground cues into visual balance."
            ),
            "spatial_distribution": self._decide(
                decisions,
                "spatial_distribution",
                (
                    _field(
                        "staging.narrative_distribution",
                        _nested(
                            brief.staging,
                            "narrative_distribution"
                        )
                    ),
                    _field(
                        "staging.spatial_relationship",
                        _nested(
                            brief.staging,
                            "spatial_relationship"
                        )
                    ),
                    _field(
                        "composition.balance",
                        _nested(
                            brief.composition,
                            "balance"
                        )
                    ),
                ),
                "Keep spatial distribution tied to resolved staging and balance."
            ),
            "compositional_hierarchy": self._decide(
                decisions,
                "compositional_hierarchy",
                (
                    _field(
                        "composition.visual_hierarchy",
                        _nested(
                            brief.composition,
                            "visual_hierarchy"
                        )
                    ),
                    _field(
                        "primary_subject",
                        brief.primary_subject
                    ),
                    _field(
                        "secondary_subject",
                        brief.secondary_subject
                    ),
                    _field(
                        "attention_focus",
                        brief.attention_focus
                    ),
                ),
                "Preserve the resolved hierarchy of subjects and attention."
            ),
            "visual_weight": self._decide(
                decisions,
                "visual_weight",
                (
                    _field(
                        "symbolic_weight",
                        brief.symbolic_weight
                    ),
                    _field(
                        "visual_reading",
                        brief.visual_reading
                    ),
                    _field(
                        "visual_priority",
                        brief.visual_priority
                    ),
                ),
                "Translate resolved symbolic and visual priority into compositional weight."
            ),
            "compositional_rhythm": self._decide(
                decisions,
                "compositional_rhythm",
                (
                    _field(
                        "scene_rhythm",
                        brief.scene_rhythm
                    ),
                    _field(
                        "motion.rhythm",
                        _nested(
                            brief.motion,
                            "rhythm"
                        )
                    ),
                    _field(
                        "composition.reading_direction",
                        _nested(
                            brief.composition,
                            "reading_direction"
                        )
                    ),
                ),
                "Use resolved rhythm and reading direction as compositional rhythm."
            ),
            "visual_tension": self._decide(
                decisions,
                "visual_tension",
                (
                    _field(
                        "composition.spatial_tension",
                        _nested(
                            brief.composition,
                            "spatial_tension"
                        )
                    ),
                    _field(
                        "dominant_visual_intention",
                        brief.dominant_visual_intention
                    ),
                    _field(
                        "intention_coherence",
                        brief.intention_coherence
                    ),
                ),
                "Represent resolved spatial and intentional pressure without inventing action."
            ),
            "symmetry_or_asymmetry": self._decide(
                decisions,
                "symmetry_or_asymmetry",
                (
                    _field(
                        "composition.balance",
                        _nested(
                            brief.composition,
                            "balance"
                        )
                    ),
                    _field(
                        "composition.framing",
                        _nested(
                            brief.composition,
                            "framing"
                        )
                    ),
                ),
                "Infer symmetry language only from resolved balance and framing cues."
            ),
            "negative_space_usage": self._decide(
                decisions,
                "negative_space_usage",
                (
                    _field(
                        "composition.negative_space",
                        _nested(
                            brief.composition,
                            "negative_space"
                        )
                    ),
                    _field(
                        "visual_priority",
                        brief.visual_priority
                    ),
                ),
                "Preserve resolved negative space usage as a compositional device."
            ),
            "foreground_organization": self._decide(
                decisions,
                "foreground_organization",
                (
                    _field(
                        "primary_subject",
                        brief.primary_subject
                    ),
                    _field(
                        "attention_focus",
                        brief.attention_focus
                    ),
                    _field(
                        "staging.main_subject",
                        _nested(
                            brief.staging,
                            "main_subject"
                        )
                    ),
                ),
                "Organize the front plane from resolved subject and attention cues."
            ),
            "midground_organization": self._decide(
                decisions,
                "midground_organization",
                (
                    _field(
                        "staging.spatial_relationship",
                        _nested(
                            brief.staging,
                            "spatial_relationship"
                        )
                    ),
                    _field(
                        "secondary_subject",
                        brief.secondary_subject
                    ),
                    _field(
                        "staging.action_or_state",
                        _nested(
                            brief.staging,
                            "action_or_state"
                        )
                    ),
                ),
                "Preserve middle-plane relationships already resolved by staging."
            ),
            "background_organization": self._decide(
                decisions,
                "background_organization",
                (
                    _field(
                        "staging.environment",
                        _nested(
                            brief.staging,
                            "environment"
                        )
                    ),
                    _field(
                        "visual_continuity",
                        brief.visual_continuity
                    ),
                    _field(
                        "continuity_relationship",
                        brief.continuity_relationship
                    ),
                ),
                "Use resolved environment and continuity cues as background organization."
            ),
            "compositional_depth": self._decide(
                decisions,
                "compositional_depth",
                (
                    _field(
                        "composition.figure_ground_relationship",
                        _nested(
                            brief.composition,
                            "figure_ground_relationship"
                        )
                    ),
                    _field(
                        "photography.depth",
                        _nested(
                            brief.photography,
                            "depth"
                        )
                    ),
                    _field(
                        "lighting.volume",
                        _nested(
                            brief.lighting,
                            "volume"
                        )
                    ),
                ),
                "Translate existing separation, depth and volume cues into compositional depth."
            ),
            "visual_reading_direction": self._decide(
                decisions,
                "visual_reading_direction",
                (
                    _field(
                        "composition.reading_direction",
                        _nested(
                            brief.composition,
                            "reading_direction"
                        )
                    ),
                    _field(
                        "attention_focus",
                        brief.attention_focus
                    ),
                    _field(
                        "visual_reading",
                        brief.visual_reading
                    ),
                ),
                "Preserve how the resolved image should be read visually."
            ),
            "stability": self._decide(
                decisions,
                "stability",
                (
                    _field(
                        "motion.stability",
                        _nested(
                            brief.motion,
                            "stability"
                        )
                    ),
                    _field(
                        "composition.balance",
                        _nested(
                            brief.composition,
                            "balance"
                        )
                    ),
                    _field(
                        "scene_rhythm",
                        brief.scene_rhythm
                    ),
                ),
                "Represent compositional stability from resolved motion, balance and rhythm."
            ),
            "compositional_dynamism": self._decide(
                decisions,
                "compositional_dynamism",
                (
                    _field(
                        "motion.latent_energy",
                        _nested(
                            brief.motion,
                            "latent_energy"
                        )
                    ),
                    _field(
                        "motion.direction",
                        _nested(
                            brief.motion,
                            "direction"
                        )
                    ),
                    _field(
                        "composition.spatial_tension",
                        _nested(
                            brief.composition,
                            "spatial_tension"
                        )
                    ),
                    _field(
                        "scene_rhythm",
                        brief.scene_rhythm
                    ),
                ),
                "Translate resolved energy and spatial tension into compositional dynamism."
            ),
        }
        trace = CompositionDirectionTrace(
            source_effective_brief_fingerprint=effective_brief.fingerprint,
            decisions=tuple(
                decisions
            ),
        )
        direction = CompositionDirection(
            **fields,
            trace=trace,
        )
        return CompositionDirection(
            **fields,
            trace=trace,
            fingerprint=self._fingerprint(
                direction
            ),
        )

    def _decide(
        self,
        decisions: list[CompositionDecisionTrace],
        field: str,
        candidates: tuple[tuple[str, Any], ...],
        justification: str,
    ) -> str:
        values = tuple(
            (
                name,
                _clean(
                    value
                ),
            )
            for name, value in candidates
        )
        selected = tuple(
            (
                name,
                value
            )
            for name, value in values
            if value
        )
        if not selected:
            return ""

        unique_values = _dedupe(
            tuple(
                value
                for _, value in selected
            )
        )
        source_fields = tuple(
            f"EffectiveVisualBrief.{name}"
            for name, _ in selected
        )
        transformation = "select_resolved_effective_brief_field"
        if len(
            unique_values
        ) > 1:
            transformation = "select_and_combine_resolved_effective_brief_fields"
        decisions.append(
            CompositionDecisionTrace(
                field=field,
                source_fields=source_fields,
                transformation=transformation,
                justification=justification,
            )
        )
        return " | ".join(
            unique_values
        )

    def _fingerprint(
        self,
        direction: CompositionDirection
    ) -> str:
        canonical = {
            "CompositionDirection": _canonical_mapping(
                CompositionDirection(
                    dominant_composition=direction.dominant_composition,
                    visual_balance=direction.visual_balance,
                    spatial_distribution=direction.spatial_distribution,
                    compositional_hierarchy=direction.compositional_hierarchy,
                    visual_weight=direction.visual_weight,
                    compositional_rhythm=direction.compositional_rhythm,
                    visual_tension=direction.visual_tension,
                    symmetry_or_asymmetry=direction.symmetry_or_asymmetry,
                    negative_space_usage=direction.negative_space_usage,
                    foreground_organization=direction.foreground_organization,
                    midground_organization=direction.midground_organization,
                    background_organization=direction.background_organization,
                    compositional_depth=direction.compositional_depth,
                    visual_reading_direction=direction.visual_reading_direction,
                    stability=direction.stability,
                    compositional_dynamism=direction.compositional_dynamism,
                    trace=direction.trace,
                )
            )
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


def _field(
    name: str,
    value: Any
) -> tuple[str, Any]:
    return name, value


def _nested(
    item: Any,
    field: str
) -> Any:
    if item is None:
        return ""
    return getattr(
        item,
        field
    )


def _clean(
    value: Any
) -> str:
    return " ".join(
        str(
            value
            or ""
        ).split()
    )


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
