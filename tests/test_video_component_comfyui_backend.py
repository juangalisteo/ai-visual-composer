import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.modules.video_component import (
    BackendVideoPrompt,
    ComfyUIVideoBackend,
    ComfyUIVideoBackendError,
    ComfyUIVideoWorkflow,
)


class FakeResponse:
    def __init__(
        self,
        payload
    ):
        self.payload = payload

    def __enter__(
        self
    ):
        return io.BytesIO(
            self.payload
        )

    def __exit__(
        self,
        exc_type,
        exc,
        traceback
    ):
        return False


class ComfyUIVideoBackendTest(unittest.TestCase):

    def test_queue_prompt_returns_prompt_id(self):
        backend = ComfyUIVideoBackend()

        with patch(
            "urllib.request.urlopen",
            return_value=FakeResponse(
                b'{"prompt_id": "abc"}'
            ),
        ):
            prompt_id = backend.queue_prompt(
                {
                    "1": {
                        "class_type": "SaveVideo",
                        "inputs": {},
                    },
                },
                "client",
            )

        self.assertEqual(
            "abc",
            prompt_id
        )

    def test_queue_prompt_wraps_connection_errors(self):
        backend = ComfyUIVideoBackend()

        with patch(
            "urllib.request.urlopen",
            side_effect=OSError("offline"),
        ):
            with self.assertRaises(
                ComfyUIVideoBackendError
            ) as context:
                backend.queue_prompt(
                    {},
                    "client",
                )

        self.assertEqual(
            "CONNECTION_ERROR",
            context.exception.category
        )

    def test_wait_for_video_reads_mp4_from_history(self):
        class HistoryBackend(ComfyUIVideoBackend):
            def _history(
                self,
                prompt_id
            ):
                return {
                    prompt_id: {
                        "outputs": {
                            "12": {
                                "images": [
                                    {
                                        "filename": "clip.mp4",
                                        "subfolder": "vc1",
                                        "type": "output",
                                    },
                                ],
                            },
                        },
                        "status": {
                            "status_str": "success",
                        },
                    },
                }

        info = HistoryBackend(
            poll_interval_seconds=0
        ).wait_for_video(
            "prompt-id"
        )

        self.assertEqual(
            "clip.mp4",
            info["filename"]
        )

    def test_download_video_rejects_empty_clip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            backend = ComfyUIVideoBackend()
            with patch(
                "urllib.request.urlopen",
                return_value=FakeResponse(
                    b""
                ),
            ):
                with self.assertRaises(
                    ComfyUIVideoBackendError
                ) as context:
                    backend.download_video(
                        {
                            "filename": "clip.mp4",
                            "subfolder": "",
                            "type": "output",
                        },
                        Path(
                            temp_dir
                        ),
                        "clip_001.mp4",
                    )

        self.assertEqual(
            "EXECUTION_ERROR",
            context.exception.category
        )

    def test_generate_stages_source_and_writes_manifest(self):
        class DeterministicBackend(ComfyUIVideoBackend):
            def queue_prompt(
                self,
                workflow,
                client_id
            ):
                return "prompt-id"

            def wait_for_video(
                self,
                prompt_id
            ):
                return {
                    "filename": "clip.mp4",
                    "subfolder": "",
                    "type": "output",
                }

            def download_video(
                self,
                video_info,
                output_dir,
                output_name
            ):
                output_path = (
                    Path(
                        output_dir
                    )
                    / output_name
                )
                output_path.write_bytes(
                    b"video-bytes"
                )
                return output_path

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            source = root / "source.png"
            source.write_bytes(
                b"png-bytes"
            )
            prepared = ComfyUIVideoWorkflow(
                workflow={
                    "1": {
                        "class_type": "SaveVideo",
                        "inputs": {},
                    },
                },
                backend_prompt=BackendVideoPrompt(
                    source_image=source,
                    positive_prompt="prompt",
                    negative_prompt="",
                    motion_summary="motion",
                    target_width=1080,
                    target_height=1920,
                    steps=12,
                    cfg=5.0,
                    sampler="uni_pc",
                    scheduler="simple",
                    profile_name="Instagram",
                ),
                source_image_name="source.png",
                output_prefix="vc1/clip_001",
            )

            result = DeterministicBackend(
                comfyui_input_dir=root / "comfy_input"
            ).generate(
                prepared,
                root / "video_clips",
                output_name="scene_001.mp4"
            )

            self.assertTrue(
                (
                    root
                    / "comfy_input"
                    / "source.png"
                ).exists()
            )
            self.assertTrue(
                result.output_clip.exists()
            )
            self.assertEqual(
                "scene_001.mp4",
                result.output_clip.name
            )
            self.assertTrue(
                result.manifest_path.exists()
            )
            manifest = json.loads(
                result.manifest_path.read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                "prompt-id",
                manifest["prompt_id"]
            )
            self.assertEqual(
                "Instagram",
                manifest["profile"]
            )
            self.assertEqual(
                123456789,
                manifest["seed"]
            )
            self.assertEqual(
                1080,
                manifest["target_width"]
            )
            self.assertEqual(
                1920,
                manifest["target_height"]
            )
            self.assertEqual(
                12,
                manifest["steps"]
            )
            self.assertEqual(
                "uni_pc",
                manifest["sampler"]
            )


if __name__ == "__main__":
    unittest.main()
