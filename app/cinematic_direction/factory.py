import hashlib
import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from app.cinematic_direction.models import (
    CinematicDirectionComponentTrace,
    CinematicDirectionSet,
    CinematicDirectionSetTrace,
)
from app.color_direction import ColorDirection
from app.composition_direction import CompositionDirection
from app.continuity_direction import ContinuityDirection
from app.lighting_direction import LightingDirection
from app.movement_direction import MovementDirection
from app.photography_direction import PhotographyDirection


def create_cinematic_direction_set(
    *,
    photography: PhotographyDirection | None = None,
    lighting: LightingDirection | None = None,
    composition: CompositionDirection | None = None,
    color: ColorDirection | None = None,
    movement: MovementDirection | None = None,
    continuity: ContinuityDirection | None = None,
    schema_version: str = "1.0.0",
    version: str = "1.0.0",
) -> CinematicDirectionSet:
    trace = CinematicDirectionSetTrace(
        components=(
            _component_trace(
                "photography",
                photography
            ),
            _component_trace(
                "lighting",
                lighting
            ),
            _component_trace(
                "composition",
                composition
            ),
            _component_trace(
                "color",
                color
            ),
            _component_trace(
                "movement",
                movement
            ),
            _component_trace(
                "continuity",
                continuity
            ),
        )
    )
    direction_set = CinematicDirectionSet(
        photography=photography,
        lighting=lighting,
        composition=composition,
        color=color,
        movement=movement,
        continuity=continuity,
        schema_version=schema_version,
        version=version,
        trace=trace,
    )
    return CinematicDirectionSet(
        photography=photography,
        lighting=lighting,
        composition=composition,
        color=color,
        movement=movement,
        continuity=continuity,
        schema_version=schema_version,
        version=version,
        trace=trace,
        fingerprint=_fingerprint(
            direction_set
        ),
    )


def _component_trace(
    name: str,
    direction: Any
) -> CinematicDirectionComponentTrace:
    if direction is None:
        return CinematicDirectionComponentTrace(
            name=name,
            present=False,
        )
    return CinematicDirectionComponentTrace(
        name=name,
        present=True,
        version=getattr(
            direction,
            "source_version",
            ""
        ),
        fingerprint=getattr(
            direction,
            "fingerprint",
            ""
        ),
    )


def _fingerprint(
    direction_set: CinematicDirectionSet
) -> str:
    canonical = {
        "CinematicDirectionSet": {
            "schema_version": direction_set.schema_version,
            "version": direction_set.version,
            "components": [
                _canonical_mapping(
                    component
                )
                for component in direction_set.trace.components
            ],
        }
    }
    return hashlib.sha256(
        json.dumps(
            canonical,
            sort_keys=True,
            separators=(
                ",",
                ":"
            )
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def _canonical_mapping(
    value: Any
) -> Any:
    if isinstance(
        value,
        Enum
    ):
        return value.value
    if is_dataclass(
        value
    ):
        return {
            key: _canonical_mapping(
                item
            )
            for key, item in asdict(
                value
            ).items()
        }
    if isinstance(
        value,
        dict
    ):
        return {
            key: _canonical_mapping(
                item
            )
            for key, item in sorted(
                value.items()
            )
        }
    if isinstance(
        value,
        (
            tuple,
            list,
        )
    ):
        return [
            _canonical_mapping(
                item
            )
            for item in value
        ]
    return value
