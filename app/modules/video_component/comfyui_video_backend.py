from pathlib import Path
import hashlib
import json
import re
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
from app.modules.video_component.contracts import (
    ComfyUIInputRetention,
    StagedComfyInput,
    WanArtifactRetention,
    WanIntermediateOutput,
)
from app.modules.video_component.lossless_frame_output import (
    LosslessWanFrameOutput,
    LosslessWanFrameOutputError,
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
        comfyui_output_dir="ComfyUI/ComfyUI/output",
        poll_interval_seconds=2,
        staging_retention=ComfyUIInputRetention.CLEANUP_ON_SUCCESS,
        lossless_frame_output=None,
    ):
        self.comfyui_url = comfyui_url.rstrip(
            "/"
        )
        self.comfyui_input_dir = Path(
            comfyui_input_dir
        )
        self.comfyui_output_dir = Path(comfyui_output_dir)
        self.poll_interval_seconds = poll_interval_seconds
        self.staging_retention = ComfyUIInputRetention(
            staging_retention
        )
        self.lossless_frame_output = (
            lossless_frame_output
            or LosslessWanFrameOutput()
        )

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
        except LosslessWanFrameOutputError as error:
            backend_error = ComfyUIVideoBackendError(
                str(error),
                category="EXECUTION_ERROR",
            )
            raise _operational_video_backend_error(
                backend_error,
                prepared_workflow=prepared_workflow,
            ) from error

    def _generate(
        self,
        *,
        prepared_workflow,
        output_dir,
        output_name,
    ) -> VideoClipGenerationResult:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        staged_input = self._stage_source_image(prepared_workflow)
        completed = False
        try:
            intermediate_output = (
                prepared_workflow.backend_prompt.intermediate_output
            )
            if intermediate_output is WanIntermediateOutput.LOSSLESS_FFV1:
                if prepared_workflow.lossless_capture is None:
                    raise ComfyUIVideoBackendError(
                        "La salida lossless_ffv1 requiere captura PNG del workflow.",
                        category="INPUT_VALIDATION_ERROR",
                    )
                result = self._generate_lossless_staged(
                    prepared_workflow=prepared_workflow,
                    output_dir=output_dir,
                    output_name=output_name,
                )
            elif intermediate_output is WanIntermediateOutput.SAVEVIDEO_H264:
                if prepared_workflow.lossless_capture is not None:
                    raise ComfyUIVideoBackendError(
                        "savevideo_h264 no admite captura lossless del workflow.",
                        category="INPUT_VALIDATION_ERROR",
                    )
                result = self._generate_staged(
                    prepared_workflow=prepared_workflow,
                    output_dir=output_dir,
                    output_name=output_name,
                )
            else:
                raise ComfyUIVideoBackendError(
                    "Salida intermedia WAN no admitida.",
                    category="INPUT_VALIDATION_ERROR",
                )
                result = self._generate_lossless_staged(
                    prepared_workflow=prepared_workflow,
                    output_dir=output_dir,
                    output_name=output_name,
                )
            completed = True
            return result
        finally:
            if completed:
                self._cleanup_after_success(staged_input)

    def _generate_lossless_staged(
        self,
        *,
        prepared_workflow,
        output_dir,
        output_name,
    ):
        plan = prepared_workflow.lossless_capture
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        prompt_id = self.queue_prompt(prepared_workflow.workflow, str(uuid.uuid4()))
        sequence = self.lossless_frame_output.capture(
            history_item=self.wait_for_lossless_capture(prompt_id, plan),
            plan=plan,
            prompt_id=prompt_id,
            destination_root=output_dir,
            download=self.download_output_file,
        )
        lossless_clip = self.lossless_frame_output.materialize_ffv1(
            sequence,
            output_dir / Path(output_name).with_suffix(".mkv").name,
        )
        self._cleanup_remote_lossless_output(plan)
        self.lossless_frame_output.cleanup_after_success(sequence)
        return self._result_from_output(
            prepared_workflow=prepared_workflow,
            output_clip=lossless_clip,
            prompt_id=prompt_id,
        )

    def _generate_staged(
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

        return self._result_from_output(
            prepared_workflow=prepared_workflow,
            output_clip=output_clip,
            prompt_id=prompt_id,
        )

    @staticmethod
    def _result_from_output(*, prepared_workflow, output_clip, prompt_id):
        backend_prompt = prepared_workflow.backend_prompt
        return VideoClipGenerationResult(
            source_image=backend_prompt.source_image,
            output_clip=output_clip,
            manifest_path=None,
            prompt_id=prompt_id,
            backend=backend_prompt.backend,
            model=backend_prompt.model,
            workflow=backend_prompt.workflow,
            seed=backend_prompt.seed,
            frames=backend_prompt.frames,
            fps=backend_prompt.fps,
            generation_width=backend_prompt.generation_width,
            generation_height=backend_prompt.generation_height,
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

    def wait_for_lossless_capture(self, prompt_id, plan):
        """Wait for the semantic SaveImage PNG batch of one lossless prompt.

        ``lossless_ffv1`` completes when the same ``prompt_id`` exposes the
        expected PNG batch at its semantic capture node. This path does not
        depend on SaveVideo and does not call ``wait_for_video()`` or
        ``download_video()``. ``savevideo_h264`` keeps its separate H.264
        wait/download route.
        """
        while True:
            history = self._history(prompt_id)
            if not isinstance(history, dict):
                raise ComfyUIVideoBackendError(
                    "ComfyUI devolvió un history incompatible para la captura lossless WAN.",
                    category="EXECUTION_ERROR",
                    prompt_id=prompt_id,
                )
            if prompt_id in history:
                history_item = history[prompt_id]
                if not isinstance(history_item, dict):
                    raise ComfyUIVideoBackendError(
                        "ComfyUI devolvió un item de history incompatible para la captura lossless WAN.",
                        category="EXECUTION_ERROR",
                        prompt_id=prompt_id,
                    )
                status = history_item.get("status", {})
                if not isinstance(status, dict):
                    raise ComfyUIVideoBackendError(
                        "ComfyUI devolvió un estado incompatible para la captura lossless WAN.",
                        category="EXECUTION_ERROR",
                        prompt_id=prompt_id,
                    )
                if status.get("status_str") == "error":
                    self._raise_history_execution_error(history_item, prompt_id)

                outputs = history_item.get("outputs", {})
                if not isinstance(outputs, dict):
                    raise ComfyUIVideoBackendError(
                        "ComfyUI devolvió outputs incompatibles para la captura lossless WAN.",
                        category="EXECUTION_ERROR",
                        prompt_id=prompt_id,
                    )
                capture_output = outputs.get(plan.capture_node_id)
                if capture_output is not None:
                    if not isinstance(capture_output, dict):
                        raise ComfyUIVideoBackendError(
                            "ComfyUI devolvió una captura lossless WAN incompatible.",
                            category="EXECUTION_ERROR",
                            prompt_id=prompt_id,
                            node_id=plan.capture_node_id,
                        )
                    images = capture_output.get("images")
                    if not isinstance(images, list):
                        raise ComfyUIVideoBackendError(
                            "ComfyUI no devolvió un batch PNG válido para la captura lossless WAN.",
                            category="EXECUTION_ERROR",
                            prompt_id=prompt_id,
                            node_id=plan.capture_node_id,
                        )
                    if len(images) == plan.expected_frame_count:
                        return history_item

                if status.get("status_str") == "success":
                    raise ComfyUIVideoBackendError(
                        "ComfyUI terminó sin el batch PNG lossless esperado.",
                        category="EXECUTION_ERROR",
                        prompt_id=prompt_id,
                        node_id=plan.capture_node_id,
                        status="success",
                    )

            time.sleep(self.poll_interval_seconds)

    def download_video(
        self,
        video_info,
        output_dir,
        output_name
    ):
        output_path = Path(output_dir) / output_name
        return self.download_output_file(video_info, output_path)

    def download_output_file(self, output_info, output_path):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        params = urllib.parse.urlencode({
            "filename": output_info["filename"],
            "subfolder": output_info.get(
                "subfolder",
                ""
            ),
            "type": output_info.get(
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
                "No se guardó el clip esperado: "
                f"{output_path}"
            )

        if output_path.stat().st_size <= 0:
            raise ComfyUIVideoBackendError(
                "El clip generado está vacío: "
                f"{output_path}",
                category="EXECUTION_ERROR",
            )

        return output_path

    def _history_item(self, prompt_id):
        history = self._history(prompt_id)
        if prompt_id not in history:
            raise ComfyUIVideoBackendError(
                "ComfyUI no devolvió el history final del prompt de video.",
                category="EXECUTION_ERROR",
                prompt_id=prompt_id,
            )
        return history[prompt_id]

    @staticmethod
    def _raise_history_execution_error(history_item, prompt_id):
        status = history_item.get("status", {})
        detail = _extract_error_detail(history_item, prompt_id)
        raise ComfyUIVideoBackendError(
            "ComfyUI devolvió un error durante la generación de video: "
            f"{detail['category']}. {detail['exception_message']}",
            category=detail["category"],
            prompt_id=prompt_id,
            node_id=detail["node_id"],
            node_type=detail["node_type"],
            exception_type=detail["exception_type"],
            exception_message=detail["exception_message"],
            status=status.get("status_str", ""),
        )

    def _cleanup_remote_lossless_output(self, plan):
        if plan.retention is WanArtifactRetention.PRESERVE_ALWAYS:
            return
        output_root = self.comfyui_output_dir.resolve()
        capture_directory = (
            output_root / Path(plan.output_prefix).parent
        ).resolve()
        if (
            output_root not in capture_directory.parents
            or capture_directory.name != plan.job_id
            or capture_directory.parent.name != "aivc_wan_lossless"
        ):
            raise ComfyUIVideoBackendError(
                "La limpieza remota lossless WAN no posee ese output.",
                category="INPUT_VALIDATION_ERROR",
            )
        try:
            if capture_directory.exists():
                shutil.rmtree(capture_directory)
        except OSError as error:
            raise ComfyUIVideoBackendError(
                "No se pudo limpiar el output lossless WAN poseido.",
                category="FILESYSTEM_ERROR",
                exception_type=type(error).__name__,
                exception_message=str(error),
            ) from error

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

        job_id = uuid.uuid4().hex
        relative_input_name = (
            Path("wan_i2v")
            / job_id
            / _safe_staged_basename(source_image)
        ).as_posix()
        staged_input = StagedComfyInput(
            job_id=job_id,
            source_path=source_image,
            relative_input_name=relative_input_name,
            staged_path=(
                self.comfyui_input_dir / relative_input_name
            ),
            retention=self.staging_retention,
        )
        staged_input.staged_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        shutil.copy2(
            source_image,
            staged_input.staged_path,
        )
        self._inject_staged_input_name(
            prepared_workflow.workflow,
            staged_input.relative_input_name,
        )
        return staged_input

    def _inject_staged_input_name(self, workflow, relative_input_name):
        load_image_nodes = [
            node
            for node in workflow.values()
            if isinstance(node, dict)
            and node.get("class_type") == "LoadImage"
        ]
        if len(load_image_nodes) == 1:
            load_image_nodes[0].setdefault("inputs", {})["image"] = (
                relative_input_name
            )

    def _cleanup_after_success(self, staged_input):
        if staged_input.retention is ComfyUIInputRetention.PRESERVE_ALWAYS:
            return

        staged_path = self._owned_staged_path(staged_input)
        try:
            staged_path.unlink(missing_ok=True)
        except OSError as error:
            raise ComfyUIVideoBackendError(
                "No se pudo limpiar el input staged de ComfyUI.",
                category="FILESYSTEM_ERROR",
                exception_type=type(error).__name__,
                exception_message=str(error),
            ) from error

    def _owned_staged_path(self, staged_input):
        input_root = self.comfyui_input_dir.resolve()
        staged_path = staged_input.staged_path.resolve()
        if input_root not in staged_path.parents:
            raise ComfyUIVideoBackendError(
                "El input staged queda fuera del directorio ComfyUI poseido.",
                category="INPUT_VALIDATION_ERROR",
            )
        if staged_path == staged_input.source_path.resolve():
            raise ComfyUIVideoBackendError(
                "El backend no puede limpiar la imagen fuente original.",
                category="INPUT_VALIDATION_ERROR",
            )
        return staged_path


def _safe_staged_basename(source_image):
    source_path = Path(source_image)
    stem = re.sub(
        r"[^A-Za-z0-9_.-]+",
        "_",
        source_path.stem,
    ).strip("._")
    suffix = source_path.suffix.lower() or ".png"
    return f"{stem or 'source'}{suffix}"


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
            "Comprueba que ComfyUI y el backend Wan/I2V estén disponibles "
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
