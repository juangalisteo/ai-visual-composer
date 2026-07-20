from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.domain import NarrativeReading


@dataclass(frozen=True)
class NarrativeReadingReference:
    id: str
    version: str = ""


@dataclass(frozen=True)
class NarrativeReadingMetadata:
    owner: str = ""
    status: str = ""
    source: str = ""
    description: str = ""


@dataclass(frozen=True)
class NarrativeReadingDocument:
    schema_version: int
    id: str
    version: str
    type: str
    title: str
    extends: NarrativeReadingReference | None
    metadata: NarrativeReadingMetadata
    trace: dict[str, Any]
    narrative_reading: dict[str, Any]
    source_path: Path


@dataclass(frozen=True)
class NarrativeFieldOrigin:
    path: str
    source_id: str
    source_version: str
    confidence: str = ""
    action: str = "set"


@dataclass(frozen=True)
class NarrativeTrace:
    inheritance_chain: tuple[str, ...]
    references: tuple[str, ...] = field(default_factory=tuple)
    field_origins: tuple[NarrativeFieldOrigin, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class EffectiveNarrativeReading:
    narrative_reading: NarrativeReading
    source_id: str
    source_version: str
    schema_version: int
    inheritance_chain: tuple[str, ...]
    trace: NarrativeTrace
    fingerprint: str
