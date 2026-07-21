from dataclasses import dataclass, field


@dataclass(frozen=True)
class PhotographyDecisionTrace:
    field: str
    source_fields: tuple[str, ...]
    transformation: str
    justification: str


@dataclass(frozen=True)
class PhotographyDirectionTrace:
    source_visual_brief_fingerprint: str = ""
    decisions: tuple[PhotographyDecisionTrace, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PhotographyDirection:
    dominant_photographic_language: str = ""
    emotional_camera_distance: str = ""
    narrative_scale: str = ""
    point_of_view: str = ""
    predominant_framing: str = ""
    perceived_depth: str = ""
    subject_environment_relationship: str = ""
    presence_feeling: str = ""
    intimacy: str = ""
    isolation: str = ""
    monumentality: str = ""
    observation: str = ""
    dynamism: str = ""
    contemplation: str = ""
    trace: PhotographyDirectionTrace = field(default_factory=PhotographyDirectionTrace)
    source_id: str = ""
    source_version: str = ""
    fingerprint: str = ""
