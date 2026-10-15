import hashlib
import tempfile
import unittest
from pathlib import Path

from app.modules.video_component.contracts import (
    WanArtifactRetention,
    WanIntermediateOutput,
    WanLosslessCapturePlan,
)
from app.modules.video_component.models import BackendVideoPrompt, ComfyUIVideoWorkflow
from app.modules.video_component.comfyui_video_backend import ComfyUIVideoBackend
from app.modules.video_component.lossless_frame_output import (
    LosslessWanFrameOutput,
    LosslessWanFrameOutputError,
)


class _Runner:
    def __init__(self, fail=False):
        self.command = None
        self.fail = fail

    def run(self, command):
        self.command = command
        if self.fail:
            raise RuntimeError("ffmpeg failed")
        Path(command[-1]).write_bytes(b"ffv1")


def _png(width=2, height=1, bit_depth=8):
    return (
        b"\x89PNG\r\n\x1a\n"
        + (13).to_bytes(4, "big")
        + b"IHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + bytes((bit_depth, 2, 0, 0, 0))
        + b"\x00\x00\x00\x00"
    )


class LosslessWanFrameOutputTest(unittest.TestCase):

    @staticmethod
    def _plan(*, job_id="job-a", retention=WanArtifactRetention.CLEANUP_ON_SUCCESS):
        return WanLosslessCapturePlan(
            job_id=job_id,
            capture_node_id="capture-a",
            output_prefix=f"aivc_wan_lossless/{job_id}/frame",
            expected_frame_count=2,
            width=2,
            height=1,
            fps=12,
            bit_depth=8,
            retention=retention,
        )

    def _history(self, items=None):
        return {
            "outputs": {
                "capture-a": {
                    "images": items or [
                        {"filename": "frame_00002_.png", "subfolder": "a", "type": "output"},
                        {"filename": "frame_00001_.png", "subfolder": "a", "type": "output"},
                    ],
                },
            },
        }

    def test_captures_all_frames_in_deterministic_order_and_materializes_ffv1(self):
        runner = _Runner()
        output = LosslessWanFrameOutput(runner=runner)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            def download(item, path):
                Path(path).write_bytes(_png())

            sequence = output.capture(
                history_item=self._history(),
                plan=self._plan(),
                prompt_id="prompt-a",
                destination_root=root,
                download=download,
            )
            self.assertEqual(["frame_000001.png", "frame_000002.png"], [path.name for path in sequence.ordered_frame_paths])
            self.assertEqual(
                hashlib.sha256(_png() + _png()).hexdigest(),
                sequence.fingerprint,
            )
            clip = output.materialize_ffv1(sequence, root / "clip.mkv")

            self.assertEqual(root / "clip.mkv", clip)
            self.assertIn("ffv1", runner.command)
            self.assertTrue(runner.command[runner.command.index("-i") + 1].endswith("frame_%06d.png"))
            self.assertIn("-framerate", runner.command)
            output.cleanup_after_success(sequence)
            self.assertFalse(sequence.artifact_root.exists())

    def test_rejects_missing_duplicate_and_out_of_sequence_frames(self):
        output = LosslessWanFrameOutput(runner=_Runner())
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            cases = (
                [{"filename": "frame_00001_.png"}],
                [
                    {"filename": "frame_00001_.png"},
                    {"filename": "frame_00001_.png"},
                ],
                [
                    {"filename": "frame_00001_.png"},
                    {"filename": "frame_00003_.png"},
                ],
            )
            for items in cases:
                with self.assertRaises(LosslessWanFrameOutputError):
                    output.capture(
                        history_item=self._history(items),
                        plan=self._plan(),
                        prompt_id="prompt-a",
                        destination_root=root,
                        download=lambda item, path: Path(path).write_bytes(_png()),
                    )

    def test_failure_preserves_owned_frames_and_preserve_always_keeps_them(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = LosslessWanFrameOutput(runner=_Runner(fail=True))
            sequence = output.capture(
                history_item=self._history(),
                plan=self._plan(),
                prompt_id="prompt-a",
                destination_root=root,
                download=lambda item, path: Path(path).write_bytes(_png()),
            )
            with self.assertRaises(LosslessWanFrameOutputError):
                output.materialize_ffv1(sequence, root / "clip.mkv")
            self.assertTrue(sequence.artifact_root.exists())

            preserved = output.capture(
                history_item=self._history(),
                plan=self._plan(job_id="job-b", retention=WanArtifactRetention.PRESERVE_ALWAYS),
                prompt_id="prompt-b",
                destination_root=root,
                download=lambda item, path: Path(path).write_bytes(_png()),
            )
            output.cleanup_after_success(preserved)
            self.assertTrue(preserved.artifact_root.exists())

    def test_backend_opt_in_uses_same_prompt_frames_and_returns_ffv1_clip(self):
        class Backend(ComfyUIVideoBackend):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.wait_for_video_calls = 0
                self.download_video_calls = 0

            def queue_prompt(self, workflow, client_id):
                self.workflow = workflow
                return "prompt-a"

            def wait_for_video(self, prompt_id):
                self.wait_for_video_calls += 1
                raise AssertionError("lossless completion must not wait for SaveVideo")

            def _history(self, prompt_id):
                return {
                    prompt_id: {
                        "outputs": {
                            "capture-a": {
                                "images": [
                                    {"filename": "frame_00001_.png", "subfolder": "a", "type": "output"},
                                    {"filename": "frame_00002_.png", "subfolder": "a", "type": "output"},
                                ],
                            },
                        },
                    },
                }

            def download_video(self, video_info, output_dir, output_name):
                self.download_video_calls += 1
                raise AssertionError("lossless completion must not download SaveVideo")

            def download_output_file(self, output_info, output_path):
                Path(output_path).write_bytes(_png())
                return Path(output_path)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.png"
            source.write_bytes(_png())
            plan = self._plan()
            workflow = ComfyUIVideoWorkflow(
                workflow={
                    "load": {"class_type": "LoadImage", "inputs": {"image": "source.png"}},
                    "capture-a": {"class_type": "SaveImage", "inputs": {"images": ["vae", 0]}},
                },
                backend_prompt=BackendVideoPrompt(
                    source_image=source,
                    positive_prompt="prompt",
                    negative_prompt="",
                    motion_summary="motion",
                    frames=2,
                    fps=12,
                    generation_width=2,
                    generation_height=1,
                    intermediate_output=WanIntermediateOutput.LOSSLESS_FFV1,
                ),
                source_image_name="source.png",
                output_prefix="clip",
                lossless_capture=plan,
            )
            backend = Backend(
                comfyui_input_dir=root / "input",
                comfyui_output_dir=root / "output",
                lossless_frame_output=LosslessWanFrameOutput(runner=_Runner()),
            )
            owned_remote = root / "output" / "aivc_wan_lossless" / plan.job_id
            other_remote = root / "output" / "aivc_wan_lossless" / "other-job"
            owned_remote.mkdir(parents=True)
            other_remote.mkdir(parents=True)
            (owned_remote / "frame_00001_.png").write_bytes(_png())
            (other_remote / "keep.png").write_bytes(_png())
            result = backend.generate(workflow, root / "clips", "scene_001.mp4")

            self.assertEqual("scene_001.mkv", result.output_clip.name)
            self.assertTrue(result.output_clip.exists())
            self.assertFalse((root / "clips" / ".wan_lossless" / plan.job_id).exists())
            self.assertFalse(owned_remote.exists())
            self.assertTrue((other_remote / "keep.png").exists())
            self.assertEqual(["capture-a", "load"], sorted(backend.workflow))
            self.assertFalse(
                any(
                    node.get("class_type") == "SaveVideo"
                    for node in backend.workflow.values()
                    if isinstance(node, dict)
                )
            )
            self.assertEqual(0, backend.wait_for_video_calls)
            self.assertEqual(0, backend.download_video_calls)


if __name__ == "__main__":
    unittest.main()
