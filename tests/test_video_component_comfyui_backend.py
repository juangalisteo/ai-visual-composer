import io
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from app.modules.video_component import (
    BackendVideoPrompt,
    ComfyUIVideoBackend,
    ComfyUIVideoBackendError,
    ComfyUIVideoWorkflow,
    WanIntermediateOutput,
)
from app.modules.video_component.contracts import (
    ComfyUIInputRetention,
    WanLosslessCapturePlan,
)
from app.shared.operational_error import OperationalError


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

    @staticmethod
    def _prepared_workflow(source):
        return ComfyUIVideoWorkflow(
            workflow={
                "load": {
                    "class_type": "LoadImage",
                    "inputs": {"image": "legacy-source.png"},
                },
            },
            backend_prompt=BackendVideoPrompt(
                source_image=source,
                positive_prompt="exact positive prompt",
                negative_prompt="exact negative prompt",
                motion_summary="subtle motion, high stability",
                intermediate_output=WanIntermediateOutput.SAVEVIDEO_H264,
            ),
            source_image_name="legacy-source.png",
            output_prefix="vc1/clip_001",
        )

    @staticmethod
    def _successful_backend_class():
        class SuccessfulBackend(ComfyUIVideoBackend):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.queued_workflows = []

            def queue_prompt(self, workflow, client_id):
                self.queued_workflows.append(deepcopy(workflow))
                return "prompt-id"

            def wait_for_video(self, prompt_id):
                return {"filename": "clip.mp4", "subfolder": "", "type": "output"}

            def download_video(self, video_info, output_dir, output_name):
                output_path = Path(output_dir) / output_name
                output_path.write_bytes(b"video-bytes")
                return output_path

        return SuccessfulBackend

    def test_generate_adapts_wan_backend_failure_with_context(self):
        class FailingBackend(ComfyUIVideoBackend):
            def _generate(self, **kwargs):
                raise ComfyUIVideoBackendError(
                    "backend failure",
                    category="EXECUTION_ERROR",
                    prompt_id="video-prompt-123",
                    node_id="42",
                    node_type="Wan22ImageToVideoLatent",
                    exception_type="BackendError",
                    status="error",
                )

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.png"
            source.write_bytes(b"png")
            prepared = ComfyUIVideoWorkflow(
                workflow={"sensitive": "workflow payload"},
                backend_prompt=BackendVideoPrompt(
                    source_image=source,
                    positive_prompt="positive prompt must stay private",
                    negative_prompt="negative prompt must stay private",
                    motion_summary="subtle motion",
                    camera_motion="static",
                    motion_intensity="subtle",
                    stability="high",
                    temporal_rhythm="slow",
                    profile_name="test_profile",
                    workflow="wan-workflow.json",
                ),
                source_image_name="source.png",
                output_prefix="vc1/clip",
            )

            with self.assertRaises(OperationalError) as context:
                FailingBackend().generate(prepared, Path(temp_dir) / "output")

        error = context.exception
        self.assertEqual("EXTERNAL_SERVICE", error.context.family)
        self.assertEqual("wan_i2v", error.context.technical_metadata["backend"])
        self.assertEqual("wan-workflow.json", error.context.technical_metadata["workflow"])
        self.assertEqual("video-prompt-123", error.context.technical_metadata["prompt_id"])
        self.assertEqual("42", error.context.technical_metadata["node_id"])
        self.assertNotIn("positive prompt", str(error.context.technical_metadata))
        self.assertIsInstance(error.__cause__, ComfyUIVideoBackendError)

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

    def test_generate_returns_complete_clip_result_without_public_manifest(self):
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

            self.assertTrue(source.exists())
            self.assertFalse(
                any((root / "comfy_input").rglob("*.png"))
            )
            self.assertTrue(
                result.output_clip.exists()
            )
            self.assertEqual(
                "scene_001.mp4",
                result.output_clip.name
            )
            self.assertIsNone(result.manifest_path)
            self.assertFalse(
                (root / "video_clips" / "video_clips_manifest.json").exists()
            )
            self.assertEqual(
                "prompt-id",
                result.prompt_id
            )
            self.assertEqual("ComfyUI", result.backend)
            self.assertEqual(
                "wan2.2_ti2v_5B_fp16.safetensors",
                result.model,
            )
            self.assertEqual(
                "config/comfyui_wan22_ti2v_i2v_workflow_api.json",
                result.workflow,
            )
            self.assertEqual(
                "Instagram",
                result.profile_name
            )
            self.assertEqual(
                123456789,
                result.seed
            )
            self.assertEqual(
                1080,
                result.target_width
            )
            self.assertEqual(
                1920,
                result.target_height
            )
            self.assertEqual(
                12,
                result.steps
            )
            self.assertEqual(320, result.generation_width)
            self.assertEqual(320, result.generation_height)
            self.assertEqual(17, result.frames)
            self.assertEqual(8.0, result.fps)
            self.assertEqual(5.0, result.cfg)
            self.assertEqual(
                "uni_pc",
                result.sampler
            )
            self.assertEqual("simple", result.scheduler)
            self.assertEqual(17 / 8, result.duration_seconds)
            self.assertEqual(64, len(result.fingerprint))
            self.assertEqual(
                "exact positive prompt",
                result.positive_prompt
            )
            self.assertEqual(
                "exact negative prompt",
                result.negative_prompt
            )
            self.assertEqual(
                "subtle motion, high stability",
                result.motion_summary
            )
            self.assertEqual(
                "slow stable drift",
                result.camera_motion
            )
            self.assertEqual(
                "subtle",
                result.motion_intensity
            )
            self.assertEqual(
                "high",
                result.stability
            )
            self.assertEqual(
                "slow and steady",
                result.temporal_rhythm
            )
            self.assertEqual(
                "subtle",
                result.motion_level
            )
            self.assertEqual(
                ("preserve source composition",),
                result.preservation_constraints
            )
            self.assertEqual(
                ("avoid abrupt motion",),
                result.avoidance_constraints
            )
            self.assertEqual(
                ("VisualTruth.visible_subject",),
                result.source_trace
            )

    def test_backend_never_overwrites_or_creates_public_manifest(self):
        successful_backend = self._successful_backend_class()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.png"
            source.write_bytes(b"source")
            output_dir = root / "output"
            output_dir.mkdir()
            manifest_path = output_dir / "video_clips_manifest.json"
            original_manifest = b'[{"scene": 99, "owner": "orchestrator"}]'
            manifest_path.write_bytes(original_manifest)

            result = successful_backend(
                comfyui_input_dir=root / "comfy_input",
            ).generate(
                self._prepared_workflow(source),
                output_dir,
            )

            self.assertIsNone(result.manifest_path)
            self.assertEqual(original_manifest, manifest_path.read_bytes())

    def test_staging_isolates_same_basename_by_technical_job_id(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first_source = root / "first" / "source image.png"
            second_source = root / "second" / "source image.png"
            first_source.parent.mkdir()
            second_source.parent.mkdir()
            first_source.write_bytes(b"first")
            second_source.write_bytes(b"second")
            backend = ComfyUIVideoBackend(
                comfyui_input_dir=root / "comfy_input",
            )
            first = backend._stage_source_image(
                self._prepared_workflow(first_source)
            )
            second = backend._stage_source_image(
                self._prepared_workflow(second_source)
            )

            self.assertNotEqual(first.job_id, second.job_id)
            self.assertNotEqual(first.staged_path, second.staged_path)
            self.assertTrue(first.relative_input_name.startswith("wan_i2v/"))
            self.assertTrue(second.relative_input_name.startswith("wan_i2v/"))
            self.assertEqual("source_image.png", Path(first.relative_input_name).name)
            self.assertEqual("source_image.png", Path(second.relative_input_name).name)
            self.assertTrue(first_source.exists())
            self.assertTrue(second_source.exists())
            self.assertTrue(first.staged_path.exists())
            self.assertTrue(second.staged_path.exists())

    def test_success_cleans_only_its_staged_input_and_queues_relative_name(self):
        successful_backend = self._successful_backend_class()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source image.png"
            source.write_bytes(b"source")
            backend = successful_backend(comfyui_input_dir=root / "comfy_input")

            backend.generate(
                self._prepared_workflow(source),
                root / "output",
            )

            queued_image = backend.queued_workflows[0]["load"]["inputs"]["image"]
            self.assertRegex(
                queued_image,
                r"^wan_i2v/[0-9a-f]{32}/source_image\.png$",
            )
            self.assertTrue(source.exists())
            self.assertFalse((root / "comfy_input" / queued_image).exists())

    def test_failures_preserve_the_owned_staged_input_for_each_remote_phase(self):
        class FailingBackend(ComfyUIVideoBackend):
            def __init__(self, phase, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.phase = phase
                self.queued_workflows = []

            def queue_prompt(self, workflow, client_id):
                self.queued_workflows.append(deepcopy(workflow))
                if self.phase == "queue":
                    raise ComfyUIVideoBackendError("queue failure")
                return "prompt-id"

            def wait_for_video(self, prompt_id):
                if self.phase == "poll":
                    raise ComfyUIVideoBackendError("poll failure")
                return {"filename": "clip.mp4"}

            def download_video(self, video_info, output_dir, output_name):
                if self.phase == "download":
                    raise ComfyUIVideoBackendError("download failure")
                raise AssertionError("unexpected successful download")

        for phase in ("queue", "poll", "download"):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                source = root / "source.png"
                source.write_bytes(b"source")
                backend = FailingBackend(
                    phase,
                    comfyui_input_dir=root / "comfy_input",
                    staging_retention=(
                        ComfyUIInputRetention.PRESERVE_ON_FAILURE
                    ),
                )

                with self.assertRaises(OperationalError) as caught:
                    backend.generate(
                        self._prepared_workflow(source),
                        root / "output",
                    )

                queued_image = backend.queued_workflows[0]["load"]["inputs"]["image"]
                self.assertEqual("EXTERNAL_SERVICE", caught.exception.context.family)
                self.assertTrue(source.exists())
                self.assertTrue((root / "comfy_input" / queued_image).exists())
                self.assertFalse(
                    (root / "output" / "video_clips_manifest.json").exists()
                )

    def test_preserve_always_keeps_staged_input_on_success_and_failure(self):
        successful_backend = self._successful_backend_class()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            success_source = root / "success.png"
            success_source.write_bytes(b"success")
            success = successful_backend(
                comfyui_input_dir=root / "success_input",
                staging_retention=ComfyUIInputRetention.PRESERVE_ALWAYS,
            )
            success.generate(
                self._prepared_workflow(success_source),
                root / "success_output",
            )
            success_relative = success.queued_workflows[0]["load"]["inputs"]["image"]
            self.assertTrue((root / "success_input" / success_relative).exists())

            class QueueFailureBackend(ComfyUIVideoBackend):
                def queue_prompt(self, workflow, client_id):
                    self.workflow = deepcopy(workflow)
                    raise ComfyUIVideoBackendError("queue failure")

            failure_source = root / "failure.png"
            failure_source.write_bytes(b"failure")
            failure = QueueFailureBackend(
                comfyui_input_dir=root / "failure_input",
                staging_retention=ComfyUIInputRetention.PRESERVE_ALWAYS,
            )
            with self.assertRaises(OperationalError):
                failure.generate(
                    self._prepared_workflow(failure_source),
                    root / "failure_output",
                )
            failure_relative = failure.workflow["load"]["inputs"]["image"]
            self.assertTrue((root / "failure_input" / failure_relative).exists())

    def test_successful_job_never_cleans_another_jobs_staged_input(self):
        successful_backend = self._successful_backend_class()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            retained_source = root / "retained.png"
            generated_source = root / "generated.png"
            retained_source.write_bytes(b"retained")
            generated_source.write_bytes(b"generated")
            backend = successful_backend(comfyui_input_dir=root / "comfy_input")
            retained = backend._stage_source_image(
                self._prepared_workflow(retained_source)
            )

            backend.generate(
                self._prepared_workflow(generated_source),
                root / "output",
            )

            self.assertTrue(retained.staged_path.exists())
            self.assertTrue(retained_source.exists())

    def test_primary_failure_does_not_run_cleanup_or_replace_its_error(self):
        class PrimaryFailureBackend(ComfyUIVideoBackend):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.cleanup_calls = 0

            def queue_prompt(self, workflow, client_id):
                raise ComfyUIVideoBackendError("primary queue failure")

            def _cleanup_after_success(self, staged_input):
                self.cleanup_calls += 1
                raise ComfyUIVideoBackendError("cleanup failure")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.png"
            source.write_bytes(b"source")
            backend = PrimaryFailureBackend(comfyui_input_dir=root / "input")

            with self.assertRaises(OperationalError) as caught:
                backend.generate(self._prepared_workflow(source), root / "output")

        self.assertEqual(0, backend.cleanup_calls)
        self.assertEqual("primary queue failure", str(caught.exception.__cause__))

    def test_cleanup_failure_after_success_is_reported(self):
        successful_backend = self._successful_backend_class()

        class CleanupFailureBackend(successful_backend):
            def _cleanup_after_success(self, staged_input):
                raise ComfyUIVideoBackendError("cleanup failure")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.png"
            source.write_bytes(b"source")

            with self.assertRaises(OperationalError) as caught:
                CleanupFailureBackend(
                    comfyui_input_dir=root / "input",
                ).generate(self._prepared_workflow(source), root / "output")

        self.assertEqual("cleanup failure", str(caught.exception.__cause__))

    @staticmethod
    def _lossless_capture_plan():
        return WanLosslessCapturePlan(
            job_id="semantic-job",
            capture_node_id="semantic-capture-node",
            output_prefix="aivc_wan_lossless/semantic-job/frame",
            expected_frame_count=2,
            width=2,
            height=1,
            fps=12,
            bit_depth=8,
        )

    def test_wait_for_lossless_capture_polls_until_its_semantic_png_batch_exists(self):
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
                            "semantic-capture-node": {
                                "images": [{}, {}],
                            },
                        },
                    },
                }

        backend = HistoryBackend()
        history_item = backend.wait_for_lossless_capture(
            "prompt-id",
            self._lossless_capture_plan(),
        )

        self.assertEqual(2, backend.calls)
        self.assertEqual(
            2,
            len(history_item["outputs"]["semantic-capture-node"]["images"]),
        )
        self.assertFalse(hasattr(backend, "timeout_seconds"))

    def test_wait_for_lossless_capture_preserves_comfyui_error_classification(self):
        class HistoryBackend(ComfyUIVideoBackend):
            def _history(self, prompt_id):
                return {
                    prompt_id: {
                        "status": {
                            "status_str": "error",
                            "messages": [
                                [
                                    "execution_error",
                                    {
                                        "node_id": "semantic-capture-node",
                                        "node_type": "SaveImage",
                                        "exception_type": "OutOfMemoryError",
                                        "exception_message": "out of memory",
                                    },
                                ],
                            ],
                        },
                    },
                }

        with self.assertRaises(ComfyUIVideoBackendError) as caught:
            HistoryBackend().wait_for_lossless_capture(
                "prompt-id",
                self._lossless_capture_plan(),
            )

        self.assertEqual("OUT_OF_MEMORY", caught.exception.category)
        self.assertEqual("semantic-capture-node", caught.exception.node_id)

    def test_wait_for_lossless_capture_rejects_success_without_capture_node(self):
        class HistoryBackend(ComfyUIVideoBackend):
            def _history(self, prompt_id):
                return {
                    prompt_id: {
                        "status": {"status_str": "success"},
                        "outputs": {},
                    },
                }

        with self.assertRaises(ComfyUIVideoBackendError) as caught:
            HistoryBackend().wait_for_lossless_capture(
                "prompt-id",
                self._lossless_capture_plan(),
            )

        self.assertEqual("EXECUTION_ERROR", caught.exception.category)
        self.assertEqual("semantic-capture-node", caught.exception.node_id)

    def test_wait_for_lossless_capture_rejects_malformed_capture_output(self):
        class HistoryBackend(ComfyUIVideoBackend):
            def _history(self, prompt_id):
                return {
                    prompt_id: {
                        "outputs": {
                            "semantic-capture-node": {"images": "not-a-batch"},
                        },
                    },
                }

        with self.assertRaises(ComfyUIVideoBackendError) as caught:
            HistoryBackend().wait_for_lossless_capture(
                "prompt-id",
                self._lossless_capture_plan(),
            )

        self.assertEqual("EXECUTION_ERROR", caught.exception.category)
        self.assertEqual("semantic-capture-node", caught.exception.node_id)

    def test_savevideo_h264_keeps_video_wait_and_download_path(self):
        class H264Backend(ComfyUIVideoBackend):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.wait_calls = 0
                self.download_calls = 0

            def queue_prompt(self, workflow, client_id):
                return "prompt-id"

            def wait_for_video(self, prompt_id):
                self.wait_calls += 1
                return {"filename": "savevideo.mp4"}

            def download_video(self, video_info, output_dir, output_name):
                self.download_calls += 1
                output_path = Path(output_dir) / output_name
                output_path.write_bytes(b"savevideo-h264")
                return output_path

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.png"
            source.write_bytes(b"source")
            backend = H264Backend(comfyui_input_dir=root / "input")

            result = backend.generate(
                self._prepared_workflow(source),
                root / "output",
                output_name="scene_001.mp4",
            )

        self.assertEqual(1, backend.wait_calls)
        self.assertEqual(1, backend.download_calls)
        self.assertEqual(".mp4", result.output_clip.suffix)


if __name__ == "__main__":
    unittest.main()
