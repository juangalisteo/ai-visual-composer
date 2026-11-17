from copy import deepcopy
import json
from pathlib import Path
import re
import uuid

from app.modules.video_component.contracts import (
    WanIntermediateOutput,
    WanWorkflowBinding,
    WanWorkflowInputRole,
    WanWorkflowNodeRole,
    WanLosslessCapturePlan,
)
from app.modules.video_component.models import (
    BackendVideoPrompt,
    ComfyUIVideoAdapterError,
    ComfyUIVideoWorkflow,
)


class ComfyUIVideoAdapter:
    _WORKFLOW_BINDING = WanWorkflowBinding(
        node_roles=(
            WanWorkflowNodeRole("unet", "UNETLoader"),
            WanWorkflowNodeRole("model_sampling", "ModelSamplingSD3"),
            WanWorkflowNodeRole("clip_loader", "CLIPLoader"),
            WanWorkflowNodeRole("vae_loader", "VAELoader"),
            WanWorkflowNodeRole("load_image", "LoadImage"),
            WanWorkflowNodeRole("video_latent", "Wan22ImageToVideoLatent"),
            WanWorkflowNodeRole("sampler", "KSampler"),
            WanWorkflowNodeRole("vae_decode", "VAEDecode"),
            WanWorkflowNodeRole("create_video", "CreateVideo"),
            WanWorkflowNodeRole("save_video", "SaveVideo"),
        ),
        positive_prompt=WanWorkflowInputRole(
            "sampler",
            "positive",
            "CLIPTextEncode",
        ),
        negative_prompt=WanWorkflowInputRole(
            "sampler",
            "negative",
            "CLIPTextEncode",
        ),
    )

    def __init__(
        self,
        workflow_path=(
            "config/comfyui_wan22_ti2v_i2v_workflow_api.json"
        ),
    ):
        self.workflow_path = Path(workflow_path)

    def adapt(
        self,
        backend_prompt: BackendVideoPrompt,
        *,
        output_prefix="vc1_video/clip_001",
    ) -> ComfyUIVideoWorkflow:
        workflow = deepcopy(self._load_workflow())
        nodes = self._resolve_workflow_nodes(workflow)

        source_image_name = _safe_image_name(backend_prompt.source_image)
        self._inject_values(
            nodes["load_image"],
            {"image": source_image_name},
        )
        self._inject_prompts(nodes, backend_prompt)
        self._inject_values(
            nodes["sampler"],
            {
                "seed": backend_prompt.seed,
                "steps": backend_prompt.steps,
                "cfg": backend_prompt.cfg,
                "sampler_name": backend_prompt.sampler,
                "scheduler": backend_prompt.scheduler,
            },
        )
        self._inject_values(
            nodes["video_latent"],
            {
                "width": backend_prompt.generation_width,
                "height": backend_prompt.generation_height,
                "length": backend_prompt.frames,
            },
        )
        capture = None
        if (
            backend_prompt.intermediate_output
            is WanIntermediateOutput.LOSSLESS_FFV1
        ):
            capture = self._inject_lossless_capture(
                workflow=workflow,
                vae_decode_node_id=nodes["vae_decode_id"],
                backend_prompt=backend_prompt,
            )
            # The versioned base graph remains validated with its H.264
            # branch, but lossless execution ends at the semantic SaveImage
            # output.  CreateVideo is intentionally retained as an orphaned
            # base node; only its SaveVideo consumer is removed.
            del workflow[nodes["save_video_id"]]
        else:
            self._inject_values(
                nodes["create_video"],
                {"fps": backend_prompt.fps},
            )
            self._inject_values(
                nodes["save_video"],
                {"filename_prefix": output_prefix},
            )

        return ComfyUIVideoWorkflow(
            workflow=workflow,
            backend_prompt=backend_prompt,
            source_image_name=source_image_name,
            output_prefix=output_prefix,
            lossless_capture=capture,
        )

    def _load_workflow(self):
        if not self.workflow_path.exists():
            raise ComfyUIVideoAdapterError(
                "No existe el workflow de vídeo ComfyUI: "
                f"{self.workflow_path}"
            )
        return json.loads(self.workflow_path.read_text(encoding="utf-8"))

    def _resolve_workflow_nodes(self, workflow):
        if not isinstance(workflow, dict):
            self._invalid_workflow("El documento raíz debe ser un objeto.")

        nodes = {}
        for role in self._WORKFLOW_BINDING.node_roles:
            matches = [
                (node_id, node)
                for node_id, node in workflow.items()
                if isinstance(node, dict)
                and node.get("class_type") == role.class_type
            ]
            if len(matches) != 1:
                self._invalid_workflow(
                    f"{role.class_type} requiere exactamente una coincidencia "
                    f"y se encontraron {len(matches)}."
                )
            nodes[role.role] = matches[0][1]
            nodes[f"{role.role}_id"] = matches[0][0]

        sampler = nodes["sampler"]
        positive_id, positive_node = self._resolve_prompt_producer(
            workflow,
            sampler,
            self._WORKFLOW_BINDING.positive_prompt,
        )
        negative_id, negative_node = self._resolve_prompt_producer(
            workflow,
            sampler,
            self._WORKFLOW_BINDING.negative_prompt,
        )
        if positive_id == negative_id:
            self._invalid_workflow(
                "KSampler positive y negative deben usar productores distintos."
            )
        nodes["positive_prompt"] = positive_node
        nodes["negative_prompt"] = negative_node
        return nodes

    def _inject_lossless_capture(self, *, workflow, vae_decode_node_id, backend_prompt):
        job_id = uuid.uuid4().hex
        capture_node_id = f"aivc_lossless_capture_{job_id}"
        if capture_node_id in workflow:
            self._invalid_workflow("La identidad de captura lossless ya existe.")
        plan = WanLosslessCapturePlan(
            job_id=job_id,
            capture_node_id=capture_node_id,
            output_prefix=f"aivc_wan_lossless/{job_id}/frame",
            expected_frame_count=backend_prompt.frames,
            width=backend_prompt.generation_width,
            height=backend_prompt.generation_height,
            fps=backend_prompt.fps,
            bit_depth=8,
        )
        workflow[capture_node_id] = {
            "class_type": "SaveImage",
            "inputs": {
                "images": [vae_decode_node_id, 0],
                "filename_prefix": plan.output_prefix,
            },
        }
        return plan

    def _resolve_prompt_producer(self, workflow, sampler, binding):
        inputs = sampler.get("inputs")
        if not isinstance(inputs, dict):
            self._invalid_workflow("KSampler debe declarar un objeto inputs.")
        reference = inputs.get(binding.input_name)
        if (
            not isinstance(reference, (list, tuple))
            or len(reference) != 2
            or not isinstance(reference[0], str)
        ):
            self._invalid_workflow(
                f"KSampler.{binding.input_name} debe referenciar un nodo ComfyUI."
            )
        producer_id = reference[0]
        producer = workflow.get(producer_id)
        if not isinstance(producer, dict):
            self._invalid_workflow(
                f"KSampler.{binding.input_name} referencia el nodo inexistente "
                f"{producer_id}."
            )
        if producer.get("class_type") != binding.producer_class_type:
            self._invalid_workflow(
                f"KSampler.{binding.input_name} debe provenir de "
                f"{binding.producer_class_type}."
            )
        return producer_id, producer

    @staticmethod
    def _invalid_workflow(detail):
        raise ComfyUIVideoAdapterError(
            "Workflow ComfyUI I2V inválido: " + detail
        )

    @staticmethod
    def _inject_values(node, values):
        node.setdefault("inputs", {}).update(values)

    def _inject_prompts(self, nodes, backend_prompt):
        self._inject_values(
            nodes["positive_prompt"],
            {"text": backend_prompt.positive_prompt},
        )
        self._inject_values(
            nodes["negative_prompt"],
            {"text": backend_prompt.negative_prompt},
        )


def _safe_image_name(source_image):
    source_path = Path(source_image)
    stem = re.sub(
        r"[^A-Za-z0-9_.-]+",
        "_",
        source_path.stem,
    ).strip("._")
    suffix = source_path.suffix.lower() or ".png"
    return f"{stem or 'source'}{suffix}"
