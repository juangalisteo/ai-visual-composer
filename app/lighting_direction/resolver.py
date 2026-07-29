import hashlib
import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from app.lighting_direction.models import (
    LightingDecisionTrace,
    LightingDirection,
    LightingDirectionTrace,
)
from app.domain import EffectiveVisualBrief


class LightingDirector:
    def resolve(
        self,
        effective_brief: EffectiveVisualBrief
    ) -> LightingDirection:
        brief = effective_brief
        decisions: list[LightingDecisionTrace] = []
        fields = {
            "dominant_lighting": self._decide(
                decisions,
                "dominant_lighting",
                (
                    _field(
                        "lighting.source",
                        _nested(
                            brief.lighting,
                            "source"
                        )
                    ),
                    _field(
                        "lighting.motivation",
                        _nested(
                            brief.lighting,
                            "motivation"
                        )
                    ),
                ),
                "Preserve the resolved dominant lighting motive."
            ),
            "luminous_atmosphere": self._decide(
                decisions,
                "luminous_atmosphere",
                (
                    _field(
                        "lighting.atmosphere",
                        _nested(
                            brief.lighting,
                            "atmosphere"
                        )
                    ),
                    _field(
                        "photography.photographic_atmosphere",
                        _nested(
                            brief.photography,
                            "photographic_atmosphere"
                        )
                    ),
                    _field(
                        "felt_experience",
                        brief.felt_experience
                    ),
                ),
                "Translate resolved atmosphere into lighting mood."
            ),
            "perceived_contrast": self._decide(
                decisions,
                "perceived_contrast",
                (
                    _field(
                        "lighting.contrast",
                        _nested(
                            brief.lighting,
                            "contrast"
                        )
                    ),
                    _field(
                        "visual_priority",
                        brief.visual_priority
                    ),
                ),
                "Keep contrast tied to resolved visual priority."
            ),
            "softness_or_hardness": self._decide(
                decisions,
                "softness_or_hardness",
                (
                    _field(
                        "lighting.quality",
                        _nested(
                            brief.lighting,
                            "quality"
                        )
                    ),
                    _field(
                        "lighting.hardness",
                        _nested(
                            brief.lighting,
                            "hardness"
                        )
                    ),
                ),
                "Represent light quality without physical light parameters."
            ),
            "conceptual_light_direction": self._decide(
                decisions,
                "conceptual_light_direction",
                (
                    _field(
                        "lighting.direction",
                        _nested(
                            brief.lighting,
                            "direction"
                        )
                    ),
                    _field(
                        "attention_focus",
                        brief.attention_focus
                    ),
                ),
                "Use resolved direction and attention as conceptual light orientation."
            ),
            "shadow_distribution": self._decide(
                decisions,
                "shadow_distribution",
                (
                    _field(
                        "lighting.visibility",
                        _nested(
                            brief.lighting,
                            "visibility"
                        )
                    ),
                    _field(
                        "composition.negative_space",
                        _nested(
                            brief.composition,
                            "negative_space"
                        )
                    ),
                ),
                "Translate visibility and spatial silence into shadow distribution."
            ),
            "subject_background_separation": self._decide(
                decisions,
                "subject_background_separation",
                (
                    _field(
                        "composition.figure_ground_relationship",
                        _nested(
                            brief.composition,
                            "figure_ground_relationship"
                        )
                    ),
                    _field(
                        "staging.spatial_relationship",
                        _nested(
                            brief.staging,
                            "spatial_relationship"
                        )
                    ),
                ),
                "Preserve existing subject-background separation cues."
            ),
            "perceived_volume": self._decide(
                decisions,
                "perceived_volume",
                (
                    _field(
                        "lighting.volume",
                        _nested(
                            brief.lighting,
                            "volume"
                        )
                    ),
                    _field(
                        "photography.light_volume_treatment",
                        _nested(
                            brief.photography,
                            "light_volume_treatment"
                        )
                    ),
                    _field(
                        "photography.depth",
                        _nested(
                            brief.photography,
                            "depth"
                        )
                    ),
                ),
                "Translate resolved depth and light volume cues into perceived volume."
            ),
            "dramatism": self._decide(
                decisions,
                "dramatism",
                (
                    _field(
                        "lighting.contrast",
                        _nested(
                            brief.lighting,
                            "contrast"
                        )
                    ),
                    _field(
                        "dominant_visual_intention",
                        brief.dominant_visual_intention
                    ),
                    _field(
                        "symbolic_weight",
                        brief.symbolic_weight
                    ),
                ),
                "Use existing contrast, intention and symbolic weight as dramatic lighting cue."
            ),
            "naturalness": self._decide(
                decisions,
                "naturalness",
                (
                    _field(
                        "lighting.motivation",
                        _nested(
                            brief.lighting,
                            "motivation"
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
                "Keep lighting naturalness aligned with resolved realism cues."
            ),
            "mystery": self._decide(
                decisions,
                "mystery",
                (
                    _field(
                        "visual_reading",
                        brief.visual_reading
                    ),
                    _field(
                        "intention_coherence",
                        brief.intention_coherence
                    ),
                ),
                "Represent unresolved visual meaning without inventing narrative content."
            ),
            "warmth": self._decide(
                decisions,
                "warmth",
                (
                    _field(
                        "color.temperature",
                        _nested(
                            brief.color,
                            "temperature"
                        )
                    ),
                    _field(
                        "color.harmony",
                        _nested(
                            brief.color,
                            "harmony"
                        )
                    ),
                ),
                "Carry resolved color warmth into lighting language."
            ),
            "coolness": self._decide(
                decisions,
                "coolness",
                (
                    _field(
                        "color.chromatic_contrast",
                        _nested(
                            brief.color,
                            "chromatic_contrast"
                        )
                    ),
                    _field(
                        "color.rupture",
                        _nested(
                            brief.color,
                            "rupture"
                        )
                    ),
                ),
                "Carry resolved chromatic contrast into lighting temperature feeling."
            ),
            "narrative_clarity": self._decide(
                decisions,
                "narrative_clarity",
                (
                    _field(
                        "lighting.visibility",
                        _nested(
                            brief.lighting,
                            "visibility"
                        )
                    ),
                    _field(
                        "narrative_coherence",
                        brief.narrative_coherence
                    ),
                    _field(
                        "visual_priority",
                        brief.visual_priority
                    ),
                ),
                "Tie legibility of light to narrative coherence and visual priority."
            ),
            "luminous_hierarchy": self._decide(
                decisions,
                "luminous_hierarchy",
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
                        "attention_focus",
                        brief.attention_focus
                    ),
                ),
                "Translate resolved subject hierarchy into luminous hierarchy."
            ),
            "spatial_feeling": self._decide(
                decisions,
                "spatial_feeling",
                (
                    _field(
                        "staging.environment",
                        _nested(
                            brief.staging,
                            "environment"
                        )
                    ),
                    _field(
                        "composition.figure_ground_relationship",
                        _nested(
                            brief.composition,
                            "figure_ground_relationship"
                        )
                    ),
                    _field(
                        "visual_continuity",
                        brief.visual_continuity
                    ),
                ),
                "Use existing environment, separation and continuity as spatial light feeling."
            ),
        }
        trace = LightingDirectionTrace(
            source_effective_brief_fingerprint=effective_brief.fingerprint,
            decisions=tuple(
                decisions
            ),
        )
        direction = LightingDirection(
            **fields,
            trace=trace,
        )
        return LightingDirection(
            **fields,
            trace=trace,
            fingerprint=self._fingerprint(
                direction
            ),
        )

    def _decide(
        self,
        decisions: list[LightingDecisionTrace],
        field: str,
        candidates: tuple[tuple[str, Any], ...],
        justification: str
    ) -> str:
        selected = tuple(
            (
                source,
                _clean(
                    value
                )
            )
            for source, value in candidates
            if _clean(
                value
            )
        )
        if not selected:
            return ""
        value = " | ".join(
            _dedupe(
                tuple(
                    item[1]
                    for item in selected
                )
            )
        )
        decisions.append(
            LightingDecisionTrace(
                field=field,
                source_fields=tuple(
                    f"EffectiveVisualBrief.{item[0]}"
                    for item in selected
                ),
                transformation=(
                    "select_and_combine_resolved_effective_brief_fields"
                    if len(
                        selected
                    ) > 1
                    else "select_resolved_effective_brief_field"
                ),
                justification=justification,
            )
        )
        return value

    def _fingerprint(
        self,
        direction: LightingDirection
    ) -> str:
        canonical = {
            "direction": _canonical_mapping(
                LightingDirection(
                    dominant_lighting=direction.dominant_lighting,
                    luminous_atmosphere=direction.luminous_atmosphere,
                    perceived_contrast=direction.perceived_contrast,
                    softness_or_hardness=direction.softness_or_hardness,
                    conceptual_light_direction=direction.conceptual_light_direction,
                    shadow_distribution=direction.shadow_distribution,
                    subject_background_separation=direction.subject_background_separation,
                    perceived_volume=direction.perceived_volume,
                    dramatism=direction.dramatism,
                    naturalness=direction.naturalness,
                    mystery=direction.mystery,
                    warmth=direction.warmth,
                    coolness=direction.coolness,
                    narrative_clarity=direction.narrative_clarity,
                    luminous_hierarchy=direction.luminous_hierarchy,
                    spatial_feeling=direction.spatial_feeling,
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
