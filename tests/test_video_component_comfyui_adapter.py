from copy import deepcopy
import json
import tempfile
import unittest
from pathlib import Path

from app.modules.video_component import (
    BackendVideoPrompt,
    ComfyUIVideoAdapter,
    ComfyUIVideoAdapterError,
    WanIntermediateOutput,
)


class ComfyUIVideoAdapterTest(unittest.TestCase):

    @staticmethod
    def _prompt(intermediate_output=WanIntermediateOutput.SAVEVIDEO_H264):
        return BackendVideoPrompt(
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
            intermediate_output=intermediate_output,
        )

    @staticmethod
    def _official_workflow():
        return json.loads(
            Path(
                "config/comfyui_wan22_ti2v_i2v_workflow_api.json"
            ).read_text(encoding="utf-8")
        )

    def _adapt_custom_workflow(self, workflow):
        with tempfile.TemporaryDirectory() as temp_dir:
            workflow_path = Path(temp_dir) / "workflow.json"
            workflow_path.write_text(
                json.dumps(workflow),
                encoding="utf-8",
            )
            return ComfyUIVideoAdapter(
                workflow_path=workflow_path
            ).adapt(
                self._prompt(),
                output_prefix="vc1_test/clip_001",
            )

    def test_injects_backend_video_prompt_into_workflow(self):
        prompt = self._prompt()

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
            320,
            workflow.workflow["8"]["inputs"]["height"]
        )
        self.assertEqual(
            8.0,
            workflow.workflow["11"]["inputs"]["fps"]
        )
        self.assertEqual(
            "vc1_test/clip_001",
            workflow.workflow["12"]["inputs"]["filename_prefix"]
        )

    def test_lossless_intermediate_output_is_bound_to_vaedecode_without_numeric_ids(self):
        workflow = self._official_workflow()
        id_map = {node_id: f"node-{node_id}" for node_id in workflow}
        reordered = {}
        for node_id, node in workflow.items():
            node = deepcopy(node)
            for value in node.get("inputs", {}).values():
                if isinstance(value, list) and len(value) == 2 and value[0] in id_map:
                    value[0] = id_map[value[0]]
            reordered[id_map[node_id]] = node
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "workflow.json"
            path.write_text(json.dumps(reordered), encoding="utf-8")
            adapted = ComfyUIVideoAdapter(workflow_path=path).adapt(
                self._prompt(WanIntermediateOutput.LOSSLESS_FFV1),
            )

        capture = adapted.lossless_capture
        self.assertIsNotNone(capture)
        self.assertEqual(17, capture.expected_frame_count)
        self.assertEqual([id_map["10"], 0], adapted.workflow[capture.capture_node_id]["inputs"]["images"])
        self.assertEqual(capture.output_prefix, adapted.workflow[capture.capture_node_id]["inputs"]["filename_prefix"])
        self.assertFalse(
            any(
                node.get("class_type") == "SaveVideo"
                for node in adapted.workflow.values()
                if isinstance(node, dict)
            )
        )
        self.assertEqual(
            "CreateVideo",
            adapted.workflow[id_map["11"]]["class_type"],
        )
        self.assertFalse(
            any(
                value[0] == id_map["11"]
                for node in adapted.workflow.values()
                if isinstance(node, dict)
                for value in node.get("inputs", {}).values()
                if isinstance(value, list) and len(value) == 2
            )
        )

    def test_savevideo_intermediate_output_does_not_add_lossless_capture(self):
        adapted = ComfyUIVideoAdapter().adapt(
            self._prompt(WanIntermediateOutput.SAVEVIDEO_H264),
        )

        self.assertIsNone(adapted.lossless_capture)
        self.assertEqual(
            "SaveVideo",
            adapted.workflow["12"]["class_type"],
        )
        self.assertEqual(
            "vc1_video/clip_001",
            adapted.workflow["12"]["inputs"]["filename_prefix"],
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

    def test_reordered_numeric_ids_keep_the_official_payload_equivalent(self):
        workflow = self._official_workflow()
        id_map = {
            node_id: str(100 + int(node_id) * 17)
            for node_id in workflow
        }
        reordered = {}
        for node_id, node in workflow.items():
            node = deepcopy(node)
            for value in node.get("inputs", {}).values():
                if (
                    isinstance(value, list)
                    and len(value) == 2
                    and value[0] in id_map
                ):
                    value[0] = id_map[value[0]]
            reordered[id_map[node_id]] = node

        adapted = self._adapt_custom_workflow(reordered)
        sampler = adapted.workflow[id_map["9"]]["inputs"]
        latent = adapted.workflow[id_map["8"]]["inputs"]
        video = adapted.workflow[id_map["11"]]["inputs"]
        output = adapted.workflow[id_map["12"]]["inputs"]

        self.assertEqual("source_image.png", adapted.source_image_name)
        self.assertEqual("positive motion prompt", adapted.workflow[id_map["6"]]["inputs"]["text"])
        self.assertEqual("negative motion prompt", adapted.workflow[id_map["7"]]["inputs"]["text"])
        self.assertEqual(77, sampler["seed"])
        self.assertEqual(12, sampler["steps"])
        self.assertEqual(5.0, sampler["cfg"])
        self.assertEqual("uni_pc", sampler["sampler_name"])
        self.assertEqual("simple", sampler["scheduler"])
        self.assertEqual(320, latent["width"])
        self.assertEqual(320, latent["height"])
        self.assertEqual(17, latent["length"])
        self.assertEqual(8.0, video["fps"])
        self.assertEqual("vc1_test/clip_001", output["filename_prefix"])

    def test_prompt_nodes_are_resolved_by_ksampler_connections_not_order(self):
        workflow = self._official_workflow()
        inverted = {
            "7": workflow["7"],
            "6": workflow["6"],
            **{
                node_id: node
                for node_id, node in workflow.items()
                if node_id not in {"6", "7"}
            },
        }

        adapted = self._adapt_custom_workflow(inverted)

        self.assertEqual(
            "positive motion prompt",
            adapted.workflow["6"]["inputs"]["text"],
        )
        self.assertEqual(
            "negative motion prompt",
            adapted.workflow["7"]["inputs"]["text"],
        )

    def test_missing_singleton_is_rejected_before_adaptation(self):
        workflow = self._official_workflow()
        del workflow["1"]

        with self.assertRaisesRegex(
            ComfyUIVideoAdapterError,
            "UNETLoader requiere exactamente una coincidencia",
        ):
            self._adapt_custom_workflow(workflow)

    def test_duplicate_singleton_is_rejected_before_adaptation(self):
        workflow = self._official_workflow()
        workflow["duplicate-load-image"] = deepcopy(workflow["5"])

        with self.assertRaisesRegex(
            ComfyUIVideoAdapterError,
            "LoadImage requiere exactamente una coincidencia",
        ):
            self._adapt_custom_workflow(workflow)

    def test_prompt_producer_must_be_clip_text_encode(self):
        workflow = self._official_workflow()
        workflow["7"]["class_type"] = "OtherTextEncode"

        with self.assertRaisesRegex(
            ComfyUIVideoAdapterError,
            "KSampler.negative debe provenir de CLIPTextEncode",
        ):
            self._adapt_custom_workflow(workflow)

    def test_missing_prompt_producer_reference_is_rejected(self):
        workflow = self._official_workflow()
        workflow["9"]["inputs"]["positive"] = ["not-a-node", 0]

        with self.assertRaisesRegex(
            ComfyUIVideoAdapterError,
            "KSampler.positive referencia el nodo inexistente not-a-node",
        ):
            self._adapt_custom_workflow(workflow)

    def test_same_prompt_producer_for_positive_and_negative_is_rejected(self):
        workflow = self._official_workflow()
        workflow["9"]["inputs"]["negative"] = ["6", 0]

        with self.assertRaisesRegex(
            ComfyUIVideoAdapterError,
            "positive y negative deben usar productores distintos",
        ):
            self._adapt_custom_workflow(workflow)


if __name__ == "__main__":
    unittest.main()
