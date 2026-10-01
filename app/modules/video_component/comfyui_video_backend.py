from pathlib import Path
import hashlib
import json
import shutil
import time
import urllib.parse
import urllib.request
import uuid

from app.modules.video_component.models import (
    ComfyUIVideoBackendError,
    ComfyUIVideoWorkflow,
    VideoClipGenerationResult,
)
from app.shared.operational_error import (
    OperationalError,
    create_operational_error,
)


class ComfyUIVideoBackend:

    def __init__(
        self,
        comfyui_url="http://127.0.0.1:8188",
        comfyui_input_dir="ComfyUI/ComfyUI/input",
        poll_interval_seconds=2,
    ):
        self.comfyui_url = comfyui_url.rstrip(
            "/"
        )
        self.comfyui_input_dir = Path(
            comfyui_input_dir
        )
        self.poll_interval_seconds = poll_interval_seconds

    def generate(
        self,
        prepared_workflow: ComfyUIVideoWorkflow,
        output_dir,
        output_name="clip_001.mp4"
    ) -> VideoClipGenerationResult:
        try:
            return self._generate(
                prepared_workflow=prepared_workflow,
                output_dir=output_dir,
                output_name=output_name,
            )
        except OperationalError:
            raise
        except ComfyUIVideoBackendError as error:
            raise _operational_video_backend_error(
                error,
                prepared_workflow=prepared_workflow,
            ) from error

    def _generate(
        self,
        *,
        prepared_workflow,
        output_dir,
        output_name,
    ) -> VideoClipGenerationResult:
        output_dir = Path(
            output_dir
        )
        output_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        self._stage_source_image(
            prepared_workflow
        )

        client_id = str(
            uuid.uuid4()
        )
        prompt_id = self.queue_prompt(
            prepared_workflow.workflow,
            client_id
        )
        video_info = self.wait_for_video(
            prompt_id
        )
        output_clip = self.download_video(
            video_info=video_info,
            output_dir=output_dir,
            output_name=output_name
        )
        manifest_path = self.write_manifest(
            prepared_workflow=prepared_workflow,
            prompt_id=prompt_id,
            output_clip=output_clip,
            output_dir=output_dir,
        )

        backend_prompt = prepared_workflow.backend_prompt
        return VideoClipGenerationResult(
            source_image=backend_prompt.source_image,
            output_clip=output_clip,
            manifest_path=manifest_path,
            prompt_id=prompt_id,
            backend=backend_prompt.backend,
            model=backend_prompt.model,
            workflow=backend_prompt.workflow,
            seed=backend_prompt.seed,
            frames=backend_prompt.frames,
            fps=backend_prompt.fps,
            generation_width=backend_prompt.generation_width,
            generation_height=backend_prompt.generation_height,
            target_width=backend_prompt.target_width,
            target_height=backend_prompt.target_height,
            steps=backend_prompt.steps,
            cfg=backend_prompt.cfg,
            sampler=backend_prompt.sampler,
            scheduler=backend_prompt.scheduler,
            profile_name=backend_prompt.profile_name,
            duration_seconds=(
                backend_prompt.frames / backend_prompt.fps
            ),
            fingerprint=_file_sha256(
                output_clip
            ),
            positive_prompt=backend_prompt.positive_prompt,
            negative_prompt=backend_prompt.negative_prompt,
            motion_summary=backend_prompt.motion_summary,
            camera_motion=backend_prompt.camera_motion,
            motion_intensity=backend_prompt.motion_intensity,
            stability=backend_prompt.stability,
            temporal_rhythm=backend_prompt.temporal_rhythm,
            motion_level=backend_prompt.motion_level,
            preservation_constraints=(
                backend_prompt.preservation_constraints
            ),
            avoidance_constraints=(
                backend_prompt.avoidance_constraints
            ),
            source_trace=backend_prompt.source_trace,
        )

    def queue_prompt(
        self,
        workflow,
        client_id
    ):
        payload = json.dumps({
            "prompt": workflow,
            "client_id": client_id,
        }).encode(
            "utf-8"
        )
        request = urllib.request.Request(
            f"{self.comfyui_url}/prompt",
            data=payload,
            headers={
                "Content-Type": "application/json"
            },
        )

        try:
            with urllib.request.urlopen(
                request,
            ) as response:
                result = json.loads(
                    response.read()
                )
        except Exception as error:
            raise ComfyUIVideoBackendError(
                "No se pudo enviar el workflow de vídeo a ComfyUI.",
                category="CONNECTION_ERROR",
                exception_type=type(
                    error
                ).__name__,
                exception_message=str(
                    error
                ),
            ) from error

        if "prompt_id" not in result:
            raise ComfyUIVideoBackendError(
                "ComfyUI no devolvió prompt_id para vídeo.",
                category="INPUT_VALIDATION_ERROR",
            )

        return result["prompt_id"]

    def wait_for_video(
        self,
        prompt_id
    ):
        while True:
            history = self._history(
                prompt_id
            )
            if prompt_id in history:
                history_item = history[prompt_id]
                video_info = _find_video_output(
                    history_item
                )
                if video_info is not None:
                    return video_info

                status = history_item.get(
                    "status",
                    {}
                )
                if status.get(
                    "status_str"
                ) == "error":
                    detail = _extract_error_detail(
                        history_item,
                        prompt_id
                    )
                    raise ComfyUIVideoBackendError(
                        "ComfyUI devolvió un error durante "
                        "la generación de vídeo: "
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
                self.poll_interval_seconds
            )

    def download_video(
        self,
        video_info,
        output_dir,
        output_name
    ):
        output_path = Path(
            output_dir
        ) / output_name
        params = urllib.parse.urlencode({
            "filename": video_info["filename"],
            "subfolder": video_info.get(
                "subfolder",
                ""
            ),
            "type": video_info.get(
                "type",
                "output"
            ),
        })
        url = (
            f"{self.comfyui_url}/view?"
            f"{params}"
        )

        try:
            with urllib.request.urlopen(
                url,
            ) as response:
                output_path.write_bytes(
                    response.read()
                )
        except Exception as error:
            raise ComfyUIVideoBackendError(
                "No se pudo descargar el clip de vídeo de ComfyUI.",
                category="CONNECTION_ERROR",
                exception_type=type(
                    error
                ).__name__,
                exception_message=str(
                    error
                ),
            ) from error

        if not output_path.exists():
            raise FileNotFoundError(
                "No se guardo el clip esperado: "
                f"{output_path}"
            )

        if output_path.stat().st_size <= 0:
            raise ComfyUIVideoBackendError(
                "El clip generado está vacío: "
                f"{output_path}",
                category="EXECUTION_ERROR",
            )

        return output_path

    def write_manifest(
        self,
        prepared_workflow,
        prompt_id,
        output_clip,
        output_dir
    ):
        backend_prompt = prepared_workflow.backend_prompt
        manifest_path = (
            Path(
                output_dir
            )
            / "video_clips_manifest.json"
        )
        data = {
            "source_image": str(
                backend_prompt.source_image
            ),
            "output_clip": str(
                output_clip
            ),
            "motion_summary": backend_prompt.motion_summary,
            "positive_prompt": backend_prompt.positive_prompt,
            "negative_prompt": backend_prompt.negative_prompt,
            "camera_motion": backend_prompt.camera_motion,
            "motion_intensity": backend_prompt.motion_intensity,
            "stability": backend_prompt.stability,
            "temporal_rhythm": backend_prompt.temporal_rhythm,
            "motion_level": backend_prompt.motion_level,
            "preservation_constraints": list(
                backend_prompt.preservation_constraints
            ),
            "avoidance_constraints": list(
                backend_prompt.avoidance_constraints
            ),
            "source_trace": list(
                backend_prompt.source_trace
            ),
            "profile": backend_prompt.profile_name,
            "backend": backend_prompt.backend,
            "model": backend_prompt.model,
            "workflow": backend_prompt.workflow,
            "prompt_id": prompt_id,
            "seed": backend_prompt.seed,
            "frames": backend_prompt.frames,
            "fps": backend_prompt.fps,
            "generation_width": (
                backend_prompt.generation_width
            ),
            "generation_height": (
                backend_prompt.generation_height
            ),
            "target_width": (
                backend_prompt.target_width
            ),
            "target_height": (
                backend_prompt.target_height
            ),
            "steps": backend_prompt.steps,
            "cfg": backend_prompt.cfg,
            "sampler": backend_prompt.sampler,
            "scheduler": backend_prompt.scheduler,
            "duration_seconds": (
                backend_prompt.frames / backend_prompt.fps
            ),
            "fingerprint": _file_sha256(
                output_clip
            ),
        }
        manifest_path.write_text(
            json.dumps(
                data,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return manifest_path

    def _history(
        self,
        prompt_id
    ):
        try:
            with urllib.request.urlopen(
                f"{self.comfyui_url}/history/{prompt_id}",
            ) as response:
                return json.loads(
                    response.read()
                )
        except Exception as error:
            raise ComfyUIVideoBackendError(
                "No se pudo consultar el history de ComfyUI.",
                category="CONNECTION_ERROR",
                prompt_id=prompt_id,
                exception_type=type(
                    error
                ).__name__,
                exception_message=str(
                    error
                ),
            ) from error

    def _stage_source_image(
        self,
        prepared_workflow
    ):
        source_image = (
            prepared_workflow.backend_prompt.source_image
        )
        if not source_image.exists():
            raise FileNotFoundError(
                "No existe la imagen fuente para I2V: "
                f"{source_image}"
            )

        self.comfyui_input_dir.mkdir(
            parents=True,
            exist_ok=True
        )
        destination = (
            self.comfyui_input_dir
            / prepared_workflow.source_image_name
        )
        shutil.copy2(
            source_image,
            destination
        )


def _find_video_output(
    history_item
):
    outputs = history_item.get(
        "outputs",
        {}
    )
    for node_output in outputs.values():
        for key in (
            "videos",
            "gifs",
            "images",
        ):
            for item in node_output.get(
                key,
                ()
            ):
                filename = item.get(
                    "filename",
                    ""
                )
                if filename.lower().endswith(
                    (
                        ".mp4",
                        ".webm",
                        ".mov",
                        ".mkv",
                    )
                ):
                    return item
    return None


def _operational_video_backend_error(
    error,
    *,
    prepared_workflow,
):
    backend_prompt = prepared_workflow.backend_prompt
    metadata = {
        "service": "comfyui",
        "backend": "wan_i2v",
        "category": error.category,
        "workflow": backend_prompt.workflow,
    }
    for field_name in (
        "prompt_id",
        "node_id",
        "node_type",
        "exception_type",
        "status",
    ):
        value = getattr(error, field_name, "")
        if value:
            metadata[field_name] = value
    return create_operational_error(
        family="EXTERNAL_SERVICE",
        user_message="ComfyUI no pudo generar el clip de video solicitado.",
        recommended_action=(
            "Comprueba que ComfyUI y el backend Wan/I2V esten disponibles "
            "antes de reintentar."
        ),
        operation="Generar video I2V con ComfyUI",
        resource=str(backend_prompt.source_image),
        technical_metadata=metadata,
    )


def _extract_error_detail(
    history_item,
    prompt_id
):
    status = history_item.get(
        "status",
        {}
    )
    payload = {}
    for message in status.get(
        "messages",
        ()
    ):
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


def _file_sha256(
    path
):
    digest = hashlib.sha256()
    with Path(
        path
    ).open(
        "rb"
    ) as file:
        for chunk in iter(
            lambda: file.read(
                1024 * 1024
            ),
            b"",
        ):
            digest.update(
                chunk
            )
    return digest.hexdigest()
