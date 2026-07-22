from app.cinematic_direction.factory import create_cinematic_direction_set
from app.cinematic_direction.models import CinematicDirectionSet
from app.color_direction import ColorDirector
from app.composition_direction import CompositionDirector
from app.continuity_direction import ContinuityDirector
from app.lighting_direction import LightingDirector
from app.movement_direction import MovementDirector
from app.photography_direction import PhotographyDirector
from app.visual_direction import EffectiveVisualBrief


class CinematicDirectionOrchestrator:
    def __init__(
        self,
        photography_director: PhotographyDirector | None = None,
        lighting_director: LightingDirector | None = None,
        composition_director: CompositionDirector | None = None,
        color_director: ColorDirector | None = None,
        movement_director: MovementDirector | None = None,
        continuity_director: ContinuityDirector | None = None,
    ) -> None:
        self.photography_director = photography_director or PhotographyDirector()
        self.lighting_director = lighting_director or LightingDirector()
        self.composition_director = composition_director or CompositionDirector()
        self.color_director = color_director or ColorDirector()
        self.movement_director = movement_director or MovementDirector()
        self.continuity_director = continuity_director or ContinuityDirector()

    def resolve(
        self,
        effective_visual_brief: EffectiveVisualBrief
    ) -> CinematicDirectionSet:
        photography = self.photography_director.resolve(
            effective_visual_brief
        )
        lighting = self.lighting_director.resolve(
            effective_visual_brief
        )
        composition = self.composition_director.resolve(
            effective_visual_brief
        )
        color = self.color_director.resolve(
            effective_visual_brief
        )
        movement = self.movement_director.resolve(
            effective_visual_brief
        )
        continuity = self.continuity_director.resolve(
            effective_visual_brief
        )
        return create_cinematic_direction_set(
            photography=photography,
            lighting=lighting,
            composition=composition,
            color=color,
            movement=movement,
            continuity=continuity,
        )
