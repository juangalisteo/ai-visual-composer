from pathlib import Path
import json
import time
import urllib.parse
import urllib.request
import uuid


class ComfyUIBackendError(RuntimeError):
    def __init__(
        self,
        message,
        *,
        category="UNKNOWN_BACKEND_ERROR",
        prompt_id="",
        node_id="",
        node_type="",
        exception_type="",
        exception_message="",
        status="",
    ):
        self.category = category
        self.prompt_id = prompt_id
        self.node_id = node_id
        self.node_type = node_type
        self.exception_type = exception_type
        self.exception_message = exception_message
        self.status = status
        super().__init__(
            message
        )


class ComfyUIBackend:

    def __init__(
        self,
        comfyui_url="http://127.0.0.1:8188",
        workflow_path="config/comfyui_flux_workflow_api.json"
    ):
        self.comfyui_url = comfyui_url
        self.workflow_path = Path(
            workflow_path
        )

    def generate(
        self,
        prompt,
        scene_number,
        output_dir,
        width,
        height
    ):
        workflow = json.loads(
            self.workflow_path.read_text(
                encoding="utf-8"
            )
        )

        workflow = self.inject_prompt(
            workflow,
            prompt
        )

        workflow = self.inject_dimensions(
            workflow,
            width,
            height
        )

        client_id = str(
            uuid.uuid4()
        )

        prompt_id = self.queue_prompt(
            workflow,
            client_id
        )

        image_info = self.wait_for_image(
            prompt_id
        )

        return self.download_image(
            image_info=image_info,
            scene_number=scene_number,
            output_dir=output_dir
        )

    def inject_dimensions(
        self,
        workflow,
        width,
        height
    ):
        latent_updated = False
        sampling_updated = False

        for node in workflow.values():
            class_type = node.get(
                "class_type",
                ""
            )

            inputs = node.get(
                "inputs",
                {}
            )

            if class_type == "EmptySD3LatentImage":
                inputs["width"] = width
                inputs["height"] = height
                latent_updated = True

            if class_type == "ModelSamplingFlux":
                inputs["width"] = width
                inputs["height"] = height
                sampling_updated = True

        if not latent_updated:
            raise ValueError(
                "No se encontro el nodo "
                "EmptySD3LatentImage "
                "en el workflow de ComfyUI."
            )

        if not sampling_updated:
            raise ValueError(
                "No se encontro el nodo "
                "ModelSamplingFlux "
                "en el workflow de ComfyUI."
            )

        return workflow

    def queue_prompt(
        self,
        workflow,
        client_id
    ):
        payload = json.dumps({
            "prompt": workflow,
            "client_id": client_id
        }).encode(
            "utf-8"
        )

        request = urllib.request.Request(
            f"{self.comfyui_url}/prompt",
            data=payload,
            headers={
                "Content-Type": "application/json"
            }
        )

        try:
            with urllib.request.urlopen(
                request
            ) as response:
                result = json.loads(
                    response.read()
                )

        except Exception as error:
            raise ComfyUIBackendError(
                "No se pudo enviar el workflow a ComfyUI.",
                category="CONNECTION_ERROR",
                exception_type=type(
                    error
                ).__name__,
                exception_message=str(
                    error
                ),
            ) from error

        if "prompt_id" not in result:
            raise ComfyUIBackendError(
                "ComfyUI no devolvio prompt_id.",
                category="INPUT_VALIDATION_ERROR",
            )

        return result["prompt_id"]

    def wait_for_image(
        self,
        prompt_id
    ):
        while True:
            try:
                with urllib.request.urlopen(
                    f"{self.comfyui_url}/history/"
                    f"{prompt_id}"
                ) as response:
                    history = json.loads(
                        response.read()
                    )

            except Exception as error:
                raise ComfyUIBackendError(
                    "No se pudo consultar el estado de ComfyUI.",
                    category="CONNECTION_ERROR",
                    prompt_id=prompt_id,
                    exception_type=type(
                        error
                    ).__name__,
                    exception_message=str(
                        error
                    ),
                ) from error

            if prompt_id in history:
                outputs = (
                    history[prompt_id]
                    .get(
                        "outputs",
                        {}
                    )
                )

                for node_output in outputs.values():
                    if "images" in node_output:
                        images = (
                            node_output["images"]
                        )

                        if images:
                            return images[0]

                status = (
                    history[prompt_id]
                    .get(
                        "status",
                        {}
                    )
                )

                if status.get(
                    "status_str"
                ) == "error":
                    detail = _extract_error_detail(
                        history[prompt_id],
                        prompt_id
                    )
                    raise ComfyUIBackendError(
                        "ComfyUI devolvio un error durante "
                        "la generacion: "
                        f"{detail['category']}. "
                        f"{detail['exception_message']}",
                        category=detail[
                            "category"
                        ],
                        prompt_id=prompt_id,
                        node_id=detail[
                            "node_id"
                        ],
                        node_type=detail[
                            "node_type"
                        ],
                        exception_type=detail[
                            "exception_type"
                        ],
                        exception_message=detail[
                            "exception_message"
                        ],
                        status=status.get(
                            "status_str",
                            ""
                        ),
                    )

            time.sleep(
                1
            )

    def download_image(
        self,
        image_info,
        scene_number,
        output_dir
    ):
        params = urllib.parse.urlencode({
            "filename": image_info["filename"],
            "subfolder": image_info.get(
                "subfolder",
                ""
            ),
            "type": image_info.get(
                "type",
                "output"
            )
        })

        url = (
            f"{self.comfyui_url}/view?"
            f"{params}"
        )

        image_path = (
            output_dir
            / f"scene_{scene_number:03d}.png"
        )

        try:
            with urllib.request.urlopen(
                url
            ) as response:
                image_path.write_bytes(
                    response.read()
                )

        except Exception as error:
            raise ComfyUIBackendError(
                "No se pudo descargar la imagen "
                f"de la escena {scene_number}.",
                category="CONNECTION_ERROR",
                exception_type=type(
                    error
                ).__name__,
                exception_message=str(
                    error
                ),
            ) from error

        if not image_path.exists():
            raise FileNotFoundError(
                "No se guardo la imagen esperada: "
                f"{image_path}"
            )

        if image_path.stat().st_size <= 0:
            raise ComfyUIBackendError(
                "La imagen descargada esta vacia: "
                f"{image_path}",
                category="EXECUTION_ERROR",
            )

        return image_path

    def inject_prompt(
        self,
        workflow,
        prompt
    ):
        prompt_injected = False

        for node in workflow.values():
            inputs = node.get(
                "inputs",
                {}
            )

            if "text" in inputs:
                text_value = inputs["text"]

                if isinstance(
                    text_value,
                    str
                ):
                    inputs["text"] = prompt
                    prompt_injected = True
                    break

        if not prompt_injected:
            raise ValueError(
                "No se encontro ningun nodo de texto "
                "en el workflow de ComfyUI."
            )

        return workflow


def _extract_error_detail(
    history_item,
    prompt_id
):
    status = history_item.get(
        "status",
        {}
    )
    messages = status.get(
        "messages",
        ()
    )
    payload = {}
    for message in messages:
        if (
            isinstance(
                message,
                (
                    list,
                    tuple,
                )
            )
            and len(
                message
            ) >= 2
            and isinstance(
                message[1],
                dict
            )
        ):
            payload = message[1]
    exception_type = str(
        payload.get(
            "exception_type",
            ""
        )
    )
    exception_message = str(
        payload.get(
            "exception_message",
            ""
        )
    )
    return {
        "prompt_id": prompt_id,
        "node_id": str(
            payload.get(
                "node_id",
                ""
            )
        ),
        "node_type": str(
            payload.get(
                "node_type",
                ""
            )
        ),
        "exception_type": exception_type,
        "exception_message": exception_message,
        "category": _classify_comfyui_error(
            exception_type,
            exception_message,
        ),
    }


def _classify_comfyui_error(
    exception_type,
    exception_message
):
    text = (
        f"{exception_type} {exception_message}"
    ).lower()
    if "outofmemory" in text or "out of memory" in text:
        return "OUT_OF_MEMORY"
    if (
        "token indices sequence length" in text
        or "maximum sequence length" in text
        or "too long" in text
    ):
        return "PROMPT_TOO_LONG"
    if "model" in text and "not found" in text:
        return "MODEL_NOT_FOUND"
    if "node" in text and "not found" in text:
        return "NODE_NOT_FOUND"
    if "workflow" in text:
        return "WORKFLOW_INVALID"
    if "validation" in text or "invalid input" in text:
        return "INPUT_VALIDATION_ERROR"
    if exception_type or exception_message:
        return "EXECUTION_ERROR"
    return "UNKNOWN_BACKEND_ERROR"
