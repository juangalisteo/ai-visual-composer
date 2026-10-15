import unittest
from pathlib import Path

from app.modules.video_component import (
    BackendVideoPrompt,
    MinimalVisualContext,
    MotionIntent,
    VideoPreparationResult,
    VideoPromptPlan,
    WanIntermediateOutput,
)


class BackendVideoPromptTest(unittest.TestCase):

    def test_builds_from_video_preparation_result(self):
        preparation = VideoPreparationResult(
            visual_context=MinimalVisualContext(
                source_path=Path("tests/fixtures/video/source.png"),
                width=1024,
                height=1024,
                aspect_ratio="1:1",
                orientation="square",
                image_format="PNG",
            ),
            motion_intent=MotionIntent(
                source="minimal_source_image_context",
                camera_motion="slow subtle cinematic camera drift",
                motion_intensity="subtle",
                stability="high",
                temporal_rhythm="slow and steady",
                motion_level="normal",
                preservation_constraints=(
                    "preserve source composition",
                ),
                avoidance_constraints=(
                    "avoid abrupt motion",
                ),
                source_trace=(
                    "MinimalVisualContext.width",
                ),
            ),
            prompt_plan=VideoPromptPlan(
                prompt="Create a cinematic I2V clip.",
                negative_prompt="Avoid deformation.",
                motion_summary="slow camera drift",
                constraints=(
                    "preserve source composition",
                ),
                source_trace=(
                    "MinimalVisualContext.width",
                    "MotionIntent.camera_motion",
                ),
            ),
        )

        prompt = BackendVideoPrompt.from_preparation(
            preparation,
            seed=42,
            frames=17,
            fps=8.0,
            generation_width=384,
            generation_height=672,
            target_width=1080,
            target_height=1920,
            steps=12,
            cfg=5.0,
            sampler="uni_pc",
            scheduler="simple",
            intermediate_output="lossless_ffv1",
            profile_name="Instagram",
        )

        self.assertEqual(
            Path("tests/fixtures/video/source.png"),
            prompt.source_image
        )
        self.assertEqual(
            "Create a cinematic I2V clip.",
            prompt.positive_prompt
        )
        self.assertEqual(
            "Avoid deformation.",
            prompt.negative_prompt
        )
        self.assertEqual(
            "slow camera drift",
            prompt.motion_summary
        )
        self.assertEqual(
            42,
            prompt.seed
        )
        self.assertEqual(
            384,
            prompt.generation_width
        )
        self.assertEqual(
            672,
            prompt.generation_height
        )
        self.assertEqual(
            1080,
            prompt.target_width
        )
        self.assertEqual(
            1920,
            prompt.target_height
        )
        self.assertEqual(
            12,
            prompt.steps
        )
        self.assertEqual(
            5.0,
            prompt.cfg
        )
        self.assertEqual(
            "uni_pc",
            prompt.sampler
        )
        self.assertEqual(
            "simple",
            prompt.scheduler
        )
        self.assertEqual(
            WanIntermediateOutput.LOSSLESS_FFV1,
            prompt.intermediate_output,
        )
        self.assertEqual(
            "Instagram",
            prompt.profile_name
        )
        self.assertEqual(
            (
                "preserve source composition",
            ),
            prompt.constraints
        )
        self.assertEqual(
            "slow subtle cinematic camera drift",
            prompt.camera_motion
        )
        self.assertEqual(
            "subtle",
            prompt.motion_intensity
        )
        self.assertEqual(
            "high",
            prompt.stability
        )
        self.assertEqual(
            "slow and steady",
            prompt.temporal_rhythm
        )
        self.assertEqual(
            "normal",
            prompt.motion_level
        )
        self.assertEqual(
            (
                "preserve source composition",
            ),
            prompt.preservation_constraints
        )
        self.assertEqual(
            (
                "avoid abrupt motion",
            ),
            prompt.avoidance_constraints
        )
        self.assertEqual(
            (
                "MinimalVisualContext.width",
                "MotionIntent.camera_motion",
            ),
            prompt.source_trace
        )

    def test_rejects_invalid_generation_parameters(self):
        with self.assertRaises(
            ValueError
        ):
            BackendVideoPrompt(
                source_image=Path("source.png"),
                positive_prompt="Prompt",
                negative_prompt="",
                motion_summary="motion",
                frames=0,
            )

    def test_defaults_to_legacy_savevideo_h264_intermediate_output(self):
        prompt = BackendVideoPrompt(
            source_image=Path("source.png"),
            positive_prompt="Prompt",
            negative_prompt="",
            motion_summary="motion",
        )

        self.assertEqual(
            WanIntermediateOutput.SAVEVIDEO_H264,
            prompt.intermediate_output,
        )


if __name__ == "__main__":
    unittest.main()
