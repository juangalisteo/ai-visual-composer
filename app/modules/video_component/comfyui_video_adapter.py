from copy import deepcopy
from pathlib import Path
import json
import re

from app.modules.video_component.models import (
    BackendVideoPrompt,
    ComfyUIVideoAdapterError,
    ComfyUIVideoWorkflow,
)


class ComfyUIVideoAdapter:
    REQUIRED_NODE_TYPES = {
        "UNETLoader",
        "ModelSamplingSD3",
        "CLIPLoader",
        "VAELoader",
        "LoadImage",
        "CLIPTextEncode",
        "Wan22ImageToVideoLatent",
        "KSampler",
        "VAEDecode",
        "CreateVideo",
        "SaveVideo",
    }

    def __init__(
        self,
        workflow_path=(
            "config/comfyui_wan22_ti2v_i2v_workflow_api.json"
        )
    ):
        self.workflow_path = Path(
            workflow_path
        )

    def adapt(
        self,
        backend_prompt: BackendVideoPrompt,
        *,
        output_prefix="vc1_video/clip_001"
    ) -> ComfyUIVideoWorkflow:
        workflow = self._load_workflow()
        workflow = deepcopy(
            workflow
        )
        self._validate_workflow(
            workflow
        )

        source_image_name = _safe_image_name(
            backend_prompt.source_image
        )

        self._inject_by_type(
            workflow,
            "LoadImage",
            {
                "image": source_image_name,
            },
        )
        self._inject_prompts(
            workflow,
            backend_prompt
        )
        self._inject_by_type(
            workflow,
            "KSampler",
            {
                "seed": backend_prompt.seed,
                "steps": backend_prompt.steps,
                "cfg": backend_prompt.cfg,
                "sampler_name": backend_prompt.sampler,
                "scheduler": backend_prompt.scheduler,
            },
        )
        self._inject_by_type(
            workflow,
            "Wan22ImageToVideoLatent",
            {
                "width": backend_prompt.generation_width,
                "height": backend_prompt.generation_height,
                "length": backend_prompt.frames,
            },
        )
        self._inject_by_type(
            workflow,
            "CreateVideo",
            {
                "fps": backend_prompt.fps,
            },
        )
        self._inject_by_type(
            workflow,
            "SaveVideo",
            {
                "filename_prefix": output_prefix,
            },
        )

        return ComfyUIVideoWorkflow(
            workflow=workflow,
            backend_prompt=backend_prompt,
            source_image_name=source_image_name,
            output_prefix=output_prefix,
        )

    def _load_workflow(
        self
    ):
        if not self.workflow_path.exists():
            raise ComfyUIVideoAdapterError(
                "No existe el workflow de vídeo ComfyUI: "
                f"{self.workflow_path}"
            )

        return json.loads(
            self.workflow_path.read_text(
                encoding="utf-8"
            )
        )

    def _validate_workflow(
        self,
        workflow
    ):
        available = {
            node.get(
                "class_type",
                ""
            )
            for node in workflow.values()
        }
        missing = sorted(
            self.REQUIRED_NODE_TYPES - available
        )
        if missing:
            raise ComfyUIVideoAdapterError(
                "Workflow ComfyUI I2V incompleto. "
                "Faltan nodos: "
                + ", ".join(
                    missing
                )
            )

        if len(
            [
                node
                for node in workflow.values()
                if node.get(
                    "class_type"
                ) == "CLIPTextEncode"
            ]
        ) < 2:
            raise ComfyUIVideoAdapterError(
                "Workflow ComfyUI I2V incompleto. "
                "Se requieren dos nodos CLIPTextEncode."
            )

    def _inject_by_type(
        self,
        workflow,
        class_type,
        values
    ):
        for node in workflow.values():
            if node.get(
                "class_type"
            ) == class_type:
                node.setdefault(
                    "inputs",
                    {}
                ).update(
                    values
                )
                return

        raise ComfyUIVideoAdapterError(
            "No se encontró el nodo requerido "
            f"{class_type} en el workflow I2V."
        )

    def _inject_prompts(
        self,
        workflow,
        backend_prompt
    ):
        text_nodes = [
            node
            for node in workflow.values()
            if node.get(
                "class_type"
            ) == "CLIPTextEncode"
        ]
        text_nodes[0].setdefault(
            "inputs",
            {}
        )["text"] = backend_prompt.positive_prompt
        text_nodes[1].setdefault(
            "inputs",
            {}
        )["text"] = backend_prompt.negative_prompt


def _safe_image_name(
    source_image
):
    source_path = Path(
        source_image
    )
    stem = re.sub(
        r"[^A-Za-z0-9_.-]+",
        "_",
        source_path.stem
    ).strip(
        "._"
    )
    suffix = source_path.suffix.lower() or ".png"
    return f"{stem or 'source'}{suffix}"
