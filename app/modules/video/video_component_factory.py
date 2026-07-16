from app.modules.video.motion.motion_builder import MotionBuilder
from app.modules.video.overlays.overlay_builder import OverlayBuilder
from app.modules.video.transitions.transition_builder import (
    TransitionBuilder
)
from app.modules.video.video_build_context import VideoBuildComponents
from app.modules.video.visual_effects.visual_effect_builder import (
    VisualEffectBuilder
)


class VideoComponentFactory:

    def create(
        self,
        video_config
    ):
        motion_builder = MotionBuilder(
            video_config.motion
        )

        transition_builder = (
            TransitionBuilder()
        )

        overlay_builder = (
            OverlayBuilder(
                video_config.overlays
            )
        )

        visual_effect_builder = (
            VisualEffectBuilder(
                video_config.visual_effects
            )
        )

        overlay_builder.reset()

        visual_effect_builder.reset()

        return VideoBuildComponents(
            motion_builder=motion_builder,
            transition_builder=transition_builder,
            overlay_builder=overlay_builder,
            visual_effect_builder=visual_effect_builder
        )
