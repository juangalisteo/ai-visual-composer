from dataclasses import dataclass, field


@dataclass(frozen=True)
class LightingDecisionTrace:
    field: str
    source_fields: tuple[str, ...]
    transformation: str
    justification: str


@dataclass(frozen=True)
class LightingDirectionTrace:
    source_visual_brief_fingerprint: str = ""
    decisions: tuple[LightingDecisionTrace, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class LightingDirection:
    dominant_lighting: str = ""
    luminous_atmosphere: str = ""
    perceived_contrast: str = ""
    softness_or_hardness: str = ""
    conceptual_light_direction: str = ""
    shadow_distribution: str = ""
    subject_background_separation: str = ""
    perceived_volume: str = ""
    dramatism: str = ""
    naturalness: str = ""
    mystery: str = ""
    warmth: str = ""
    coolness: str = ""
    narrative_clarity: str = ""
    luminous_hierarchy: str = ""
    spatial_feeling: str = ""
    trace: LightingDirectionTrace = field(default_factory=LightingDirectionTrace)
    source_id: str = ""
    source_version: str = ""
    fingerprint: str = ""
