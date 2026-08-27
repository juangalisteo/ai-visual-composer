import unittest
from pathlib import Path

from app.modules.video_component import (
    MinimalVisualContext,
    MotionIntent,
    VideoPreparationResult,
    VideoPromptPlan,
)


class VideoComponentContractsTest(unittest.TestCase):

    def test_minimal_visual_context_accepts_valid_structure(self):
        context = MinimalVisualContext(
            source_path=Path("tests/fixtures/video/source.png"),
            width=1920,
            height=1080,
            aspect_ratio="16:9",
            orientation="landscape",
            image_format="png",
            stability_constraints=(
                "preserve_source_composition",
            )
        )

        self.assertEqual(
            "PNG",
            context.image_format
        )
        self.assertEqual(
            (
                "preserve_source_composition",
            ),
            context.stability_constraints
        )

    def test_minimal_visual_context_rejects_invalid_dimensions(self):
        with self.assertRaises(
            ValueError
        ):
            MinimalVisualContext(
                source_path=Path("source.png"),
                width=0,
                height=1080,
                aspect_ratio="0:1080",
                orientation="landscape",
                image_format="PNG"
            )

    def test_motion_intent_requires_temporal_information(self):
        with self.assertRaises(
            ValueError
        ):
            MotionIntent(
                source="",
                camera_motion="slow",
                motion_intensity="subtle",
                stability="high",
                temporal_rhythm="slow"
            )

    def test_video_preparation_result_remains_dry_run(self):
        context = MinimalVisualContext(
            source_path=Path("tests/fixtures/video/source.png"),
            width=1080,
            height=1080,
            aspect_ratio="1:1",
            orientation="square",
            image_format="PNG"
        )
        motion = MotionIntent(
            source="minimal_source_image_context",
            camera_motion="slow subtle cinematic camera drift",
            motion_intensity="subtle",
            stability="high",
            temporal_rhythm="slow and steady"
        )
        prompt = VideoPromptPlan(
            prompt="Create a stable clip.",
            negative_prompt="Avoid deformation.",
            motion_summary="subtle motion"
        )

        result = VideoPreparationResult(
            visual_context=context,
            motion_intent=motion,
            prompt_plan=prompt
        )

        self.assertEqual(
            "prepared",
            result.status
        )
        self.assertFalse(
            result.backend_required
        )


if __name__ == "__main__":
    unittest.main()
