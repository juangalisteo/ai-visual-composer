from dataclasses import dataclass, field
from enum import Enum


class IntentionLevel(str, Enum):
    WORK = "work"
    SEQUENCE = "sequence"
    SCENE = "scene"
    BEAT = "beat"


@dataclass(frozen=True)
class CommunicativeIntention:
    understanding: str = ""
    key_message: str = ""
    emphasis: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class EmotionalIntention:
    desired_effect: str = ""
    emotional_quality: str = ""
    intensity: str = ""


@dataclass(frozen=True)
class CognitiveIntention:
    question: str = ""
    operation: str = ""
    insight: str = ""


@dataclass(frozen=True)
class NarrativeIntention:
    purpose: str = ""
    function: str = ""
    arc_relation: str = ""


@dataclass(frozen=True)
class SymbolicIntention:
    meaning: str = ""
    allowed_readings: tuple[str, ...] = field(default_factory=tuple)
    ambiguity: str = ""


@dataclass(frozen=True)
class TransformativeIntention:
    before: str = ""
    after: str = ""
    shift: str = ""


@dataclass(frozen=True)
class AttentionalIntention:
    focus: str = ""
    priority: str = ""
    de_emphasize: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class NegativeIntention:
    avoid_interpretations: tuple[str, ...] = field(default_factory=tuple)
    avoid_effects: tuple[str, ...] = field(default_factory=tuple)
    avoid_meaning_drift: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Intention:
    communicative: CommunicativeIntention | None = None
    emotional: EmotionalIntention | None = None
    cognitive: CognitiveIntention | None = None
    narrative: NarrativeIntention | None = None
    symbolic: SymbolicIntention | None = None
    transformative: TransformativeIntention | None = None
    attentional: AttentionalIntention | None = None
    negative: NegativeIntention | None = None
