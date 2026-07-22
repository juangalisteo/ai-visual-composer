import hashlib
import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from app.movement_direction.models import (
    MovementDecisionTrace,
    MovementDirection,
    MovementDirectionTrace,
)
from app.visual_direction import EffectiveVisualBrief


class MovementDirector:
    def resolve(
        self,
        effective_visual_brief: EffectiveVisualBrief
    ) -> MovementDirection:
        brief = effective_visual_brief.visual_brief
        decisions: list[MovementDecisionTrace] = []
        fields = {
            "dominant_movement": self._decide(
                decisions,
                "dominant_movement",
                (
                    _field(
                        "motion.direction",
                        _nested(
                            brief.motion,
                            "direction"
                        )
                    ),
                    _field(
                        "motion.latent_energy",
                        _nested(
                            brief.motion,
                            "latent_energy"
                        )
                    ),
                    _field(
                        "staging.action_or_state",
                        _nested(
                            brief.staging,
                            "action_or_state"
                        )
                    ),
                ),
                "Preserve the resolved dominant movement cues."
            ),
            "movement_energy": self._decide(
                decisions,
                "movement_energy",
                (
                    _field(
                        "motion.latent_energy",
                        _nested(
                            brief.motion,
                            "latent_energy"
                        )
                    ),
                    _field(
                        "scene_rhythm",
                        brief.scene_rhythm
                    ),
                    _field(
                        "dominant_visual_intention",
                        brief.dominant_visual_intention
                    ),
                ),
                "Translate resolved energy, rhythm and intention into movement energy."
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
                        "photography.point_of_view",
                        _nested(
                            brief.photography,
                            "point_of_view"
                        )
                    ),
                ),
                "Keep movement stability aligned with resolved balance and point of view."
            ),
            "fluidity": self._decide(
                decisions,
                "fluidity",
                (
                    _field(
                        "motion.visual_breathing",
                        _nested(
                            brief.motion,
                            "visual_breathing"
                        )
                    ),
                    _field(
                        "motion.rhythm",
                        _nested(
                            brief.motion,
                            "rhythm"
                        )
                    ),
                    _field(
                        "lighting.atmosphere",
                        _nested(
                            brief.lighting,
                            "atmosphere"
                        )
                    ),
                ),
                "Represent movement fluidity through resolved breathing, rhythm and atmosphere."
            ),
            "displacement_rhythm": self._decide(
                decisions,
                "displacement_rhythm",
                (
                    _field(
                        "motion.rhythm",
                        _nested(
                            brief.motion,
                            "rhythm"
                        )
                    ),
                    _field(
                        "scene_rhythm",
                        brief.scene_rhythm
                    ),
                    _field(
                        "composition.reading_direction",
                        _nested(
                            brief.composition,
                            "reading_direction"
                        )
                    ),
                ),
                "Use resolved rhythm and visual reading as displacement rhythm."
            ),
            "perceived_intensity": self._decide(
                decisions,
                "perceived_intensity",
                (
                    _field(
                        "motion.latent_energy",
                        _nested(
                            brief.motion,
                            "latent_energy"
                        )
                    ),
                    _field(
                        "visual_priority",
                        brief.visual_priority
                    ),
                    _field(
                        "intention_coherence",
                        brief.intention_coherence
                    ),
                ),
                "Translate resolved energy and priority into perceived movement intensity."
            ),
            "narrative_movement_direction": self._decide(
                decisions,
                "narrative_movement_direction",
                (
                    _field(
                        "motion.direction",
                        _nested(
                            brief.motion,
                            "direction"
                        )
                    ),
                    _field(
                        "visual_reading",
                        brief.visual_reading
                    ),
                    _field(
                        "dominant_visual_intention",
                        brief.dominant_visual_intention
                    ),
                ),
                "Preserve the resolved narrative direction of movement without adding action."
            ),
            "subject_tracking": self._decide(
                decisions,
                "subject_tracking",
                (
                    _field(
                        "primary_subject",
                        brief.primary_subject
                    ),
                    _field(
                        "staging.main_subject",
                        _nested(
                            brief.staging,
                            "main_subject"
                        )
                    ),
                    _field(
                        "attention_focus",
                        brief.attention_focus
                    ),
                ),
                "Tie subject following only to resolved subject and attention cues."
            ),
            "movement_prominence": self._decide(
                decisions,
                "movement_prominence",
                (
                    _field(
                        "visual_priority",
                        brief.visual_priority
                    ),
                    _field(
                        "symbolic_weight",
                        brief.symbolic_weight
                    ),
                    _field(
                        "attention_focus",
                        brief.attention_focus
                    ),
                ),
                "Preserve how important movement is within the resolved visual hierarchy."
            ),
            "immersion_feeling": self._decide(
                decisions,
                "immersion_feeling",
                (
                    _field(
                        "staging.spatial_relationship",
                        _nested(
                            brief.staging,
                            "spatial_relationship"
                        )
                    ),
                    _field(
                        "photography.emotional_distance",
                        _nested(
                            brief.photography,
                            "emotional_distance"
                        )
                    ),
                    _field(
                        "felt_experience",
                        brief.felt_experience
                    ),
                ),
                "Use resolved space and emotional distance as immersion feeling."
            ),
            "contemplation": self._decide(
                decisions,
                "contemplation",
                (
                    _field(
                        "motion.stillness",
                        _nested(
                            brief.motion,
                            "stillness"
                        )
                    ),
                    _field(
                        "felt_experience",
                        brief.felt_experience
                    ),
                    _field(
                        "visual_bible_coherence",
                        brief.visual_bible_coherence
                    ),
                ),
                "Represent contemplative movement only from resolved stillness and feeling."
            ),
            "dynamism": self._decide(
                decisions,
                "dynamism",
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
                ),
                "Translate resolved energy, direction and spatial tension into dynamism."
            ),
            "kinetic_tension": self._decide(
                decisions,
                "kinetic_tension",
                (
                    _field(
                        "motion.progression_or_suspension",
                        _nested(
                            brief.motion,
                            "progression_or_suspension"
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
                "Keep kinetic tension tied to resolved suspension, space and intention."
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
                        "staging.action_or_state",
                        _nested(
                            brief.staging,
                            "action_or_state"
                        )
                    ),
                    _field(
                        "visual_bible_coherence",
                        brief.visual_bible_coherence
                    ),
                ),
                "Keep movement naturalness aligned with resolved realism and staging."
            ),
            "movement_continuity": self._decide(
                decisions,
                "movement_continuity",
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
                        "motion.progression_or_suspension",
                        _nested(
                            brief.motion,
                            "progression_or_suspension"
                        )
                    ),
                ),
                "Preserve resolved continuity as movement continuity."
            ),
            "spatial_coherence": self._decide(
                decisions,
                "spatial_coherence",
                (
                    _field(
                        "staging.spatial_relationship",
                        _nested(
                            brief.staging,
                            "spatial_relationship"
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
                        "narrative_coherence",
                        brief.narrative_coherence
                    ),
                ),
                "Keep movement spatial coherence aligned with resolved space and narrative."
            ),
        }
        trace = MovementDirectionTrace(
            source_visual_brief_fingerprint=effective_visual_brief.fingerprint,
            decisions=tuple(
                decisions
            ),
        )
        direction = MovementDirection(
            **fields,
            trace=trace,
            source_id=effective_visual_brief.source_id,
            source_version=effective_visual_brief.source_version,
        )
        return MovementDirection(
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
        decisions: list[MovementDecisionTrace],
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
            MovementDecisionTrace(
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
        direction: MovementDirection
    ) -> str:
        canonical = {
            "MovementDirection": _canonical_mapping(
                MovementDirection(
                    dominant_movement=direction.dominant_movement,
                    movement_energy=direction.movement_energy,
                    stability=direction.stability,
                    fluidity=direction.fluidity,
                    displacement_rhythm=direction.displacement_rhythm,
                    perceived_intensity=direction.perceived_intensity,
                    narrative_movement_direction=direction.narrative_movement_direction,
                    subject_tracking=direction.subject_tracking,
                    movement_prominence=direction.movement_prominence,
                    immersion_feeling=direction.immersion_feeling,
                    contemplation=direction.contemplation,
                    dynamism=direction.dynamism,
                    kinetic_tension=direction.kinetic_tension,
                    naturalness=direction.naturalness,
                    movement_continuity=direction.movement_continuity,
                    spatial_coherence=direction.spatial_coherence,
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
