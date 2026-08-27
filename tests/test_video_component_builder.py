import struct
import tempfile
import unittest
from pathlib import Path

from app.domain import StoryboardScene
from app.modules.video_component import VideoComponentBuilder
from app.modules.video_component.models import (
    MinimalVisualContext,
    MotionIntent,
    VideoPromptPlan,
)


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def write_png_header(
    path,
    width,
    height
):
    path.write_bytes(
        PNG_SIGNATURE
        + struct.pack(
            ">I",
            13
        )
        + b"IHDR"
        + struct.pack(
            ">II",
            width,
            height
        )
        + b"\x08\x02\x00\x00\x00"
        + b"\x00\x00\x00\x00"
    )


class VideoComponentBuilderTest(unittest.TestCase):

    def test_prepares_video_request_without_backend(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = (
                Path(temp_dir)
                / "source.png"
            )
            write_png_header(
                source_path,
                1280,
                720
            )

            result = VideoComponentBuilder().prepare(
                source_path=source_path
            )

        self.assertEqual(
            "prepared",
            result.status
        )
        self.assertFalse(
            result.backend_required
        )
        self.assertEqual(
            "16:9",
            result.visual_context.aspect_ratio
        )
        self.assertEqual(
            "subtle",
            result.motion_intent.motion_intensity
        )
        self.assertIn(
            "image-to-video",
            result.prompt_plan.prompt
        )

    def test_uses_default_video_source_path(self):
        class FakeAnalyzer:
            def __init__(self):
                self.received_path = None

            def analyze(
                self,
                source_path
            ):
                self.received_path = Path(
                    source_path
                )
                raise RuntimeError(
                    "stop after path capture"
                )

        analyzer = FakeAnalyzer()
        builder = VideoComponentBuilder(
            source_image_analyzer=analyzer
        )

        with self.assertRaises(
            RuntimeError
        ):
            builder.prepare()

        self.assertEqual(
            Path("tests/fixtures/video/source.png"),
            analyzer.received_path
        )

    def test_orchestration_does_not_generate_video_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            source_path = (
                root
                / "source.png"
            )
            write_png_header(
                source_path,
                720,
                1280
            )

            VideoComponentBuilder().prepare(
                source_path=source_path
            )

            self.assertFalse(
                list(
                    root.glob("*.mp4")
                )
            )

    def test_passes_storyboard_scene_to_motion_intent_builder(self):
        class FakeAnalyzer:
            def analyze(
                self,
                source_path
            ):
                return MinimalVisualContext(
                    source_path=Path(
                        source_path
                    ),
                    width=1280,
                    height=720,
                    aspect_ratio="16:9",
                    orientation="landscape",
                    image_format="PNG",
                )

        class FakeMotionIntentBuilder:
            def __init__(
                self
            ):
                self.storyboard_scene = None

            def build(
                self,
                visual_context,
                storyboard_scene=None
            ):
                self.storyboard_scene = storyboard_scene
                return MotionIntent(
                    source="test",
                    camera_motion="slow drift",
                    motion_intensity="subtle",
                    stability="high",
                    temporal_rhythm="slow",
                )

        class FakeTranslator:
            def translate(
                self,
                motion_intent
            ):
                return VideoPromptPlan(
                    prompt="image-to-video prompt",
                    negative_prompt="",
                    motion_summary="slow drift",
                )

        motion_builder = FakeMotionIntentBuilder()
        storyboard_scene = StoryboardScene(
            scene_number=1,
            text="Nikola Tesla en su laboratorio.",
            visible_subject="Nikola Tesla",
            visible_action="sentado junto a una lampara",
            visible_environment="laboratorio",
            filmable_interpretation="plano cinematico estable",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = (
                Path(
                    temp_dir
                )
                / "source.png"
            )
            source_path.write_bytes(
                b"png"
            )

            VideoComponentBuilder(
                source_image_analyzer=FakeAnalyzer(),
                motion_intent_builder=motion_builder,
                video_prompt_translator=FakeTranslator(),
            ).prepare(
                source_path=source_path,
                storyboard_scene=storyboard_scene
            )

        self.assertIs(
            storyboard_scene,
            motion_builder.storyboard_scene
        )


if __name__ == "__main__":
    unittest.main()
