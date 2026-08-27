from app.modules.video_component.models import (
    MotionIntent,
    VideoPromptPlan,
)


class VideoPromptTranslator:

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

        prompt = (
            "Create a short image-to-video clip with "
            f"{motion_intent.camera_motion}. "
            f"Motion intensity: {motion_intent.motion_intensity}. "
            f"Temporal rhythm: {motion_intent.temporal_rhythm}. "
            f"Stability: {motion_intent.stability}. "
            "Preserve the source image faithfully. "
            f"Preservation constraints: {preservation}."
        )

        negative_prompt = (
            "Avoid abrupt motion, invented actions, new subjects, "
            "identity changes, geometry deformation, subject morphing, "
            f"and unstable composition. Avoidance constraints: {avoidance}."
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
