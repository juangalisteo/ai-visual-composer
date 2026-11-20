from app.modules.video_component.models import (
    MotionIntent,
    VideoPromptPlan,
)
from app.shared.prompt_library import PromptLibrary


# Templates of prompts/ with the WAN prompt and its negative prompt.
WAN_PROMPT_TEMPLATE = "video/wan.txt"
WAN_NEGATIVE_TEMPLATE = "video/wan_negative.txt"


class VideoPromptTranslator:

    def __init__(self, prompts=None):
        self.prompts = prompts or PromptLibrary()

    def translate(
        self,
        motion_intent: MotionIntent
    ) -> VideoPromptPlan:
        preservation = self._join(
            motion_intent.preservation_constraints
        )
        avoidance = self._join(
            motion_intent.avoidance_constraints
        )

        prompt = self.prompts.render(
            WAN_PROMPT_TEMPLATE,
            movimiento_camara=motion_intent.camera_motion,
            intensidad=motion_intent.motion_intensity,
            ritmo=motion_intent.temporal_rhythm,
            estabilidad=motion_intent.stability,
            conservar=preservation,
        )

        negative_prompt = self.prompts.render(
            WAN_NEGATIVE_TEMPLATE,
            evitar=avoidance,
        )

        return VideoPromptPlan(
            prompt=prompt,
            negative_prompt=negative_prompt,
            motion_summary=(
                f"{motion_intent.motion_intensity} motion, "
                f"{motion_intent.stability} stability, "
                f"{motion_intent.temporal_rhythm} rhythm"
            ),
            constraints=(
                motion_intent.preservation_constraints
                + motion_intent.avoidance_constraints
            ),
            source_trace=(
                motion_intent.source_trace
                + (
                    "MotionIntent.camera_motion",
                    "MotionIntent.motion_intensity",
                    "MotionIntent.stability",
                    "MotionIntent.temporal_rhythm",
                    "MotionIntent.motion_level",
                    "MotionIntent.preservation_constraints",
                    "MotionIntent.avoidance_constraints",
                )
            )
        )

    def _join(
        self,
        values
    ):
        return ", ".join(
            str(value).strip()
            for value in values
            if str(value).strip()
        )
