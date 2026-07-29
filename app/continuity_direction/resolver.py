import hashlib
import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from app.continuity_direction.models import (
    ContinuityDecisionTrace,
    ContinuityDirection,
    ContinuityDirectionTrace,
)
from app.domain import EffectiveVisualBrief


class ContinuityDirector:
    def resolve(
        self,
        effective_brief: EffectiveVisualBrief
    ) -> ContinuityDirection:
        brief = effective_brief
        decisions: list[ContinuityDecisionTrace] = []
        fields = {
            "visual_continuity": self._decide(
                decisions,
                "visual_continuity",
                (
                    _field(
                        "visual_continuity",
                        brief.visual_continuity
                    ),
                    _field(
                        "continuity_relationship",
                        brief.continuity_relationship
                    ),
                    _field(
                        "visual_bible_coherence",
                        brief.visual_bible_coherence
                    ),
                ),
                "Preserve the resolved continuity relationship with the visual identity."
            ),
            "inter_scene_coherence": self._decide(
                decisions,
                "inter_scene_coherence",
                (
                    _field(
                        "continuity_relationship",
                        brief.continuity_relationship
                    ),
                    _field(
                        "narrative_coherence",
                        brief.narrative_coherence
                    ),
                    _field(
                        "intention_coherence",
                        brief.intention_coherence
                    ),
                ),
                "Keep scene-to-scene coherence tied to resolved narrative and intention."
            ),
            "identity_persistence": self._decide(
                decisions,
                "identity_persistence",
                (
                    _field(
                        "visual_bible_coherence",
                        brief.visual_bible_coherence
                    ),
                    _field(
                        "color.visual_identity_relationship",
                        _nested(
                            brief.color,
                            "visual_identity_relationship"
                        )
                    ),
                    _field(
                        "visual_strategy.world_style",
                        _nested(
                            brief.visual_strategy,
                            "world_style"
                        )
                    ),
                ),
                "Preserve visual identity persistence from already resolved identity cues."
            ),
            "character_consistency": self._decide(
                decisions,
                "character_consistency",
                (
                    _field(
                        "primary_subject",
                        brief.primary_subject
                    ),
                    _field(
                        "secondary_subject",
                        brief.secondary_subject
                    ),
                    _field(
                        "staging.human_presence",
                        _nested(
                            brief.staging,
                            "human_presence"
                        )
                    ),
                ),
                "Use only resolved subject and presence cues as character consistency."
            ),
            "wardrobe_consistency": self._decide(
                decisions,
                "wardrobe_consistency",
                (
                    _field(
                        "staging.human_presence",
                        _nested(
                            brief.staging,
                            "human_presence"
                        )
                    ),
                    _field(
                        "visual_bible_coherence",
                        brief.visual_bible_coherence
                    ),
                    _field(
                        "continuity_relationship",
                        brief.continuity_relationship
                    ),
                ),
                "Represent wardrobe consistency only when resolved human and continuity cues exist."
            ),
            "lighting_consistency": self._decide(
                decisions,
                "lighting_consistency",
                (
                    _field(
                        "lighting.motivation",
                        _nested(
                            brief.lighting,
                            "motivation"
                        )
                    ),
                    _field(
                        "lighting.atmosphere",
                        _nested(
                            brief.lighting,
                            "atmosphere"
                        )
                    ),
                    _field(
                        "lighting.visibility",
                        _nested(
                            brief.lighting,
                            "visibility"
                        )
                    ),
                ),
                "Preserve lighting continuity from resolved motivation, atmosphere and visibility."
            ),
            "chromatic_consistency": self._decide(
                decisions,
                "chromatic_consistency",
                (
                    _field(
                        "color.harmony",
                        _nested(
                            brief.color,
                            "harmony"
                        )
                    ),
                    _field(
                        "color.visual_identity_relationship",
                        _nested(
                            brief.color,
                            "visual_identity_relationship"
                        )
                    ),
                    _field(
                        "color.emotional_evolution",
                        _nested(
                            brief.color,
                            "emotional_evolution"
                        )
                    ),
                ),
                "Use resolved color harmony, identity and evolution as chromatic consistency."
            ),
            "compositional_consistency": self._decide(
                decisions,
                "compositional_consistency",
                (
                    _field(
                        "composition.visual_hierarchy",
                        _nested(
                            brief.composition,
                            "visual_hierarchy"
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
                        "composition.figure_ground_relationship",
                        _nested(
                            brief.composition,
                            "figure_ground_relationship"
                        )
                    ),
                ),
                "Keep compositional continuity tied to resolved hierarchy, balance and separation."
            ),
            "movement_consistency": self._decide(
                decisions,
                "movement_consistency",
                (
                    _field(
                        "motion.rhythm",
                        _nested(
                            brief.motion,
                            "rhythm"
                        )
                    ),
                    _field(
                        "motion.stability",
                        _nested(
                            brief.motion,
                            "stability"
                        )
                    ),
                    _field(
                        "motion.progression_or_suspension",
                        _nested(
                            brief.motion,
                            "progression_or_suspension"
                        )
                    ),
                ),
                "Preserve movement continuity from resolved rhythm, stability and progression."
            ),
            "spatial_continuity": self._decide(
                decisions,
                "spatial_continuity",
                (
                    _field(
                        "staging.environment",
                        _nested(
                            brief.staging,
                            "environment"
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
                        "continuity_relationship",
                        brief.continuity_relationship
                    ),
                ),
                "Use resolved environment, spatial relation and continuity as spatial continuity."
            ),
            "temporal_continuity": self._decide(
                decisions,
                "temporal_continuity",
                (
                    _field(
                        "motion.progression_or_suspension",
                        _nested(
                            brief.motion,
                            "progression_or_suspension"
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
                "Preserve temporal continuity from resolved progression and continuity cues."
            ),
            "visual_narrative_continuity": self._decide(
                decisions,
                "visual_narrative_continuity",
                (
                    _field(
                        "narrative_coherence",
                        brief.narrative_coherence
                    ),
                    _field(
                        "visual_reading",
                        brief.visual_reading
                    ),
                    _field(
                        "continuity_relationship",
                        brief.continuity_relationship
                    ),
                ),
                "Keep visual narrative continuity aligned with resolved reading and narrative coherence."
            ),
            "stylistic_stability": self._decide(
                decisions,
                "stylistic_stability",
                (
                    _field(
                        "visual_strategy.world_style",
                        _nested(
                            brief.visual_strategy,
                            "world_style"
                        )
                    ),
                    _field(
                        "visual_strategy.realism_level",
                        _nested(
                            brief.visual_strategy,
                            "realism_level"
                        )
                    ),
                    _field(
                        "visual_bible_coherence",
                        brief.visual_bible_coherence
                    ),
                ),
                "Preserve stylistic stability from resolved style, realism and bible coherence."
            ),
            "global_coherence": self._decide(
                decisions,
                "global_coherence",
                (
                    _field(
                        "visual_bible_coherence",
                        brief.visual_bible_coherence
                    ),
                    _field(
                        "narrative_coherence",
                        brief.narrative_coherence
                    ),
                    _field(
                        "intention_coherence",
                        brief.intention_coherence
                    ),
                ),
                "Represent global visual coherence from already resolved coherence fields."
            ),
            "key_element_preservation": self._decide(
                decisions,
                "key_element_preservation",
                (
                    _field(
                        "symbolic_weight",
                        brief.symbolic_weight
                    ),
                    _field(
                        "attention_focus",
                        brief.attention_focus
                    ),
                    _field(
                        "staging.significant_objects",
                        _nested(
                            brief.staging,
                            "significant_objects"
                        )
                    ),
                ),
                "Preserve key elements only from resolved symbolic, attentional and object cues."
            ),
            "visual_transition": self._decide(
                decisions,
                "visual_transition",
                (
                    _field(
                        "continuity_relationship",
                        brief.continuity_relationship
                    ),
                    _field(
                        "color.emotional_evolution",
                        _nested(
                            brief.color,
                            "emotional_evolution"
                        )
                    ),
                    _field(
                        "motion.progression_or_suspension",
                        _nested(
                            brief.motion,
                            "progression_or_suspension"
                        )
                    ),
                ),
                "Use resolved continuity, chromatic evolution and motion progression as visual transition."
            ),
        }
        trace = ContinuityDirectionTrace(
            source_effective_brief_fingerprint=effective_brief.fingerprint,
            decisions=tuple(
                decisions
            ),
        )
        direction = ContinuityDirection(
            **fields,
            trace=trace,
        )
        return ContinuityDirection(
            **fields,
            trace=trace,
            fingerprint=self._fingerprint(
                direction
            ),
        )

    def _decide(
        self,
        decisions: list[ContinuityDecisionTrace],
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
            ContinuityDecisionTrace(
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
        direction: ContinuityDirection
    ) -> str:
        canonical = {
            "ContinuityDirection": _canonical_mapping(
                ContinuityDirection(
                    visual_continuity=direction.visual_continuity,
                    inter_scene_coherence=direction.inter_scene_coherence,
                    identity_persistence=direction.identity_persistence,
                    character_consistency=direction.character_consistency,
                    wardrobe_consistency=direction.wardrobe_consistency,
                    lighting_consistency=direction.lighting_consistency,
                    chromatic_consistency=direction.chromatic_consistency,
                    compositional_consistency=direction.compositional_consistency,
                    movement_consistency=direction.movement_consistency,
                    spatial_continuity=direction.spatial_continuity,
                    temporal_continuity=direction.temporal_continuity,
                    visual_narrative_continuity=direction.visual_narrative_continuity,
                    stylistic_stability=direction.stylistic_stability,
                    global_coherence=direction.global_coherence,
                    key_element_preservation=direction.key_element_preservation,
                    visual_transition=direction.visual_transition,
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
    if isinstance(
        value,
        (
            tuple,
            list,
        )
    ):
        return " | ".join(
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
