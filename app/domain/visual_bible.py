from dataclasses import dataclass, field


@dataclass(frozen=True)
class VisualPhilosophy:
    beauty: str = ""
    elegance: str = ""
    sobriety: str = ""
    excess: str = ""
    artifice: str = ""
    authenticity: str = ""
    naturalness: str = ""
    non_negotiable_principles: tuple[str, ...] = field(default_factory=tuple)
    incompatible_images: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Identity:
    visual_statement: str = ""
    sensibility: str = ""
    dominant_tone: str = ""
    visual_personality: str = ""
    recognition: str = ""


@dataclass(frozen=True)
class CinematicLanguage:
    rhythm: str = ""
    observational_distance: str = ""
    immersion: str = ""
    theatricality: str = ""
    audiovisual_energy: str = ""


@dataclass(frozen=True)
class RealismAndAbstraction:
    realism_level: str = ""
    stylization_level: str = ""
    abstraction_level: str = ""
    poetic_license: str = ""
    artifice_limits: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SymbolicSystem:
    allowed_symbols: tuple[str, ...] = field(default_factory=tuple)
    recurring_symbols: tuple[str, ...] = field(default_factory=tuple)
    forbidden_symbols: tuple[str, ...] = field(default_factory=tuple)
    literalness: str = ""
    metaphor_degree: str = ""


@dataclass(frozen=True)
class CompositionPrinciples:
    balance: str = ""
    negative_space: str = ""
    density: str = ""
    scale: str = ""
    hierarchy: str = ""
    figure_ground_relationship: str = ""


@dataclass(frozen=True)
class PhotographyPrinciples:
    point_of_view: str = ""
    emotional_distance: str = ""
    depth: str = ""
    optical_texture: str = ""
    naturalism: str = ""
    subject_relationship: str = ""


@dataclass(frozen=True)
class LightingPrinciples:
    dominant_source: str = ""
    motivation: str = ""
    contrast: str = ""
    shadow: str = ""
    visibility: str = ""
    atmosphere: str = ""


@dataclass(frozen=True)
class ColorSystem:
    dominant_temperature: str = ""
    base_palette: tuple[str, ...] = field(default_factory=tuple)
    secondary_palettes: tuple[str, ...] = field(default_factory=tuple)
    saturation: str = ""
    contrast: str = ""
    colors_to_avoid: tuple[str, ...] = field(default_factory=tuple)
    evolution_rules: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class TextureAndMateriality:
    preferred_materials: tuple[str, ...] = field(default_factory=tuple)
    tactility: str = ""
    grain: str = ""
    detail: str = ""
    polish: str = ""
    naturalness: str = ""


@dataclass(frozen=True)
class ContinuityPrinciples:
    atmosphere: str = ""
    light: str = ""
    color: str = ""
    symbols: str = ""
    scale: str = ""
    density: str = ""


@dataclass(frozen=True)
class CreativeLimits:
    foreign_styles: tuple[str, ...] = field(default_factory=tuple)
    cliches: tuple[str, ...] = field(default_factory=tuple)
    excesses: tuple[str, ...] = field(default_factory=tuple)
    incompatible_resources: tuple[str, ...] = field(default_factory=tuple)
    unacceptable_artifice_levels: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class QualityCriteria:
    coherence: str = ""
    elegance: str = ""
    specificity: str = ""
    naturalness: str = ""
    cinematic_strength: str = ""
    generic_aesthetic_absence: str = ""
    belonging: str = ""


@dataclass(frozen=True)
class VisualBible:
    philosophy: VisualPhilosophy
    identity: Identity
    cinematic_language: CinematicLanguage
    realism_and_abstraction: RealismAndAbstraction
    symbolic_system: SymbolicSystem
    composition: CompositionPrinciples
    photography: PhotographyPrinciples
    lighting: LightingPrinciples
    color: ColorSystem
    texture_and_materiality: TextureAndMateriality
    continuity: ContinuityPrinciples
    creative_limits: CreativeLimits
    quality: QualityCriteria
