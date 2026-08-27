import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.domain import GenerationResult
from app.modules.images.image_builder import ImageBuilder
from app.modules.images.manifest_writer import ImageManifestWriter
from app.modules.video.media.media_loader import MediaLoader


class RecordingBackend:

    def __init__(
        self,
        image_path
    ):
        self.image_path = image_path

    def generate(
        self,
        prompt,
        scene_number,
        output_dir,
        width,
        height
    ):
        output_dir.mkdir(
            parents=True,
            exist_ok=True
        )
        self.image_path.write_bytes(
            b"image"
        )

        return self.image_path


class RecordingManifestWriter:

    def __init__(
        self,
        manifest_path
    ):
        self.manifest_path = manifest_path
        self.entries = []
        self.writes = []

    def build_entry(
        self,
        generation_result,
        prompt,
        prompt_metadata,
        image_path
    ):
        entry = ImageManifestWriter().build_entry(
            generation_result=generation_result,
            prompt=prompt,
            prompt_metadata=prompt_metadata,
            image_path=image_path
        )
        self.entries.append(
            entry
        )

        return entry

    def write(
        self,
        manifest_path,
        entries
    ):
        self.writes.append(
            (
                manifest_path,
                entries
            )
        )

        return ImageManifestWriter().write(
            manifest_path=manifest_path,
            entries=entries
        )


class ImageManifestWriterTest(unittest.TestCase):

    def test_build_entry_preserves_legacy_keys_order_and_types(self):
        writer = ImageManifestWriter()
        image_path = Path(
            "output/images/scene_001.png"
        )
        generation_result = GenerationResult(
            output_path=str(
                image_path
            ),
            scene_number=1,
            width=640,
            height=360,
            duration=3
        )
        prompt_metadata = {
            "positive_prompt": "positive",
            "negative_prompt": "",
            "visual_director": {
                "enabled": False,
                "fallback": False,
                "fallback_reason": None,
                "directives": {}
            }
        }

        entry = writer.build_entry(
            generation_result=generation_result,
            prompt="final prompt",
            prompt_metadata=prompt_metadata,
            image_path=image_path
        )

        self.assertEqual(
            [
                "scene",
                "prompt",
                "positive_prompt",
                "negative_prompt",
                "visual_director",
                "image",
                "width",
                "height",
                "duration"
            ],
            list(
                entry.keys()
            )
        )
        self.assertEqual(
            1,
            entry["scene"]
        )
        self.assertEqual(
            "final prompt",
            entry["prompt"]
        )
        self.assertEqual(
            "positive",
            entry["positive_prompt"]
        )
        self.assertEqual(
            "",
            entry["negative_prompt"]
        )
        self.assertEqual(
            str(
                image_path
            ),
            entry["image"]
        )
        self.assertEqual(
            3,
            entry["duration"]
        )

    def test_write_preserves_legacy_json_format(self):
        writer = ImageManifestWriter()
        entries = [
            {
                "scene": 1,
                "prompt": "final prompt",
                "positive_prompt": "positive",
                "negative_prompt": "",
                "visual_director": {
                    "enabled": False,
                    "fallback": False,
                    "fallback_reason": None,
                    "directives": {}
                },
                "image": "output/images/scene_001.png",
                "width": 640,
                "height": 360,
                "duration": 3
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(
                temp_dir
            ) / "images_manifest.json"

            result = writer.write(
                manifest_path=manifest_path,
                entries=entries
            )

            self.assertEqual(
                manifest_path,
                result
            )
            self.assertEqual(
                json.dumps(
                    entries,
                    ensure_ascii=False,
                    indent=4
                ),
                manifest_path.read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                entries,
                json.loads(
                    manifest_path.read_text(
                        encoding="utf-8"
                    )
                )
            )

    def test_media_loader_consumes_manifest_without_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            image_path = root / "images" / "scene_001.png"
            image_path.parent.mkdir()
            image_path.write_bytes(
                b"image"
            )
            audio_path = root / "audio.mp3"
            subtitle_path = root / "subtitles.srt"
            manifest_path = root / "images_manifest.json"
            output_path = root / "video.mp4"

            audio_path.write_bytes(
                b"audio"
            )
            subtitle_path.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\nTexto",
                encoding="utf-8"
            )

            ImageManifestWriter().write(
                manifest_path=manifest_path,
                entries=[
                    {
                        "scene": 1,
                        "prompt": "final prompt",
                        "positive_prompt": "positive",
                        "negative_prompt": "",
                        "visual_director": {
                            "enabled": False,
                            "fallback": False,
                            "fallback_reason": None,
                            "directives": {}
                        },
                        "image": str(
                            image_path
                        ),
                        "width": 640,
                        "height": 360,
                        "duration": 3
                    }
                ]
            )

            media = MediaLoader().load(
                audio_path=audio_path,
                subtitle_path=subtitle_path,
                images_manifest_path=manifest_path,
                output_path=output_path
            )

        self.assertEqual(
            (
                image_path,
            ),
            media.image_paths
        )
        self.assertEqual(
            (
                "image",
            ),
            media.media_types
        )

    def test_image_builder_delegates_manifest_entry_and_write(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            storyboard_path = root / "storyboard.json"
            manifest_path = root / "images_manifest.json"
            output_dir = root / "images"
            image_path = output_dir / "scene_001.png"
            workflow_path = root / "workflow.json"
            manifest_writer = RecordingManifestWriter(
                manifest_path=manifest_path
            )

            storyboard_path.write_text(
                json.dumps(
                    [
                        {
                            "scene": 1,
                            "text": "La escena conserva su texto.",
                            "visible_subject": "quiet valley",
                            "visible_action": "dawn light spreads slowly",
                            "visible_environment": "mountain landscape",
                            "time_context": "dawn",
                            "key_objects": [
                                "mist",
                            ],
                            "spatial_relationships": [
                                "mist rests below the ridge",
                            ],
                            "continuity_links": [],
                            "abstract_source": "beginning",
                            "filmable_interpretation": (
                                "A quiet dawn over a valley"
                            ),
                            "visual_constraints": [
                                "no readable text",
                            ],
                            "visual_truth_status": "structured",
                            "duration": 3
                        }
                    ],
                    ensure_ascii=False
                ),
                encoding="utf-8"
            )
            workflow_path.write_text(
                "{}",
                encoding="utf-8"
            )

            project = SimpleNamespace(
                images_manifest_path=lambda: manifest_path
            )
            config = SimpleNamespace(
                get_profile_config=lambda: {
                    "format": "horizontal",
                    "video_style": {
                        "width": 640,
                        "height": 360
                    },
                    "visual_director": {
                        "enabled": False
                    }
                }
            )

            with patch.multiple(
                "app.modules.images.image_builder",
                ProjectManager=lambda: project,
                ConfigManager=lambda: config
            ):
                result_path = ImageBuilder(
                    workflow_path=workflow_path,
                    backend=RecordingBackend(
                        image_path=image_path
                    ),
                    manifest_writer=manifest_writer
                ).build(
                    storyboard_path=storyboard_path,
                    output_dir=output_dir
                )

            manifest = json.loads(
                manifest_path.read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(
            manifest_path,
            result_path
        )
        self.assertEqual(
            1,
            len(
                manifest_writer.entries
            )
        )
        self.assertEqual(
            1,
            len(
                manifest_writer.writes
            )
        )
        self.assertEqual(
            manifest_writer.entries,
            manifest
        )


if __name__ == "__main__":
    unittest.main()
