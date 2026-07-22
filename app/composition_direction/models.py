from dataclasses import dataclass, field


@dataclass(frozen=True)
class CompositionDecisionTrace:
    field: str
    source_fields: tuple[str, ...]
    transformation: str
    justification: str


@dataclass(frozen=True)
class CompositionDirectionTrace:
    source_visual_brief_fingerprint: str = ""
    decisions: tuple[CompositionDecisionTrace, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CompositionDirection:
    dominant_composition: str = ""
    visual_balance: str = ""
    spatial_distribution: str = ""
    compositional_hierarchy: str = ""
    visual_weight: str = ""
    compositional_rhythm: str = ""
    visual_tension: str = ""
    symmetry_or_asymmetry: str = ""
    negative_space_usage: str = ""
    foreground_organization: str = ""
    midground_organization: str = ""
    background_organization: str = ""
    compositional_depth: str = ""
    visual_reading_direction: str = ""
    stability: str = ""
    compositional_dynamism: str = ""
    trace: CompositionDirectionTrace = field(default_factory=CompositionDirectionTrace)
    source_id: str = ""
    source_version: str = ""
    fingerprint: str = ""
