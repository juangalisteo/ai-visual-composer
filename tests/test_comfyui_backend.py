import copy
import inspect
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.modules.images.backends import ComfyUIBackend, ComfyUIBackendError
from app.modules.images.image_builder import ImageBuilder
from app.shared.operational_error import OperationalError


class MockResponse:

    def __init__(
        self,
        payload
    ):
        self.payload = payload

    def __enter__(
        self
    ):
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        traceback
    ):
        return False

    def read(
        self
    ):
        return self.payload


class RecordingBackend:

    def __init__(
        self,
        image_path
    ):
        self.image_path = image_path
        self.calls = []

    def generate(
        self,
        prompt,
        scene_number,
        output_dir,
        width,
        height
    ):
        self.calls.append({
            "prompt": prompt,
            "scene_number": scene_number,
            "output_dir": output_dir,
            "width": width,
            "height": height
        })
        output_dir.mkdir(
            parents=True,
            exist_ok=True
        )
        self.image_path.write_bytes(
            b"image-bytes"
        )

        return self.image_path


class ComfyUIBackendTest(unittest.TestCase):

    def test_generate_adapts_backend_failure_with_safe_context(self):
        class FailingBackend(ComfyUIBackend):
            def _generate(self, **kwargs):
                raise ComfyUIBackendError(
                    "backend failure",
                    category="OUT_OF_MEMORY",
                    prompt_id="prompt-123",
                    node_id="30",
                    node_type="ModelSamplingFlux",
                    exception_type="OutOfMemoryError",
                    status="error",
                )

        with self.assertRaises(OperationalError) as context:
            FailingBackend(workflow_path="config/test-workflow.json").generate(
                prompt="must not enter metadata",
                scene_number=7,
                output_dir=Path("output/images"),
                width=1080,
                height=1920,
            )

        error = context.exception
        self.assertEqual("EXTERNAL_SERVICE", error.context.family)
        self.assertEqual("comfyui", error.context.technical_metadata["service"])
        self.assertEqual("image", error.context.technical_metadata["backend"])
        self.assertEqual("prompt-123", error.context.technical_metadata["prompt_id"])
        self.assertEqual("30", error.context.technical_metadata["node_id"])
        self.assertEqual("OUT_OF_MEMORY", error.context.technical_metadata["category"])
        self.assertNotIn("must not enter metadata", str(error.context.technical_metadata))
        self.assertIsInstance(error.__cause__, ComfyUIBackendError)

    def test_inject_prompt_matches_legacy_behavior(self):
        workflow = self._workflow()
        result = ComfyUIBackend().inject_prompt(
            workflow=workflow,
            prompt="final prompt"
        )

        self.assertIs(
            workflow,
            result
        )
        self.assertEqual(
            "final prompt",
            result["6"]["inputs"]["text"]
        )
        self.assertEqual(
            "untouched",
            result["99"]["inputs"]["text"]
        )

    def test_inject_dimensions_matches_legacy_behavior(self):
        workflow = self._workflow()
        result = ComfyUIBackend().inject_dimensions(
            workflow=workflow,
            width=640,
            height=360
        )

        self.assertEqual(
            640,
            result["27"]["inputs"]["width"]
        )
        self.assertEqual(
            360,
            result["27"]["inputs"]["height"]
        )
        self.assertEqual(
            640,
            result["30"]["inputs"]["width"]
        )
        self.assertEqual(
            360,
            result["30"]["inputs"]["height"]
        )

    def test_workflow_after_injection_is_structurally_identical(self):
        workflow = self._workflow()
        expected = copy.deepcopy(
            workflow
        )
        expected["6"]["inputs"]["text"] = "final prompt"
        expected["27"]["inputs"]["width"] = 640
        expected["27"]["inputs"]["height"] = 360
        expected["30"]["inputs"]["width"] = 640
        expected["30"]["inputs"]["height"] = 360

        backend = ComfyUIBackend()
        workflow = backend.inject_prompt(
            workflow,
            "final prompt"
        )
        workflow = backend.inject_dimensions(
            workflow,
            640,
            360
        )

        self.assertEqual(
            expected,
            workflow
        )

    def test_queue_prompt_uses_same_endpoint_payload_and_headers(self):
        requests = []

        def fake_urlopen(
            request
        ):
            requests.append(
                request
            )
            return MockResponse(
                json.dumps({
                    "prompt_id": "abc"
                }).encode(
                    "utf-8"
                )
            )

        workflow = self._workflow()

        with patch(
            "app.modules.images.backends.comfyui_backend.urllib.request.urlopen",
            side_effect=fake_urlopen
        ):
            prompt_id = ComfyUIBackend(
                comfyui_url="http://localhost:8188"
            ).queue_prompt(
                workflow=workflow,
                client_id="client-1"
            )

        self.assertEqual(
            "abc",
            prompt_id
        )
        self.assertEqual(
            "http://localhost:8188/prompt",
            requests[0].full_url
        )
        self.assertEqual(
            {
                "prompt": workflow,
                "client_id": "client-1"
            },
            json.loads(
                requests[0].data.decode(
                    "utf-8"
                )
            )
        )
        self.assertEqual(
            "application/json",
            requests[0].get_header(
                "Content-type"
            )
        )

    def test_wait_for_image_preserves_history_polling(self):
        calls = []

        def fake_urlopen(
            url
        ):
            calls.append(
                url
            )
            if len(
                calls
            ) == 1:
                return MockResponse(
                    json.dumps({}).encode(
                        "utf-8"
                    )
                )

            return MockResponse(
                json.dumps({
                    "abc": {
                        "outputs": {
                            "9": {
                                "images": [
                                    {
                                        "filename": "image.png",
                                        "subfolder": "",
                                        "type": "output"
                                    }
                                ]
                            }
                        }
                    }
                }).encode(
                    "utf-8"
                )
            )

        with patch(
            "app.modules.images.backends.comfyui_backend.urllib.request.urlopen",
            side_effect=fake_urlopen
        ), patch(
            "app.modules.images.backends.comfyui_backend.time.sleep"
        ) as sleep:
            image_info = ComfyUIBackend(
                comfyui_url="http://localhost:8188"
            ).wait_for_image(
                "abc"
            )

        self.assertEqual(
            2,
            len(
                calls
            )
        )
        self.assertEqual(
            "http://localhost:8188/history/abc",
            calls[0]
        )
        sleep.assert_called_once_with(
            1
        )
        self.assertEqual(
            "image.png",
            image_info["filename"]
        )

    def test_download_image_preserves_url_path_bytes_and_result(self):
        urls = []

        def fake_urlopen(
            url
        ):
            urls.append(
                url
            )
            return MockResponse(
                b"image-bytes"
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(
                temp_dir
            )

            with patch(
                "app.modules.images.backends.comfyui_backend.urllib.request.urlopen",
                side_effect=fake_urlopen
            ):
                image_path = ComfyUIBackend(
                    comfyui_url="http://localhost:8188"
                ).download_image(
                    image_info={
                        "filename": "image.png",
                        "subfolder": "folder",
                        "type": "output"
                    },
                    scene_number=2,
                    output_dir=output_dir
                )

            self.assertEqual(
                "http://localhost:8188/view?filename=image.png&subfolder=folder&type=output",
                urls[0]
            )
            self.assertEqual(
                output_dir / "scene_002.png",
                image_path
            )
            self.assertEqual(
                b"image-bytes",
                image_path.read_bytes()
            )

    def test_http_errors_preserve_runtime_errors(self):
        backend = ComfyUIBackend()

        with patch(
            "app.modules.images.backends.comfyui_backend.urllib.request.urlopen",
            side_effect=OSError("network")
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "No se pudo enviar el workflow a ComfyUI."
            ):
                backend.queue_prompt(
                    workflow=self._workflow(),
                    client_id="client-1"
                )

        with patch(
            "app.modules.images.backends.comfyui_backend.urllib.request.urlopen",
            side_effect=OSError("network")
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "No se pudo consultar el estado de ComfyUI."
            ):
                backend.wait_for_image(
                    "abc"
                )

    def test_comfyui_error_status_preserves_runtime_error(self):
        with patch(
            "app.modules.images.backends.comfyui_backend.urllib.request.urlopen",
            return_value=MockResponse(
                json.dumps({
                    "abc": {
                        "outputs": {},
                        "status": {
                            "status_str": "error"
                        }
                    }
                }).encode(
                    "utf-8"
                )
            )
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "ComfyUI devolvió un error durante la generación."
            ):
                ComfyUIBackend().wait_for_image(
                    "abc"
                )

    def test_comfyui_prompt_too_long_error_is_classified(self):
        with patch(
            "app.modules.images.backends.comfyui_backend.urllib.request.urlopen",
            return_value=MockResponse(
                json.dumps({
                    "abc": {
                        "outputs": {},
                        "status": {
                            "status_str": "error",
                            "messages": (
                                (
                                    "execution_error",
                                    {
                                        "node_id": "6",
                                        "node_type": "CLIPTextEncode",
                                        "exception_type": "IndexError",
                                        "exception_message": (
                                            "Token indices sequence length is "
                                            "longer than the specified maximum "
                                            "sequence length for this model "
                                            "(4682 > 512)"
                                        ),
                                    },
                                ),
                            ),
                        },
                    },
                }).encode(
                    "utf-8"
                )
            )
        ):
            with self.assertRaises(
                ComfyUIBackendError
            ) as context:
                ComfyUIBackend().wait_for_image(
                    "abc"
                )

        self.assertEqual(
            context.exception.category,
            "PROMPT_TOO_LONG",
        )
        self.assertEqual(
            context.exception.node_id,
            "6",
        )
        self.assertEqual(
            context.exception.node_type,
            "CLIPTextEncode",
        )
        self.assertIn(
            "4682 > 512",
            context.exception.exception_message,
        )

    def test_comfyui_out_of_memory_error_is_classified(self):
        with patch(
            "app.modules.images.backends.comfyui_backend.urllib.request.urlopen",
            return_value=MockResponse(
                json.dumps({
                    "abc": {
                        "outputs": {},
                        "status": {
                            "status_str": "error",
                            "messages": (
                                (
                                    "execution_error",
                                    {
                                        "node_id": "30",
                                        "node_type": "ModelSamplingFlux",
                                        "exception_type": "OutOfMemoryError",
                                        "exception_message": "CUDA out of memory",
                                    },
                                ),
                            ),
                        },
                    },
                }).encode(
                    "utf-8"
                )
            )
        ):
            with self.assertRaises(
                ComfyUIBackendError
            ) as context:
                ComfyUIBackend().wait_for_image(
                    "abc"
                )

        self.assertEqual(
            context.exception.category,
            "OUT_OF_MEMORY",
        )
        self.assertEqual(
            context.exception.node_id,
            "30",
        )

    def test_generate_sends_identical_injected_payload_and_downloads(self):
        requests = []

        def fake_urlopen(
            request
        ):
            requests.append(
                request
            )

            if hasattr(
                request,
                "full_url"
            ):
                return MockResponse(
                    json.dumps({
                        "prompt_id": "abc"
                    }).encode(
                        "utf-8"
                    )
                )

            if request.endswith(
                "/history/abc"
            ):
                return MockResponse(
                    json.dumps({
                        "abc": {
                            "outputs": {
                                "9": {
                                    "images": [
                                        {
                                            "filename": "image.png",
                                            "subfolder": "",
                                            "type": "output"
                                        }
                                    ]
                                }
                            }
                        }
                    }).encode(
                        "utf-8"
                    )
                )

            return MockResponse(
                b"image-bytes"
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            workflow_path = root / "workflow.json"
            workflow_path.write_text(
                json.dumps(
                    self._workflow()
                ),
                encoding="utf-8"
            )
            output_dir = root / "images"
            output_dir.mkdir()

            with patch(
                "app.modules.images.backends.comfyui_backend.uuid.uuid4",
                return_value="client-1"
            ), patch(
                "app.modules.images.backends.comfyui_backend.urllib.request.urlopen",
                side_effect=fake_urlopen
            ):
                image_path = ComfyUIBackend(
                    comfyui_url="http://localhost:8188",
                    workflow_path=workflow_path
                ).generate(
                    prompt="final prompt",
                    scene_number=1,
                    output_dir=output_dir,
                    width=640,
                    height=360
                )

            payload = json.loads(
                requests[0].data.decode(
                    "utf-8"
                )
            )

            self.assertEqual(
                "client-1",
                payload["client_id"]
            )
            self.assertEqual(
                "final prompt",
                payload["prompt"]["6"]["inputs"]["text"]
            )
            self.assertEqual(
                640,
                payload["prompt"]["27"]["inputs"]["width"]
            )
            self.assertEqual(
                360,
                payload["prompt"]["30"]["inputs"]["height"]
            )
            self.assertEqual(
                output_dir / "scene_001.png",
                image_path
            )

    def test_image_builder_delegates_generation_to_backend(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            image_path = root / "images" / "scene_001.png"
            backend = RecordingBackend(
                image_path=image_path
            )
            builder = ImageBuilder(
                backend=backend
            )

            result = builder._generate_image(
                prompt="final prompt",
                scene_number=1,
                output_dir=root / "images",
                width=640,
                height=360
            )

        self.assertEqual(
            image_path,
            result
        )
        self.assertEqual(
            [
                {
                    "prompt": "final prompt",
                    "scene_number": 1,
                    "output_dir": image_path.parent,
                    "width": 640,
                    "height": 360
                }
            ],
            backend.calls
        )

    def test_backend_has_no_creative_or_manifest_dependencies(self):
        source = inspect.getsource(
            ComfyUIBackend
        )

        for forbidden in (
            "VisualDirector",
            "ImagePromptSystem",
            "Storyboard",
            "VisualBrief",
            "Narrative",
            "Intention",
            "manifest",
            "GenerationResult"
        ):
            with self.subTest(
                forbidden=forbidden
            ):
                self.assertNotIn(
                    forbidden,
                    source
                )

    def _workflow(
        self
    ):
        return {
            "6": {
                "inputs": {
                    "text": "old prompt",
                    "clip": [
                        "11",
                        0
                    ]
                },
                "class_type": "CLIPTextEncode"
            },
            "27": {
                "inputs": {
                    "width": 1024,
                    "height": 1024,
                    "batch_size": 1
                },
                "class_type": "EmptySD3LatentImage"
            },
            "30": {
                "inputs": {
                    "width": 1024,
                    "height": 1024
                },
                "class_type": "ModelSamplingFlux"
            },
            "99": {
                "inputs": {
                    "text": "untouched"
                },
                "class_type": "OtherNode"
            }
        }


if __name__ == "__main__":
    unittest.main()
