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
        motion_level = _motion_level(
            storyboard_scene
        )
        motion_policy = _motion_policy(
            motion_level
        )
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
            motion_level=motion_level,
            camera_motion=motion_policy["camera_motion"],
            motion_intensity=motion_policy["motion_intensity"],
            stability=motion_policy["stability"],
            temporal_rhythm=motion_policy["temporal_rhythm"],
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


MOTION_POLICIES = {
    "subtle": {
        "camera_motion": "slow micro camera drift",
        "motion_intensity": "subtle",
        "stability": "very high",
        "temporal_rhythm": "slow and steady",
    },
    "normal": {
        "camera_motion": "gentle slow push-in",
        "motion_intensity": "moderate",
        "stability": "high",
        "temporal_rhythm": "natural and controlled",
    },
    "intense": {
        "camera_motion": "controlled short tracking move",
        "motion_intensity": "strong but controlled",
        "stability": "high",
        "temporal_rhythm": "dynamic but stable",
    },
}


INTENSE_ACTION_CUES = (
    "runs",
    "running",
    "sprints",
    "sprinting",
    "jumps",
    "jumping",
    "races",
    "racing",
    "falls",
    "falling",
    "fights",
    "fighting",
    "throws",
    "throwing",
    "flees",
    "chases",
    "dives",
    "explodes",
    "collapses",
    "corre",
    "corriendo",
    "salta",
    "saltando",
    "cae",
    "cayendo",
    "lucha",
    "luchando",
    "lanza",
    "lanzando",
    "huye",
    "persigue",
    "se zambulle",
    "explota",
    "colapsa",
)


STATIC_ACTION_CUES = (
    "sits",
    "sitting",
    "seated",
    "stands still",
    "standing still",
    "contemplates",
    "contemplating",
    "rests",
    "resting",
    "observes",
    "waiting",
    "waits",
    "still life",
    "sentado",
    "sentada",
    "contempla",
    "descansa",
    "observa",
    "espera",
    "quieto",
    "quieta",
    "estático",
    "estática",
)


STATIC_VISUAL_CONSTRAINT_CUES = (
    "no motion",
    "no movement",
    "static composition",
    "sin movimiento",
    "composición estática",
)


def _motion_level(
    storyboard_scene
):
    if storyboard_scene is None:
        return "subtle"

    action = _scene_text(
        storyboard_scene,
        "visible_action"
    )
    filmable_interpretation = _scene_text(
        storyboard_scene,
        "filmable_interpretation"
    )
    motion_context = " ".join(
        (
            action,
            filmable_interpretation,
        )
    ).lower()

    if _has_static_visual_constraint(
        storyboard_scene
    ) or _contains_any(
        motion_context,
        STATIC_ACTION_CUES
    ):
        return "subtle"

    if _contains_any(
        motion_context,
        INTENSE_ACTION_CUES
    ):
        return "intense"

    if action:
        return "normal"

    return "subtle"


def _motion_policy(
    motion_level
):
    return MOTION_POLICIES[
        motion_level
    ]


def _has_static_visual_constraint(
    storyboard_scene
):
    constraints = " ".join(
        str(value).strip().lower()
        for value in getattr(
            storyboard_scene,
            "visual_constraints",
            (),
        )
        if str(value).strip()
    )
    return _contains_any(
        constraints,
        STATIC_VISUAL_CONSTRAINT_CUES
    )


def _scene_text(
    storyboard_scene,
    field_name
):
    return str(
        getattr(
            storyboard_scene,
            field_name,
            ""
        )
        or ""
    ).strip()


def _contains_any(
    value,
    cues
):
    return any(
        cue in value
        for cue in cues
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
