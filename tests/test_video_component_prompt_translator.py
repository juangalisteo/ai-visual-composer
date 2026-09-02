import unittest

from app.modules.video_component import (
    MotionIntent,
    VideoPromptTranslator,
)


class VideoPromptTranslatorTest(unittest.TestCase):

    def _motion_intent(self):
        return MotionIntent(
            source="minimal_source_image_context",
            camera_motion="slow subtle cinematic camera drift",
            motion_intensity="subtle",
            stability="high",
            temporal_rhythm="slow and steady",
            preservation_constraints=(
                "preserve_source_composition",
                "preserve_original_lighting",
            ),
            avoidance_constraints=(
                "no abrupt motion",
                "no invented action",
            ),
            source_trace=(
                "MinimalVisualContext.width",
            )
        )

    def test_translates_motion_intent_to_video_prompt_plan(self):
        plan = VideoPromptTranslator().translate(
            self._motion_intent()
        )

        self.assertEqual(
            (
                "Create a short image-to-video clip with slow subtle "
                "cinematic camera drift. Motion intensity: subtle. "
                "Temporal rhythm: slow and steady. Stability: high. "
                "Preserve the source image faithfully. Keep the source "
                "image composition locked across all frames. Preserve the "
                "same subject identity, face, clothing, anatomy, key objects "
                "and background layout. Animate only the declared subtle "
                "motion; keep a single slow stable camera drift with no "
                "reframing, zoom, orbit or camera shake. Preservation "
                "constraints: preserve_source_composition, "
                "preserve_original_lighting."
            ),
            plan.prompt
        )
        self.assertEqual(
            (
                "Avoid abrupt motion, invented actions, new subjects, "
                "identity changes, geometry deformation, subject morphing, "
                "unstable composition, temporal flicker, face or body "
                "distortion, duplicate limbs, object mutation, warped "
                "geometry, sudden scene changes, camera shake, and unintended "
                "reframing. Avoidance constraints: no abrupt motion, no "
                "invented action."
            ),
            plan.negative_prompt
        )
        self.assertIn(
            "subtle motion",
            plan.motion_summary
        )

    def test_translation_is_deterministic(self):
        translator = VideoPromptTranslator()
        first = translator.translate(
            self._motion_intent()
        )
        second = translator.translate(
            self._motion_intent()
        )

        self.assertEqual(
            first,
            second
        )

    def test_translator_is_backend_neutral(self):
        plan = VideoPromptTranslator().translate(
            self._motion_intent()
        )
        serialized = (
            plan.prompt
            + plan.negative_prompt
        ).lower()

        for forbidden in (
            "comfyui",
            "wan",
            "workflow",
            "sampler",
            "scheduler",
            "cuda",
        ):
            self.assertNotIn(
                forbidden,
                serialized
            )


if __name__ == "__main__":
    unittest.main()
