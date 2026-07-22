from dataclasses import dataclass, field


@dataclass(frozen=True)
class MovementDecisionTrace:
    field: str
    source_fields: tuple[str, ...]
    transformation: str
    justification: str


@dataclass(frozen=True)
class MovementDirectionTrace:
    source_visual_brief_fingerprint: str = ""
    decisions: tuple[MovementDecisionTrace, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class MovementDirection:
    dominant_movement: str = ""
    movement_energy: str = ""
    stability: str = ""
    fluidity: str = ""
    displacement_rhythm: str = ""
    perceived_intensity: str = ""
    narrative_movement_direction: str = ""
    subject_tracking: str = ""
    movement_prominence: str = ""
    immersion_feeling: str = ""
    contemplation: str = ""
    dynamism: str = ""
    kinetic_tension: str = ""
    naturalness: str = ""
    movement_continuity: str = ""
    spatial_coherence: str = ""
    trace: MovementDirectionTrace = field(default_factory=MovementDirectionTrace)
    source_id: str = ""
    source_version: str = ""
    fingerprint: str = ""
