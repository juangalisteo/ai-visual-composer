import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from app.modules.video.ffmpeg.graphs.overlay_graph_builder import (
    OverlayGraphBuilder
)
from app.modules.video.media.media_loader import MediaLoader


class RecordingOverlayBuilder:

    def __init__(
        self
    ):
        self.config = SimpleNamespace(
            repeat_mode="scene",
            min_seconds=1.0
        )
        self.calls = []

    def build(
        self,
        scene_index,
        scene_count,
        scene_metadata=None
    ):
        self.calls.append(
            (
                scene_index,
                scene_count,
                scene_metadata
            )
        )
        return {
            "overlay": f"overlay_{scene_index}.mov",
            "input_position": scene_index,
            "blend_mode": "screen",
            "opacity": 0.5,
            "duration": 1.0
        }


class OverlaySceneTimingTest(
    unittest.TestCase
):

    def test_scene_mode_creates_one_timed_operation_per_scene(
        self
    ):
        overlay_builder = RecordingOverlayBuilder()
        graph = SimpleNamespace(
            context=SimpleNamespace(
                config=SimpleNamespace(
                    width=640,
                    height=360,
                    fps=24,
                    overlays=SimpleNamespace(
                        enabled=True
                    )
                ),
                media=SimpleNamespace(
                    scene_metadata=(
                        {
                            "visible_subject": "scene one"
                        },
                        {
                            "visible_subject": "scene two"
                        },
                        {
                            "visible_subject": "scene three"
                        }
                    )
                ),
                timeline=SimpleNamespace(
                    audio_duration=5.0,
                    image_duration=2.0
                ),
                first_overlay_input=3
            ),
            filter_parts=[
                "[0:v]base[base]"
            ],
            current_stream="[base]",
            video_streams=(
                "[v0]",
                "[v1]",
                "[v2]"
            ),
            overlay_streams=(),
            visual_effect_streams=()
        )

        result = OverlayGraphBuilder(
            overlay_builder
        ).build(
            graph
        )

        self.assertEqual(
            [
                (0, 3, {
                    "visible_subject": "scene one"
                }),
                (1, 3, {
                    "visible_subject": "scene two"
                }),
                (2, 3, {
                    "visible_subject": "scene three"
                })
            ],
            overlay_builder.calls
        )
        self.assertEqual(
            3,
            len(
                result.overlay_streams
            )
        )
        self.assertIn(
            "enable='between(t,0.000,2.000)'",
            result.parts[2]
        )
        self.assertIn(
            "enable='between(t,2.000,4.000)'",
            result.parts[4]
        )
        self.assertIn(
            "enable='between(t,4.000,5.000)'",
            result.parts[6]
        )


class OverlaySceneMetadataLoaderTest(
    unittest.TestCase
):

    def test_media_loader_aligns_visual_truth_with_image_scenes(
        self
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            audio_path = root / "audio.mp3"
            subtitle_path = root / "subtitles.srt"
            first_image = root / "scene_001.png"
            second_image = root / "scene_002.png"
            manifest_path = root / "images_manifest.json"
            storyboard_path = root / "storyboard.json"

            audio_path.write_bytes(
                b"audio"
            )
            subtitle_path.write_text(
                "subtitle",
                encoding="utf-8"
            )
            first_image.write_bytes(
                b"image-one"
            )
            second_image.write_bytes(
                b"image-two"
            )
            manifest_path.write_text(
                json.dumps(
                    [
                        {
                            "scene": 2,
                            "image": str(second_image)
                        },
                        {
                            "scene": 1,
                            "image": str(first_image)
                        }
                    ]
                ),
                encoding="utf-8"
            )
            storyboard_path.write_text(
                json.dumps(
                    [
                        {
                            "scene": 1,
                            "visible_subject": "stone temple",
                            "visible_action": "sunlight moves"
                        },
                        {
                            "scene": 2,
                            "visible_subject": "Tesla coil",
                            "visible_action": (
                                "electric sparks cross the coil"
                            ),
                            "key_objects": [
                                "electric generator"
                            ]
                        }
                    ]
                ),
                encoding="utf-8"
            )

            media = MediaLoader().load(
                audio_path=audio_path,
                subtitle_path=subtitle_path,
                images_manifest_path=manifest_path,
                output_path=root / "video" / "final.mp4",
                storyboard_path=storyboard_path
            )

        self.assertEqual(
            (
                second_image,
                first_image
            ),
            media.image_paths
        )
        self.assertEqual(
            "Tesla coil",
            media.scene_metadata[0][
                "visible_subject"
            ]
        )
        self.assertEqual(
            "stone temple",
            media.scene_metadata[1][
                "visible_subject"
            ]
        )

if __name__ == "__main__":
    unittest.main()
