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
        ) as urlopen_mock:
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
        self.assertNotIn(
            "timeout",
            urlopen_mock.call_args.kwargs,
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

    def test_wait_for_video_keeps_polling_without_deadline(self):
        class HistoryBackend(ComfyUIVideoBackend):
            def __init__(self):
                super().__init__(poll_interval_seconds=0)
                self.calls = 0

            def _history(self, prompt_id):
                self.calls += 1
                if self.calls == 1:
                    return {}
                return {
                    prompt_id: {
                        "outputs": {
                            "12": {
                                "images": [{
                                    "filename": "clip.mp4",
                                }],
                            },
                        },
                    },
                }

        backend = HistoryBackend()
        info = backend.wait_for_video("prompt-id")

        self.assertEqual("clip.mp4", info["filename"])
        self.assertEqual(2, backend.calls)
        self.assertFalse(hasattr(backend, "timeout_seconds"))

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

    def test_history_and_download_omit_request_timeout(self):
        backend = ComfyUIVideoBackend()

        with patch(
            "urllib.request.urlopen",
            return_value=FakeResponse(b"{}"),
        ) as history_mock:
            backend._history("prompt-id")

        self.assertNotIn("timeout", history_mock.call_args.kwargs)

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "urllib.request.urlopen",
                return_value=FakeResponse(b"video-bytes"),
            ) as download_mock:
                output = backend.download_video(
                    {"filename": "clip.mp4"},
                    Path(temp_dir),
                    "clip.mp4",
                )

        self.assertEqual("clip.mp4", output.name)
        self.assertNotIn("timeout", download_mock.call_args.kwargs)

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
                    positive_prompt="exact positive prompt",
                    negative_prompt="exact negative prompt",
                    motion_summary="subtle motion, high stability",
                    camera_motion="slow stable drift",
                    motion_intensity="subtle",
                    stability="high",
                    temporal_rhythm="slow and steady",
                    motion_level="subtle",
                    preservation_constraints=(
                        "preserve source composition",
                    ),
                    avoidance_constraints=(
                        "avoid abrupt motion",
                    ),
                    source_trace=(
                        "VisualTruth.visible_subject",
                    ),
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
            self.assertEqual(
                "exact positive prompt",
                manifest["positive_prompt"]
            )
            self.assertEqual(
                "exact negative prompt",
                manifest["negative_prompt"]
            )
            self.assertEqual(
                "subtle motion, high stability",
                manifest["motion_summary"]
            )
            self.assertEqual(
                "slow stable drift",
                manifest["camera_motion"]
            )
            self.assertEqual(
                "subtle",
                manifest["motion_intensity"]
            )
            self.assertEqual(
                "high",
                manifest["stability"]
            )
            self.assertEqual(
                "slow and steady",
                manifest["temporal_rhythm"]
            )
            self.assertEqual(
                "subtle",
                manifest["motion_level"]
            )
            self.assertEqual(
                ["preserve source composition"],
                manifest["preservation_constraints"]
            )
            self.assertEqual(
                ["avoid abrupt motion"],
                manifest["avoidance_constraints"]
            )
            self.assertEqual(
                ["VisualTruth.visible_subject"],
                manifest["source_trace"]
            )


if __name__ == "__main__":
    unittest.main()
