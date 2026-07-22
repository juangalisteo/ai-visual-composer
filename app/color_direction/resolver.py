import hashlib
import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from app.color_direction.models import (
    ColorDecisionTrace,
    ColorDirection,
    ColorDirectionTrace,
)
from app.visual_direction import EffectiveVisualBrief


class ColorDirector:
    def resolve(
        self,
        effective_visual_brief: EffectiveVisualBrief
    ) -> ColorDirection:
        brief = effective_visual_brief.visual_brief
        decisions: list[ColorDecisionTrace] = []
        fields = {
            "dominant_palette": self._decide(
                decisions,
                "dominant_palette",
                (
                    _field(
                        "color.palette",
                        _nested(
                            brief.color,
                            "palette"
                        )
                    ),
                    _field(
                        "color.harmony",
                        _nested(
                            brief.color,
                            "harmony"
                        )
                    ),
                    _field(
                        "visual_bible_coherence",
                        brief.visual_bible_coherence
                    ),
                ),
                "Preserve the resolved palette and its relationship with visual identity."
            ),
            "color_harmony": self._decide(
                decisions,
                "color_harmony",
                (
                    _field(
                        "color.harmony",
                        _nested(
                            brief.color,
                            "harmony"
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
                "Translate resolved harmony cues into a high-level color relationship."
            ),
            "chromatic_contrast": self._decide(
                decisions,
                "chromatic_contrast",
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
                    _field(
                        "visual_priority",
                        brief.visual_priority
                    ),
                ),
                "Keep chromatic contrast tied to resolved priority and rupture cues."
            ),
            "perceived_saturation": self._decide(
                decisions,
                "perceived_saturation",
                (
                    _field(
                        "color.saturation",
                        _nested(
                            brief.color,
                            "saturation"
                        )
                    ),
                    _field(
                        "visual_strategy.realism_level",
                        _nested(
                            brief.visual_strategy,
                            "realism_level"
                        )
                    ),
                ),
                "Represent perceived saturation without technical color values."
            ),
            "perceived_luminosity": self._decide(
                decisions,
                "perceived_luminosity",
                (
                    _field(
                        "lighting.visibility",
                        _nested(
                            brief.lighting,
                            "visibility"
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
                        "photography.photographic_atmosphere",
                        _nested(
                            brief.photography,
                            "photographic_atmosphere"
                        )
                    ),
                ),
                "Translate resolved visibility and atmosphere into perceived luminosity."
            ),
            "emotional_temperature": self._decide(
                decisions,
                "emotional_temperature",
                (
                    _field(
                        "color.temperature",
                        _nested(
                            brief.color,
                            "temperature"
                        )
                    ),
                    _field(
                        "felt_experience",
                        brief.felt_experience
                    ),
                    _field(
                        "dominant_visual_intention",
                        brief.dominant_visual_intention
                    ),
                ),
                "Preserve emotional temperature as a conceptual color feeling."
            ),
            "chromatic_balance": self._decide(
                decisions,
                "chromatic_balance",
                (
                    _field(
                        "color.harmony",
                        _nested(
                            brief.color,
                            "harmony"
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
                        "visual_bible_coherence",
                        brief.visual_bible_coherence
                    ),
                ),
                "Keep color balance aligned with resolved composition and visual identity."
            ),
            "dominant_color_role": self._decide(
                decisions,
                "dominant_color_role",
                (
                    _field(
                        "color.visual_identity_relationship",
                        _nested(
                            brief.color,
                            "visual_identity_relationship"
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
                "Assign dominant color role only from resolved identity and attention cues."
            ),
            "secondary_color_role": self._decide(
                decisions,
                "secondary_color_role",
                (
                    _field(
                        "secondary_subject",
                        brief.secondary_subject
                    ),
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
                ),
                "Use resolved secondary subject and environment cues as supporting color role."
            ),
            "accent_color_role": self._decide(
                decisions,
                "accent_color_role",
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
                        "visual_reading",
                        brief.visual_reading
                    ),
                ),
                "Translate symbolic and attentional cues into conceptual accent color role."
            ),
            "chromatic_symbolism": self._decide(
                decisions,
                "chromatic_symbolism",
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
                        "color.visual_identity_relationship",
                        _nested(
                            brief.color,
                            "visual_identity_relationship"
                        )
                    ),
                ),
                "Preserve resolved symbolism as color meaning without adding symbols."
            ),
            "chromatic_continuity": self._decide(
                decisions,
                "chromatic_continuity",
                (
                    _field(
                        "color.emotional_evolution",
                        _nested(
                            brief.color,
                            "emotional_evolution"
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
                "Use resolved evolution and continuity cues as chromatic continuity."
            ),
            "chromatic_tension": self._decide(
                decisions,
                "chromatic_tension",
                (
                    _field(
                        "color.rupture",
                        _nested(
                            brief.color,
                            "rupture"
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
                        "intention_coherence",
                        brief.intention_coherence
                    ),
                ),
                "Translate resolved rupture, tension and intention coherence into color tension."
            ),
            "naturalness": self._decide(
                decisions,
                "naturalness",
                (
                    _field(
                        "visual_strategy.realism_level",
                        _nested(
                            brief.visual_strategy,
                            "realism_level"
                        )
                    ),
                    _field(
                        "color.harmony",
                        _nested(
                            brief.color,
                            "harmony"
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
                "Keep color naturalness aligned with resolved realism and motivated light."
            ),
            "stylization": self._decide(
                decisions,
                "stylization",
                (
                    _field(
                        "visual_strategy.symbolism_degree",
                        _nested(
                            brief.visual_strategy,
                            "symbolism_degree"
                        )
                    ),
                    _field(
                        "visual_strategy.world_style",
                        _nested(
                            brief.visual_strategy,
                            "world_style"
                        )
                    ),
                    _field(
                        "color.visual_identity_relationship",
                        _nested(
                            brief.color,
                            "visual_identity_relationship"
                        )
                    ),
                ),
                "Represent stylization only from resolved strategy and visual identity cues."
            ),
            "visual_coherence": self._decide(
                decisions,
                "visual_coherence",
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
                "Preserve color coherence with resolved visual, narrative and intention layers."
            ),
        }
        trace = ColorDirectionTrace(
            source_visual_brief_fingerprint=effective_visual_brief.fingerprint,
            decisions=tuple(
                decisions
            ),
        )
        direction = ColorDirection(
            **fields,
            trace=trace,
            source_id=effective_visual_brief.source_id,
            source_version=effective_visual_brief.source_version,
        )
        return ColorDirection(
            **fields,
            trace=trace,
            source_id=effective_visual_brief.source_id,
            source_version=effective_visual_brief.source_version,
            fingerprint=self._fingerprint(
                direction
            ),
        )

    def _decide(
        self,
        decisions: list[ColorDecisionTrace],
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
            f"VisualBrief.{name}"
            for name, _ in selected
        )
        transformation = "select_resolved_visual_brief_field"
        if len(
            unique_values
        ) > 1:
            transformation = "select_and_combine_resolved_visual_brief_fields"
        decisions.append(
            ColorDecisionTrace(
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
        direction: ColorDirection
    ) -> str:
        canonical = {
            "ColorDirection": _canonical_mapping(
                ColorDirection(
                    dominant_palette=direction.dominant_palette,
                    color_harmony=direction.color_harmony,
                    chromatic_contrast=direction.chromatic_contrast,
                    perceived_saturation=direction.perceived_saturation,
                    perceived_luminosity=direction.perceived_luminosity,
                    emotional_temperature=direction.emotional_temperature,
                    chromatic_balance=direction.chromatic_balance,
                    dominant_color_role=direction.dominant_color_role,
                    secondary_color_role=direction.secondary_color_role,
                    accent_color_role=direction.accent_color_role,
                    chromatic_symbolism=direction.chromatic_symbolism,
                    chromatic_continuity=direction.chromatic_continuity,
                    chromatic_tension=direction.chromatic_tension,
                    naturalness=direction.naturalness,
                    stylization=direction.stylization,
                    visual_coherence=direction.visual_coherence,
                    trace=direction.trace,
                    source_id=direction.source_id,
                    source_version=direction.source_version,
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
