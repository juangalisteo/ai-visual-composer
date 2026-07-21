from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.domain import Intention, IntentionLevel


@dataclass(frozen=True)
class IntentionReference:
    id: str
    version: str = ""


@dataclass(frozen=True)
class IntentionMetadata:
    owner: str = ""
    status: str = ""
    source: str = ""
    description: str = ""


@dataclass(frozen=True)
class IntentionDocument:
    schema_version: int
    id: str
    version: str
    type: str
    title: str
    extends: IntentionReference | None
    metadata: IntentionMetadata
    trace: dict[str, Any]
    intention: dict[str, Any]
    source_path: Path


@dataclass(frozen=True)
class IntentionFieldOrigin:
    path: str
    source_id: str
    source_version: str
    action: str = "set"


@dataclass(frozen=True)
class IntentionTrace:
    inheritance_chain: tuple[str, ...]
    references: tuple[str, ...] = field(default_factory=tuple)
    field_origins: tuple[IntentionFieldOrigin, ...] = field(default_factory=tuple)
    active_exclusions: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class IntentionConflict:
    source_id: str
    conflict_type: str
    description: str
    requires_review: bool = True


@dataclass(frozen=True)
class EffectiveIntention:
    intention: Intention
    source_id: str
    source_version: str
    schema_version: int
    level: IntentionLevel
    inheritance_chain: tuple[str, ...]
    trace: IntentionTrace
    conflicts: tuple[IntentionConflict, ...]
    fingerprint: str
