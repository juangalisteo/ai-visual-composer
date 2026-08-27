import json
import tempfile
import unittest
from pathlib import Path

from app.modules.video_component import (
    BackendVideoPrompt,
    ComfyUIVideoAdapter,
    ComfyUIVideoAdapterError,
)


class ComfyUIVideoAdapterTest(unittest.TestCase):

    def test_injects_backend_video_prompt_into_workflow(self):
        prompt = BackendVideoPrompt(
            source_image=Path("input/video/source image.png"),
            positive_prompt="positive motion prompt",
            negative_prompt="negative motion prompt",
            motion_summary="slow camera drift",
            seed=77,
            frames=17,
            fps=8.0,
            generation_width=320,
            generation_height=320,
            steps=12,
            cfg=5.0,
            sampler="uni_pc",
            scheduler="simple",
        )

        workflow = ComfyUIVideoAdapter().adapt(
            prompt,
            output_prefix="vc1_test/clip_001",
        )

        self.assertEqual(
            "source_image.png",
            workflow.source_image_name
        )
        self.assertEqual(
            "positive motion prompt",
            workflow.workflow["6"]["inputs"]["text"]
        )
        self.assertEqual(
            "negative motion prompt",
            workflow.workflow["7"]["inputs"]["text"]
        )
        self.assertEqual(
            77,
            workflow.workflow["9"]["inputs"]["seed"]
        )
        self.assertEqual(
            12,
            workflow.workflow["9"]["inputs"]["steps"]
        )
        self.assertEqual(
            5.0,
            workflow.workflow["9"]["inputs"]["cfg"]
        )
        self.assertEqual(
            "uni_pc",
            workflow.workflow["9"]["inputs"]["sampler_name"]
        )
        self.assertEqual(
            "simple",
            workflow.workflow["9"]["inputs"]["scheduler"]
        )
        self.assertEqual(
            17,
            workflow.workflow["8"]["inputs"]["length"]
        )
        self.assertEqual(
            320,
            workflow.workflow["8"]["inputs"]["width"]
        )
        self.assertEqual(
            "vc1_test/clip_001",
            workflow.workflow["12"]["inputs"]["filename_prefix"]
        )

    def test_raises_clear_error_when_required_node_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workflow_path = Path(
                temp_dir
            ) / "workflow.json"
            workflow_path.write_text(
                json.dumps({
                    "1": {
                        "class_type": "LoadImage",
                        "inputs": {
                            "image": "source.png",
                        },
                    },
                }),
                encoding="utf-8",
            )

            prompt = BackendVideoPrompt(
                source_image=Path("source.png"),
                positive_prompt="prompt",
                negative_prompt="",
                motion_summary="motion",
            )

            with self.assertRaises(
                ComfyUIVideoAdapterError
            ):
                ComfyUIVideoAdapter(
                    workflow_path=workflow_path
                ).adapt(
                    prompt
                )


if __name__ == "__main__":
    unittest.main()
