import unittest
from pathlib import Path

from app.domain import StoryboardScene
from app.modules.video_component import (
    MinimalVisualContext,
    MotionIntentBuilder,
)


class MotionIntentBuilderTest(unittest.TestCase):

    def _context(self):
        return MinimalVisualContext(
            source_path=Path("tests/fixtures/video/source.png"),
            width=1920,
            height=1080,
            aspect_ratio="16:9",
            orientation="landscape",
            image_format="PNG",
            stability_constraints=(
                "preserve_source_composition",
                "preserve_source_geometry",
            )
        )

    def test_builds_conservative_motion_intent(self):
        motion = MotionIntentBuilder().build(
            self._context()
        )

        self.assertEqual(
            "subtle",
            motion.motion_intensity
        )
        self.assertEqual(
            "high",
            motion.stability
        )
        self.assertIn(
            "no invented action",
            motion.avoidance_constraints
        )
        self.assertIn(
            "preserve_original_framing",
            motion.preservation_constraints
        )

    def test_motion_intent_is_deterministic(self):
        builder = MotionIntentBuilder()
        first = builder.build(
            self._context()
        )
        second = builder.build(
            self._context()
        )

        self.assertEqual(
            first,
            second
        )

    def test_motion_intent_does_not_invent_semantic_content(self):
        motion = MotionIntentBuilder().build(
            self._context()
        )
        serialized = " ".join(
            (
                motion.camera_motion,
                motion.motion_intensity,
                motion.stability,
                motion.temporal_rhythm,
                " ".join(
                    motion.preservation_constraints
                ),
                " ".join(
                    motion.avoidance_constraints
                ),
            )
        ).lower()

        for forbidden in (
            "person",
            "lamp",
            "face",
            "breathing",
            "flicker",
        ):
            self.assertNotIn(
                forbidden,
                serialized
            )

    def test_storyboard_scene_adds_preservation_trace(self):
        storyboard_scene = StoryboardScene(
            scene_number=1,
            text="Nikola Tesla en su laboratorio.",
            visible_subject="Nikola Tesla",
            visible_action="sentado junto a una lampara iluminada",
            visible_environment="laboratorio electrico",
            key_objects=(
                "lampara",
                "bobina",
            ),
            filmable_interpretation="escena cinematica realista",
        )

        motion = MotionIntentBuilder().build(
            self._context(),
            storyboard_scene=storyboard_scene
        )

        self.assertIn(
            (
                "preserve_storyboard_visible_subject: "
                "Nikola Tesla"
            ),
            motion.preservation_constraints
        )
        self.assertIn(
            "StoryboardScene.visible_subject",
            motion.source_trace
        )
        self.assertIn(
            "no subject beyond StoryboardScene.visible_subject",
            motion.avoidance_constraints
        )


if __name__ == "__main__":
    unittest.main()
