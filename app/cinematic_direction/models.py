from dataclasses import dataclass, field

from app.color_direction import ColorDirection
from app.composition_direction import CompositionDirection
from app.continuity_direction import ContinuityDirection
from app.lighting_direction import LightingDirection
from app.movement_direction import MovementDirection
from app.photography_direction import PhotographyDirection


@dataclass(frozen=True)
class CinematicDirectionComponentTrace:
    name: str
    present: bool
    version: str = ""
    fingerprint: str = ""


@dataclass(frozen=True)
class CinematicDirectionSetTrace:
    components: tuple[CinematicDirectionComponentTrace, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CinematicDirectionSet:
    photography: PhotographyDirection | None = None
    lighting: LightingDirection | None = None
    composition: CompositionDirection | None = None
    color: ColorDirection | None = None
    movement: MovementDirection | None = None
    continuity: ContinuityDirection | None = None
    schema_version: str = "1.0.0"
    version: str = "1.0.0"
    trace: CinematicDirectionSetTrace = field(default_factory=CinematicDirectionSetTrace)
    fingerprint: str = ""
