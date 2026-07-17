from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class NarrativeAnalysis:
    source_text: str
    summary: str = ""
    themes: tuple[str, ...] = field(default_factory=tuple)
    concepts: tuple[str, ...] = field(default_factory=tuple)
    tensions: tuple[str, ...] = field(default_factory=tuple)
    tone: str = ""
    abstraction_level: str = ""
    notes: str = ""


@dataclass(frozen=True)
class GlobalIntention:
    purpose: str
    emotional_arc: str = ""
    intellectual_arc: str = ""
    dominant_emotion: str = ""
    secondary_emotion: str = ""
    initial_state: str = ""
    final_state: str = ""
    visual_energy: str = ""
    notes: str = ""


@dataclass(frozen=True)
class LocalIntention:
    global_intention: GlobalIntention
    scene_function: str
    dominant_emotion: str = ""
    secondary_emotion: str = ""
    narrative_tension: str = ""
    abstraction_level: str = ""
    intimacy_level: str = ""
    clarity_level: str = ""
    relation_to_global_arc: str = ""
    notes: str = ""


@dataclass(frozen=True)
class StoryboardScene:
    scene_number: int
    text: str
    narrative_role: str = ""
    narrative_moment: str = ""
    subject: str = ""
    action: str = ""
    setting: str = ""
    duration: float | None = None
    source_index: int | None = None
    notes: str = ""


@dataclass(frozen=True)
class VisualPlan:
    storyboard_scene: StoryboardScene
    local_intention: LocalIntention | None = None
    staging: tuple[str, ...] = field(default_factory=tuple)
    art_direction: tuple[str, ...] = field(default_factory=tuple)
    photography: tuple[str, ...] = field(default_factory=tuple)
    composition: tuple[str, ...] = field(default_factory=tuple)
    continuity: tuple[str, ...] = field(default_factory=tuple)
    constraints: tuple[str, ...] = field(default_factory=tuple)
    notes: str = ""


@dataclass(frozen=True)
class VisualBrief:
    storyboard_scene: StoryboardScene
    visual_plan: VisualPlan | None = None
    subject: str = ""
    environment: str = ""
    action: str = ""
    mood: str = ""
    composition: str = ""
    camera: str = ""
    lighting: str = ""
    color: str = ""
    constraints: tuple[str, ...] = field(default_factory=tuple)
    negative_constraints: tuple[str, ...] = field(default_factory=tuple)
    notes: str = ""


@dataclass(frozen=True)
class GenerationResult:
    output_path: str
    scene_number: int | None = None
    width: int | None = None
    height: int | None = None
    duration: float | None = None
    status: str = "completed"
    generation_id: str = ""
    metadata: tuple[tuple[str, Any], ...] = field(default_factory=tuple)
