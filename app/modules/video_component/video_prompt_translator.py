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
            "Keep the source image composition locked across all frames. "
            "Preserve the same subject identity, face, clothing, anatomy, "
            "key objects and background layout. Animate only the declared "
            "motion. Use one stable camera move consistent with it; no "
            "additional reframing, zoom, orbit, or camera shake. "
            f"Preservation constraints: {preservation}."
        )

        negative_prompt = (
            "Avoid abrupt motion, invented actions, new subjects, "
            "identity changes, geometry deformation, subject morphing, "
            "unstable composition, temporal flicker, face or body distortion, "
            "duplicate limbs, object mutation, warped geometry, sudden scene "
            "changes, camera shake, and unintended reframing. Avoidance "
            f"constraints: {avoidance}."
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
