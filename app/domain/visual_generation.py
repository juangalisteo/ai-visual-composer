from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class NarrativeReading:
    event: str
    meaning: str = ""
    central_idea: str = ""
    scene_function: str = ""
    relevant_concepts: tuple[str, ...] = field(default_factory=tuple)
    possible_symbols: tuple[str, ...] = field(default_factory=tuple)
    symbols_to_avoid: tuple[str, ...] = field(default_factory=tuple)
    relation_to_whole: str = ""


@dataclass(frozen=True)
class GlobalIntent:
    expressive_purpose: str
    dominant_emotion: str = ""
    tone: str = ""
    global_energy: str = ""
    transformation_arc: str = ""
    audience_relationship: str = ""


@dataclass(frozen=True)
class SceneIntent:
    emotional_function: str
    emotion: str = ""
    emotional_intensity: str = ""
    narrative_tension: str = ""
    subtext: str = ""
    temporal_impulse: str = ""
    nearby_scene_contrast: str = ""


@dataclass(frozen=True)
class VisualStrategy:
    representation_approach: str
    realism_level: str = ""
    symbolism_degree: str = ""
    scale_treatment: str = ""
    world_style: str = ""
    visual_limits: tuple[str, ...] = field(default_factory=tuple)
    resources_to_avoid: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class StagingPlan:
    main_subject: str
    environment: str = ""
    action_or_state: str = ""
    spatial_relationship: str = ""
    significant_objects: tuple[str, ...] = field(default_factory=tuple)
    human_presence: str = ""
    narrative_distribution: str = ""


@dataclass(frozen=True)
class PhotographyPlan:
    point_of_view: str
    emotional_distance: str = ""
    depth: str = ""
    texture: str = ""
    photographic_atmosphere: str = ""
    light_volume_treatment: str = ""
    photographic_realism: str = ""


@dataclass(frozen=True)
class CompositionPlan:
    visual_hierarchy: str
    framing: str = ""
    balance: str = ""
    negative_space: str = ""
    frame_scale: str = ""
    reading_direction: str = ""
    spatial_tension: str = ""
    figure_ground_relationship: str = ""


@dataclass(frozen=True)
class LightingPlan:
    source: str
    direction: str = ""
    quality: str = ""
    hardness: str = ""
    contrast: str = ""
    motivation: str = ""
    atmosphere: str = ""
    visibility: str = ""
    volume: str = ""


@dataclass(frozen=True)
class ColorPlan:
    temperature: str
    palette: tuple[str, ...] = field(default_factory=tuple)
    saturation: str = ""
    chromatic_contrast: str = ""
    harmony: str = ""
    rupture: str = ""
    emotional_evolution: str = ""
    visual_identity_relationship: str = ""


@dataclass(frozen=True)
class MotionSense:
    latent_energy: str
    rhythm: str = ""
    stillness: str = ""
    direction: str = ""
    stability: str = ""
    progression_or_suspension: str = ""
    visual_breathing: str = ""


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
class VisualBrief:
    visible_content: str
    felt_experience: str = ""
    visual_strategy: VisualStrategy | None = None
    staging: StagingPlan | None = None
    photography: PhotographyPlan | None = None
    composition: CompositionPlan | None = None
    lighting: LightingPlan | None = None
    color: ColorPlan | None = None
    motion: MotionSense | None = None
    continuity_relationship: str = ""


@dataclass(frozen=True)
class GenerationTranslation:
    target_backend: str
    translation_priorities: tuple[str, ...] = field(default_factory=tuple)
    translation_restrictions: tuple[str, ...] = field(default_factory=tuple)
    translated_directives: tuple[str, ...] = field(default_factory=tuple)
    trace_references: tuple[str, ...] = field(default_factory=tuple)


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
