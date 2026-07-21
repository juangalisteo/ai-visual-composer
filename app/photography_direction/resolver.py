import hashlib
import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from app.photography_direction.models import (
    PhotographyDecisionTrace,
    PhotographyDirection,
    PhotographyDirectionTrace,
)
from app.visual_direction import EffectiveVisualBrief


class PhotographyDirector:
    def resolve(
        self,
        effective_visual_brief: EffectiveVisualBrief
    ) -> PhotographyDirection:
        brief = effective_visual_brief.visual_brief
        decisions: list[PhotographyDecisionTrace] = []
        fields = {
            "dominant_photographic_language": self._decide(
                decisions,
                "dominant_photographic_language",
                (
                    _field(
                        "photography.photographic_atmosphere",
                        _nested(
                            brief.photography,
                            "photographic_atmosphere"
                        )
                    ),
                    _field(
                        "photography.photographic_realism",
                        _nested(
                            brief.photography,
                            "photographic_realism"
                        )
                    ),
                    _field(
                        "visual_bible_coherence",
                        brief.visual_bible_coherence
                    ),
                ),
                "Select the strongest existing photographic language cue."
            ),
            "emotional_camera_distance": self._decide(
                decisions,
                "emotional_camera_distance",
                (
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
                "Preserve the resolved emotional distance without choosing equipment."
            ),
            "narrative_scale": self._decide(
                decisions,
                "narrative_scale",
                (
                    _field(
                        "composition.frame_scale",
                        _nested(
                            brief.composition,
                            "frame_scale"
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
                "Translate narrative hierarchy into photographic scale."
            ),
            "point_of_view": self._decide(
                decisions,
                "point_of_view",
                (
                    _field(
                        "photography.point_of_view",
                        _nested(
                            brief.photography,
                            "point_of_view"
                        )
                    ),
                    _field(
                        "attention_focus",
                        brief.attention_focus
                    ),
                ),
                "Use the resolved point of view or attentional focus as camera stance."
            ),
            "predominant_framing": self._decide(
                decisions,
                "predominant_framing",
                (
                    _field(
                        "composition.framing",
                        _nested(
                            brief.composition,
                            "framing"
                        )
                    ),
                    _field(
                        "composition.visual_hierarchy",
                        _nested(
                            brief.composition,
                            "visual_hierarchy"
                        )
                    ),
                    _field(
                        "visual_priority",
                        brief.visual_priority
                    ),
                ),
                "Translate composition hierarchy into a high-level framing direction."
            ),
            "perceived_depth": self._decide(
                decisions,
                "perceived_depth",
                (
                    _field(
                        "photography.depth",
                        _nested(
                            brief.photography,
                            "depth"
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
                "Preserve resolved depth and figure-ground cues."
            ),
            "subject_environment_relationship": self._decide(
                decisions,
                "subject_environment_relationship",
                (
                    _field(
                        "staging.spatial_relationship",
                        _nested(
                            brief.staging,
                            "spatial_relationship"
                        )
                    ),
                    _field(
                        "staging.environment",
                        _nested(
                            brief.staging,
                            "environment"
                        )
                    ),
                    _field(
                        "primary_subject",
                        brief.primary_subject
                    ),
                ),
                "Keep the subject-environment relation defined by staging and subject priority."
            ),
            "presence_feeling": self._decide(
                decisions,
                "presence_feeling",
                (
                    _field(
                        "staging.human_presence",
                        _nested(
                            brief.staging,
                            "human_presence"
                        )
                    ),
                    _field(
                        "visible_content",
                        brief.visible_content
                    ),
                    _field(
                        "felt_experience",
                        brief.felt_experience
                    ),
                ),
                "Convert resolved presence cues into photographic presence."
            ),
            "intimacy": self._decide(
                decisions,
                "intimacy",
                (
                    _field(
                        "photography.emotional_distance",
                        _nested(
                            brief.photography,
                            "emotional_distance"
                        )
                    ),
                    _field(
                        "attention_focus",
                        brief.attention_focus
                    ),
                ),
                "Use existing emotional and attentional closeness as intimacy signal."
            ),
            "isolation": self._decide(
                decisions,
                "isolation",
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
                "Use spatial separation cues without inventing new blocking."
            ),
            "monumentality": self._decide(
                decisions,
                "monumentality",
                (
                    _field(
                        "visual_reading",
                        brief.visual_reading
                    ),
                    _field(
                        "symbolic_weight",
                        brief.symbolic_weight
                    ),
                ),
                "Translate symbolic weight into photographic scale only when present."
            ),
            "observation": self._decide(
                decisions,
                "observation",
                (
                    _field(
                        "photography.point_of_view",
                        _nested(
                            brief.photography,
                            "point_of_view"
                        )
                    ),
                    _field(
                        "dominant_visual_intention",
                        brief.dominant_visual_intention
                    ),
                ),
                "Preserve the resolved observer stance."
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
                        "scene_rhythm",
                        brief.scene_rhythm
                    ),
                ),
                "Translate resolved motion and rhythm into photographic energy."
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
                        "scene_rhythm",
                        brief.scene_rhythm
                    ),
                    _field(
                        "felt_experience",
                        brief.felt_experience
                    ),
                ),
                "Use resolved stillness, rhythm and felt experience as contemplation cue."
            ),
        }
        trace = PhotographyDirectionTrace(
            source_visual_brief_fingerprint=effective_visual_brief.fingerprint,
            decisions=tuple(
                decisions
            ),
        )
        direction = PhotographyDirection(
            **fields,
            trace=trace,
            source_id=effective_visual_brief.source_id,
            source_version=effective_visual_brief.source_version,
        )
        return PhotographyDirection(
            **fields,
            trace=trace,
            source_id=direction.source_id,
            source_version=direction.source_version,
            fingerprint=self._fingerprint(
                direction
            ),
        )

    def _decide(
        self,
        decisions: list[PhotographyDecisionTrace],
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
            PhotographyDecisionTrace(
                field=field,
                source_fields=tuple(
                    f"VisualBrief.{item[0]}"
                    for item in selected
                ),
                transformation=(
                    "select_and_combine_resolved_visual_brief_fields"
                    if len(
                        selected
                    ) > 1
                    else "select_resolved_visual_brief_field"
                ),
                justification=justification,
            )
        )
        return value

    def _fingerprint(
        self,
        direction: PhotographyDirection
    ) -> str:
        canonical = {
            "direction": _canonical_mapping(
                PhotographyDirection(
                    dominant_photographic_language=direction.dominant_photographic_language,
                    emotional_camera_distance=direction.emotional_camera_distance,
                    narrative_scale=direction.narrative_scale,
                    point_of_view=direction.point_of_view,
                    predominant_framing=direction.predominant_framing,
                    perceived_depth=direction.perceived_depth,
                    subject_environment_relationship=direction.subject_environment_relationship,
                    presence_feeling=direction.presence_feeling,
                    intimacy=direction.intimacy,
                    isolation=direction.isolation,
                    monumentality=direction.monumentality,
                    observation=direction.observation,
                    dynamism=direction.dynamism,
                    contemplation=direction.contemplation,
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
