from app.modules.video_component.models import (
    MinimalVisualContext,
    MotionIntent,
)


class MotionIntentBuilder:

    def build(
        self,
        visual_context: MinimalVisualContext,
        storyboard_scene=None
    ) -> MotionIntent:
        constraints = (
            visual_context.stability_constraints
            + (
                "preserve_original_lighting",
                "preserve_original_framing",
            )
            + _storyboard_preservation_constraints(
                storyboard_scene
            )
        )

        return MotionIntent(
            source="minimal_source_image_context",
            camera_motion=(
                "slow subtle cinematic camera drift"
            ),
            motion_intensity="subtle",
            stability="high",
            temporal_rhythm="slow and steady",
            preservation_constraints=constraints,
            avoidance_constraints=(
                "no abrupt motion",
                "no invented action",
                "no new subjects",
                "no geometry deformation",
                "no identity change",
            )
            + _storyboard_avoidance_constraints(
                storyboard_scene
            ),
            source_trace=(
                "MinimalVisualContext.source_path",
                "MinimalVisualContext.width",
                "MinimalVisualContext.height",
                "MinimalVisualContext.aspect_ratio",
                "MinimalVisualContext.orientation",
                "MinimalVisualContext.image_format",
                "MinimalVisualContext.stability_constraints",
            )
            + _storyboard_source_trace(
                storyboard_scene
            )
        )


def _storyboard_preservation_constraints(
    storyboard_scene
):
    if storyboard_scene is None:
        return ()

    constraints = [
        "contextual_environment_motion_only",
        "minimal_natural_subject_motion",
    ]
    for field_name in (
        "visible_subject",
        "visible_action",
        "visible_environment",
        "filmable_interpretation",
        "time_context",
    ):
        value = str(
            getattr(
                storyboard_scene,
                field_name,
                ""
            )
        ).strip()
        if value:
            constraints.append(
                f"preserve_storyboard_{field_name}: {value}"
            )

    for field_name in (
        "key_objects",
        "spatial_relationships",
        "continuity_links",
        "visual_constraints",
    ):
        values = tuple(
            getattr(
                storyboard_scene,
                field_name,
                ()
            )
        )
        if values:
            constraints.append(
                "preserve_storyboard_"
                f"{field_name}: "
                + "; ".join(
                    str(
                        value
                    ).strip()
                    for value in values
                    if str(
                        value
                    ).strip()
                )
            )

    return tuple(
        constraint
        for constraint in constraints
        if constraint
    )


def _storyboard_avoidance_constraints(
    storyboard_scene
):
    if storyboard_scene is None:
        return ()

    return (
        "no action beyond StoryboardScene.visible_action",
        "no subject beyond StoryboardScene.visible_subject",
        "no environment beyond StoryboardScene.visible_environment",
    )


def _storyboard_source_trace(
    storyboard_scene
):
    if storyboard_scene is None:
        return ()

    return (
        "StoryboardScene.scene_number",
        "StoryboardScene.visible_subject",
        "StoryboardScene.visible_action",
        "StoryboardScene.visible_environment",
        "StoryboardScene.filmable_interpretation",
        "StoryboardScene.key_objects",
        "StoryboardScene.spatial_relationships",
        "StoryboardScene.continuity_links",
        "StoryboardScene.visual_constraints",
    )
