from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.domain import VisualBible


@dataclass(frozen=True)
class VisualBibleReference:
    id: str
    version: str = ""


@dataclass(frozen=True)
class VisualBibleCompositionReference:
    reference: VisualBibleReference
    role: str


@dataclass(frozen=True)
class VisualBibleMetadata:
    owner: str = ""
    status: str = ""
    description: str = ""


@dataclass(frozen=True)
class InheritancePolicy:
    locked: tuple[str, ...] = field(default_factory=tuple)
    appendable: tuple[str, ...] = field(default_factory=tuple)
    overridable: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class VisualBibleDocument:
    schema_version: int
    id: str
    version: str
    type: str
    title: str
    extends: VisualBibleReference | None
    composes: tuple[VisualBibleCompositionReference, ...]
    metadata: VisualBibleMetadata
    inheritance_policy: InheritancePolicy
    visual_bible: dict[str, Any]
    source_path: Path


@dataclass(frozen=True)
class VisualBibleFieldOrigin:
    path: str
    source_id: str
    source_version: str
    action: str


@dataclass(frozen=True)
class VisualBibleTrace:
    inheritance_chain: tuple[str, ...]
    composed_layers: tuple[str, ...] = field(default_factory=tuple)
    field_origins: tuple[VisualBibleFieldOrigin, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class EffectiveVisualBible:
    visual_bible: VisualBible
    source_id: str
    source_version: str
    schema_version: int
    inheritance_chain: tuple[str, ...]
    composed_layers: tuple[str, ...]
    trace: VisualBibleTrace
    fingerprint: str
