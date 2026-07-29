from dataclasses import dataclass, field

from app.domain import (
    EffectiveVisualBrief,
    Intention,
    NarrativeReading,
    VisualBible,
    VisualBrief,
)


@dataclass(frozen=True)
class VisualDirectionInput:
    visual_bible: VisualBible
    narrative_reading: NarrativeReading
    intention: Intention
    source_id: str = ""
    source_version: str = ""


@dataclass(frozen=True)
class VisualBriefFieldOrigin:
    field: str
    source_layer: str
    source_path: str
    action: str = "set"


@dataclass(frozen=True)
class VisualBriefTrace:
    field_origins: tuple[VisualBriefFieldOrigin, ...] = field(default_factory=tuple)
    reinforced_fields: tuple[str, ...] = field(default_factory=tuple)
    specialized_fields: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class VisualDirectionConflict:
    source_layers: tuple[str, ...]
    conflict_type: str
    description: str
    field: str = ""
    requires_review: bool = True
