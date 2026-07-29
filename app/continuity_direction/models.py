from dataclasses import dataclass, field


@dataclass(frozen=True)
class ContinuityDecisionTrace:
    field: str
    source_fields: tuple[str, ...]
    transformation: str
    justification: str


@dataclass(frozen=True)
class ContinuityDirectionTrace:
    source_effective_brief_fingerprint: str = ""
    decisions: tuple[ContinuityDecisionTrace, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ContinuityDirection:
    visual_continuity: str = ""
    inter_scene_coherence: str = ""
    identity_persistence: str = ""
    character_consistency: str = ""
    wardrobe_consistency: str = ""
    lighting_consistency: str = ""
    chromatic_consistency: str = ""
    compositional_consistency: str = ""
    movement_consistency: str = ""
    spatial_continuity: str = ""
    temporal_continuity: str = ""
    visual_narrative_continuity: str = ""
    stylistic_stability: str = ""
    global_coherence: str = ""
    key_element_preservation: str = ""
    visual_transition: str = ""
    trace: ContinuityDirectionTrace = field(default_factory=ContinuityDirectionTrace)
    fingerprint: str = ""
