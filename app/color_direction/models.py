from dataclasses import dataclass, field


@dataclass(frozen=True)
class ColorDecisionTrace:
    field: str
    source_fields: tuple[str, ...]
    transformation: str
    justification: str


@dataclass(frozen=True)
class ColorDirectionTrace:
    source_visual_brief_fingerprint: str = ""
    decisions: tuple[ColorDecisionTrace, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ColorDirection:
    dominant_palette: str = ""
    color_harmony: str = ""
    chromatic_contrast: str = ""
    perceived_saturation: str = ""
    perceived_luminosity: str = ""
    emotional_temperature: str = ""
    chromatic_balance: str = ""
    dominant_color_role: str = ""
    secondary_color_role: str = ""
    accent_color_role: str = ""
    chromatic_symbolism: str = ""
    chromatic_continuity: str = ""
    chromatic_tension: str = ""
    naturalness: str = ""
    stylization: str = ""
    visual_coherence: str = ""
    trace: ColorDirectionTrace = field(default_factory=ColorDirectionTrace)
    source_id: str = ""
    source_version: str = ""
    fingerprint: str = ""
