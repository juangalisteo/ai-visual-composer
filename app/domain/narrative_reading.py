from dataclasses import dataclass, field
from enum import Enum


class NarrativeConfidence(str, Enum):
    EXPLICIT = "explicit"
    CONTEXTUAL = "contextual"
    INFERRED = "inferred"


@dataclass(frozen=True)
class NarrativeFacts:
    stated: tuple[str, ...] = field(default_factory=tuple)
    shown: tuple[str, ...] = field(default_factory=tuple)
    existing_elements: tuple[str, ...] = field(default_factory=tuple)
    conditions: tuple[str, ...] = field(default_factory=tuple)
    confidence: NarrativeConfidence = NarrativeConfidence.EXPLICIT


@dataclass(frozen=True)
class NarrativeEvent:
    action: str = ""
    subject: str = ""
    object: str = ""
    initial_state: str = ""
    final_state: str = ""
    environment: str = ""
    time_context: str = ""
    key_objects: tuple[str, ...] = field(default_factory=tuple)
    spatial_relationships: tuple[str, ...] = field(default_factory=tuple)
    continuity_links: tuple[str, ...] = field(default_factory=tuple)
    abstract_source: str = ""
    visual_constraints: tuple[str, ...] = field(default_factory=tuple)
    visual_truth_status: str = ""
    source_model: str = ""
    confidence: NarrativeConfidence = NarrativeConfidence.EXPLICIT


@dataclass(frozen=True)
class NarrativeContext:
    previous_relation: str = ""
    next_relation: str = ""
    known_context: str = ""
    continuity: str = ""
    confidence: NarrativeConfidence = NarrativeConfidence.EXPLICIT


@dataclass(frozen=True)
class NarrativeChange:
    changes: tuple[str, ...] = field(default_factory=tuple)
    remains: tuple[str, ...] = field(default_factory=tuple)
    change_type: str = ""
    affected_entity: str = ""
    confidence: NarrativeConfidence = NarrativeConfidence.EXPLICIT


@dataclass(frozen=True)
class NarrativeFunction:
    primary: str = ""
    secondary: tuple[str, ...] = field(default_factory=tuple)
    structural_role: str = ""
    confidence: NarrativeConfidence = NarrativeConfidence.EXPLICIT


@dataclass(frozen=True)
class NarrativeEntities:
    characters: tuple[str, ...] = field(default_factory=tuple)
    objects: tuple[str, ...] = field(default_factory=tuple)
    places: tuple[str, ...] = field(default_factory=tuple)
    personified_concepts: tuple[str, ...] = field(default_factory=tuple)
    confidence: NarrativeConfidence = NarrativeConfidence.EXPLICIT


@dataclass(frozen=True)
class NarrativeRelations:
    relations: tuple[str, ...] = field(default_factory=tuple)
    confidence: NarrativeConfidence = NarrativeConfidence.EXPLICIT


@dataclass(frozen=True)
class NarrativeConflict:
    conflict_type: str = ""
    description: str = ""
    tension: str = ""
    confidence: NarrativeConfidence = NarrativeConfidence.EXPLICIT


@dataclass(frozen=True)
class NarrativeConcepts:
    explicit: tuple[str, ...] = field(default_factory=tuple)
    contextual: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ExplicitSymbols:
    symbols: tuple[str, ...] = field(default_factory=tuple)
    confidence: NarrativeConfidence = NarrativeConfidence.EXPLICIT


@dataclass(frozen=True)
class NarrativeContinuity:
    continues: tuple[str, ...] = field(default_factory=tuple)
    prepares: tuple[str, ...] = field(default_factory=tuple)
    consequences: tuple[str, ...] = field(default_factory=tuple)
    contrasts: tuple[str, ...] = field(default_factory=tuple)
    resolves: tuple[str, ...] = field(default_factory=tuple)
    resumes: tuple[str, ...] = field(default_factory=tuple)
    confidence: NarrativeConfidence = NarrativeConfidence.CONTEXTUAL


@dataclass(frozen=True)
class NarrativeReading:
    facts: NarrativeFacts = field(default_factory=NarrativeFacts)
    event: NarrativeEvent = field(default_factory=NarrativeEvent)
    context: NarrativeContext = field(default_factory=NarrativeContext)
    change: NarrativeChange = field(default_factory=NarrativeChange)
    function: NarrativeFunction = field(default_factory=NarrativeFunction)
    entities: NarrativeEntities = field(default_factory=NarrativeEntities)
    relations: NarrativeRelations = field(default_factory=NarrativeRelations)
    conflict: NarrativeConflict = field(default_factory=NarrativeConflict)
    concepts: NarrativeConcepts = field(default_factory=NarrativeConcepts)
    explicit_symbols: ExplicitSymbols = field(default_factory=ExplicitSymbols)
    continuity: NarrativeContinuity = field(default_factory=NarrativeContinuity)
