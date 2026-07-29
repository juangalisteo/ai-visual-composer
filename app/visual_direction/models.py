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


# TRANSITIONAL COMPONENT
# Temporary compatibility during Runtime Integration migration.
# Scheduled for reevaluation after completion of IP3.0-5.
# Do not introduce new dependencies.
@dataclass(frozen=True)
class VisualBriefTrace:
    field_origins: tuple[VisualBriefFieldOrigin, ...] = field(default_factory=tuple)
    reinforced_fields: tuple[str, ...] = field(default_factory=tuple)
    specialized_fields: tuple[str, ...] = field(default_factory=tuple)


# TRANSITIONAL COMPONENT
# Temporary compatibility during Runtime Integration migration.
# Scheduled for reevaluation after completion of IP3.0-5.
# Do not introduce new dependencies.
@dataclass(frozen=True)
class VisualDirectionConflict:
    source_layers: tuple[str, ...]
    conflict_type: str
    description: str
    field: str = ""
    requires_review: bool = True
