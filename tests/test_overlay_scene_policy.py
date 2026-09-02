import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from app.modules.video.config.overlay_config import OverlayConfig
from app.modules.video.ffmpeg.graphs.overlay_graph_builder import (
    OverlayGraphBuilder
)
from app.modules.video.media.media_loader import MediaLoader
from app.modules.video.overlays.overlay_selector import OverlaySelector


def overlay_config(
    directory,
    file_selection="sequence"
):
    return OverlayConfig(
        enabled=True,
        directory=str(directory),
        folder_selection="random",
        file_selection=file_selection,
        avoid_repeats=True,
        repeat_mode="scene",
        min_seconds=1.0,
        max_seconds=1.0,
        loop_file=True,
        opacity=0.5,
        blend_mode="screen",
        probability=1.0,
        folders=(
            "Electricity",
            "Light Leaks"
        ),
        types=(),
        extensions=(
            ".mp4",
            ".mov"
        ),
        folder_weights={},
        file_weights={}
    )


class OverlayScenePolicyTest(
    unittest.TestCase
):

    def setUp(
        self
    ):
        self.temporary_directory = (
            tempfile.TemporaryDirectory()
        )
        self.root = Path(
            self.temporary_directory.name
        )
        electricity = self.root / "Electricity"
        light_leaks = self.root / "Light Leaks"
        electricity.mkdir()
        light_leaks.mkdir()

        for folder, prefix in (
            (electricity, "electricity"),
            (light_leaks, "light")
        ):
            for index in range(1, 3):
                (
                    folder
                    / f"{prefix}_{index}.mp4"
                ).touch()

    def tearDown(
        self
    ):
        self.temporary_directory.cleanup()

    def _selector(
        self
    ):
        return OverlaySelector(
            overlay_config(
                self.root
            )
        )

    def test_odd_scenes_use_only_light_leaks(
        self
    ):
        selector = self._selector()

        first = selector.select(
            scene_index=0,
            scene_count=3,
            scene_metadata={
                "visible_action": (
                    "electricity arcs across the room"
                )
            }
        )
        third = selector.select(
            scene_index=2,
            scene_count=3,
            scene_metadata={
                "visible_action": "lightning strike"
            }
        )

        self.assertEqual(
            "Light Leaks",
            first.parent.name
        )
        self.assertEqual(
            "Light Leaks",
            third.parent.name
        )

    def test_even_scene_allows_electricity_for_explicit_evidence(
        self
    ):
        selected = self._selector().select(
            scene_index=1,
            scene_count=2,
            scene_metadata={
                "visible_environment": (
                    "Una tormenta electrica ilumina el cielo."
                )
            }
        )

        self.assertEqual(
            "Electricity",
            selected.parent.name
        )

    def test_static_fourth_electric_scene_allows_electricity(
        self
    ):
        selected = self._selector().select(
            scene_index=3,
            scene_count=4,
            scene_metadata={
                "visible_environment": (
                    "Tormenta electrica con relampagos."
                ),
                "key_objects": (
                    "chispas electricas",
                ),
            }
        )

        self.assertEqual(
            "Electricity",
            selected.parent.name
        )

    def test_even_scene_without_thematic_evidence_uses_light_leaks(
        self
    ):
        selected = self._selector().select(
            scene_index=1,
            scene_count=2,
            scene_metadata={
                "visible_subject": "a stone temple",
                "visible_action": "sunlight crosses columns",
                "visible_environment": "quiet ancient courtyard"
            }
        )

        self.assertEqual(
            "Light Leaks",
            selected.parent.name
        )

    def test_unrelated_scene_never_receives_electricity(
        self
    ):
        selected = self._selector().select(
            scene_index=1,
            scene_count=2,
            scene_metadata={
                "visible_subject": "a person reading",
                "key_objects": (
                    "book",
                    "wooden desk"
                ),
                "visual_constraints": (
                    "quiet atmosphere",
                )
            }
        )

        self.assertEqual(
            "Light Leaks",
            selected.parent.name
        )

    def test_light_leaks_does_not_repeat_the_previous_file(
        self
    ):
        selector = self._selector()

        first = selector.select(
            scene_index=0,
            scene_count=3,
            scene_metadata={}
        )
        third = selector.select(
            scene_index=2,
            scene_count=3,
            scene_metadata={}
        )

        self.assertNotEqual(
            first,
            third
        )


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

    def test_i2v_metadata_enables_electricity_for_fourth_scene(
        self
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio_path = root / "audio.mp3"
            subtitle_path = root / "subtitles.srt"
            manifest_path = root / "video_clips_manifest.json"
            storyboard_path = root / "storyboard.json"
            clips = []

            audio_path.write_bytes(b"audio")
            subtitle_path.write_text("subtitle", encoding="utf-8")

            for scene_number in range(1, 5):
                clip_path = root / f"scene_{scene_number:03d}.mp4"
                clip_path.write_bytes(b"video")
                clips.append(
                    {
                        "scene": scene_number,
                        "output_clip": str(clip_path),
                        "duration_seconds": 1.0,
                    }
                )

            manifest_path.write_text(
                json.dumps(list(reversed(clips))),
                encoding="utf-8"
            )
            storyboard_path.write_text(
                json.dumps(
                    [
                        {
                            "scene": 1,
                            "visible_action": "quiet sunrise",
                        },
                        {
                            "scene": 2,
                            "visible_subject": "stone temple",
                        },
                        {
                            "scene": 3,
                            "visible_action": "calm clouds",
                        },
                        {
                            "scene": 4,
                            "visible_environment": (
                                "tormenta electrica con relampagos"
                            ),
                            "key_objects": [
                                "chispas electricas",
                            ],
                        },
                    ]
                ),
                encoding="utf-8"
            )

            media = MediaLoader().load(
                audio_path=audio_path,
                subtitle_path=subtitle_path,
                images_manifest_path=manifest_path,
                output_path=root / "video" / "final.mp4",
                media_manifest_type="video_clips",
                storyboard_path=storyboard_path,
            )
            electricity = root / "overlays" / "Electricity"
            light_leaks = root / "overlays" / "Light Leaks"
            electricity.mkdir(parents=True)
            light_leaks.mkdir(parents=True)
            (electricity / "electricity.mp4").touch()
            (light_leaks / "light.mp4").touch()
            selector = OverlaySelector(
                overlay_config(root / "overlays")
            )

            self.assertEqual(
                ("video", "video", "video", "video"),
                media.media_types
            )
            self.assertEqual(
                "tormenta electrica con relampagos",
                media.scene_metadata[3]["visible_environment"]
            )
            self.assertEqual(
                "Light Leaks",
                selector.select(
                    scene_index=0,
                    scene_count=4,
                    scene_metadata=media.scene_metadata[0],
                ).parent.name
            )
            self.assertEqual(
                "Light Leaks",
                selector.select(
                    scene_index=1,
                    scene_count=4,
                    scene_metadata=media.scene_metadata[1],
                ).parent.name
            )
            self.assertEqual(
                "Electricity",
                selector.select(
                    scene_index=3,
                    scene_count=4,
                    scene_metadata=media.scene_metadata[3],
                ).parent.name
            )


if __name__ == "__main__":
    unittest.main()
