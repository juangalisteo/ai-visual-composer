"""Motion of each WAN clip, decided from its storyboard scene.

Every text lives in ``prompts/video/``: ``motion.json`` holds the texts of
each motion level, the keywords that choose the level and the fixed
preservation and avoidance constraints; ``motion_storyboard_field.txt`` says
how each storyboard field is preserved (``{campo}``, ``{valor}``). A missing
file, text or marker is a CONFIG error.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from app.modules.video_component.models import (
    MinimalVisualContext,
    MotionIntent,
)
from app.shared.prompt_library import (
    PromptLibrary,
    require_prompt_text,
    require_prompt_texts,
)


# Files of prompts/ with the motion texts.
MOTION_TEXTS = "video/motion.json"
STORYBOARD_FIELD_TEMPLATE = "video/motion_storyboard_field.txt"

# Closed vocabulary of the motion levels; each one declares its texts under
# ``levels`` in motion.json.
SUBTLE = "subtle"
NORMAL = "normal"
INTENSE = "intense"
MOTION_LEVELS = (SUBTLE, NORMAL, INTENSE)
LEVEL_TEXTS = (
    "camera_motion",
    "motion_intensity",
    "stability",
    "temporal_rhythm",
)


@dataclass(frozen=True)
class MotionPromptTexts:
    """Texts of prompts/video/motion.json."""

    # Motion level → its texts (one per LEVEL_TEXTS name).
    levels: Mapping[str, Mapping[str, str]]
    intense_action_cues: tuple[str, ...]
    static_action_cues: tuple[str, ...]
    static_visual_constraint_cues: tuple[str, ...]
    preservation_constraints: tuple[str, ...]
    storyboard_preservation_constraints: tuple[str, ...]
    avoidance_constraints: tuple[str, ...]
    storyboard_avoidance_constraints: tuple[str, ...]

    @classmethod
    def load(cls, prompts=None):
        prompts = prompts or PromptLibrary()
        document = prompts.mapping(MOTION_TEXTS)

        def texts(key):
            return require_prompt_texts(document, key, prompts, MOTION_TEXTS)

        return cls(
            levels=_level_texts(document, prompts),
            intense_action_cues=texts("intense_action_cues"),
            static_action_cues=texts("static_action_cues"),
            static_visual_constraint_cues=texts(
                "static_visual_constraint_cues"
            ),
            preservation_constraints=texts("preservation_constraints"),
            storyboard_preservation_constraints=texts(
                "storyboard_preservation_constraints"
            ),
            avoidance_constraints=texts("avoidance_constraints"),
            storyboard_avoidance_constraints=texts(
                "storyboard_avoidance_constraints"
            ),
        )


def _level_texts(document, prompts):
    levels = document.get("levels")
    if not isinstance(levels, dict):
        levels = {}
    result = {}
    for level in MOTION_LEVELS:
        declared = levels.get(level)
        if not isinstance(declared, dict):
            declared = {}
        result[level] = MappingProxyType({
            name: require_prompt_text(
                {f"levels.{level}.{name}": declared.get(name)},
                f"levels.{level}.{name}",
                prompts,
                MOTION_TEXTS,
            )
            for name in LEVEL_TEXTS
        })
    return MappingProxyType(result)


class MotionIntentBuilder:
    """The texts are read from prompts/ the first time they are needed."""

    def __init__(
        self,
        texts: MotionPromptTexts | None = None,
        prompts=None,
    ):
        self.prompts = prompts or PromptLibrary()
        self._texts = texts

    @property
    def texts(self) -> MotionPromptTexts:
        if self._texts is None:
            self._texts = MotionPromptTexts.load(self.prompts)
        return self._texts

    def build(
        self,
        visual_context: MinimalVisualContext,
        storyboard_scene=None
    ) -> MotionIntent:
        texts = self.texts
        motion_level = _motion_level(
            storyboard_scene,
            texts
        )
        motion_policy = texts.levels[
            motion_level
        ]
        constraints = (
            visual_context.stability_constraints
            + texts.preservation_constraints
            + self._storyboard_preservation_constraints(
                storyboard_scene,
                texts
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
                texts.avoidance_constraints
                + _storyboard_avoidance_constraints(
                    storyboard_scene,
                    texts
                )
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
        self,
        storyboard_scene,
        texts
    ):
        if storyboard_scene is None:
            return ()

        constraints = list(
            texts.storyboard_preservation_constraints
        )
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
                    self._storyboard_field(
                        field_name,
                        value
                    )
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
                    self._storyboard_field(
                        field_name,
                        "; ".join(
                            str(
                                value
                            ).strip()
                            for value in values
                            if str(
                                value
                            ).strip()
                        )
                    )
                )

        return tuple(
            constraint
            for constraint in constraints
            if constraint
        )

    def _storyboard_field(
        self,
        field_name,
        value
    ):
        return self.prompts.render(
            STORYBOARD_FIELD_TEMPLATE,
            campo=field_name,
            valor=value,
        )


def _motion_level(
    storyboard_scene,
    texts
):
    if storyboard_scene is None:
        return SUBTLE

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
        storyboard_scene,
        texts.static_visual_constraint_cues
    ) or _contains_any(
        motion_context,
        texts.static_action_cues
    ):
        return SUBTLE

    if _contains_any(
        motion_context,
        texts.intense_action_cues
    ):
        return INTENSE

    if action:
        return NORMAL

    return SUBTLE


def _has_static_visual_constraint(
    storyboard_scene,
    cues
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
        cues
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


def _storyboard_avoidance_constraints(
    storyboard_scene,
    texts
):
    if storyboard_scene is None:
        return ()

    return texts.storyboard_avoidance_constraints


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
