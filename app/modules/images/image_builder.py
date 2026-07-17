from pathlib import Path
import json
import time
import urllib.parse
import urllib.request
import uuid

from app.managers.project_manager import ProjectManager
from app.domain.adapters import (
    LegacyGenerationResultAdapter,
    LegacyStoryboardSceneAdapter
)
from app.shared.config_manager import ConfigManager
from app.shared.progress_logger import ProgressLogger
from app.modules.visual_director import (
    VisualDirectionContext,
    VisualDirector
)


class ImageBuilder:

    base_visual_identity = (
        "professional cinematic realism, grounded documentary aesthetic, "
        "natural believable appearance, coherent production design, "
        "professional visual quality"
    )

    def __init__(
        self,
        comfyui_url="http://127.0.0.1:8188",
        workflow_path="config/comfyui_flux_workflow_api.json",
        visual_director=None
    ):
        self.comfyui_url = comfyui_url

        self.workflow_path = Path(
            workflow_path
        )

        self.visual_director = (
            visual_director
            or VisualDirector()
        )

    def build(
        self,
        storyboard_path=None,
        output_dir=None
    ):
        total_start = time.perf_counter()

        ProgressLogger.start(
            "GENERANDO IMÁGENES"
        )

        project = ProjectManager()

        config = ConfigManager()

        profile = (
            config.get_profile_config()
        )

        width, height = (
            self._get_image_dimensions(
                profile
            )
        )

        ProgressLogger.info(
            f"Formato de imagen: "
            f"{width}x{height}"
        )

        if storyboard_path is None:
            storyboard_path = (
                project.storyboard_path()
            )

        if output_dir is None:
            output_dir = (
                project.images_dir()
            )

        storyboard_path = Path(
            storyboard_path
        )

        output_dir = Path(
            output_dir
        )

        if not storyboard_path.exists():
            raise FileNotFoundError(
                "No existe el storyboard: "
                f"{storyboard_path}"
            )

        if not self.workflow_path.exists():
            raise FileNotFoundError(
                "No existe el workflow de ComfyUI: "
                f"{self.workflow_path}"
            )

        output_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        scenes = json.loads(
            storyboard_path.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(
            scenes,
            list
        ):
            raise ValueError(
                "El storyboard debe contener "
                "una lista de escenas."
            )

        if not scenes:
            raise ValueError(
                "El storyboard no contiene escenas."
            )

        scene_count = len(
            scenes
        )

        generated_images = []
        previous_directives = {}
        visual_director_elapsed = 0.0
        visual_director_enabled = (
            self._is_visual_director_enabled(
                profile
            )
        )

        for index, scene in enumerate(
            scenes,
            start=1
        ):
            storyboard_scene = (
                LegacyStoryboardSceneAdapter.from_dict(
                    scene=scene,
                    default_scene_number=index
                )
            )

            scene_number = (
                storyboard_scene.scene_number
            )

            visual_idea = (
                LegacyStoryboardSceneAdapter.visual_idea(
                    scene
                )
            )

            if not visual_idea:
                raise ValueError(
                    f"La escena {scene_number} "
                    f"no contiene visual_idea."
                )

            (
                prompt,
                prompt_metadata,
                previous_directives,
                elapsed
            ) = self._build_directed_prompt(
                storyboard_scene=storyboard_scene,
                visual_idea=visual_idea,
                scene_number=scene_number,
                scene_index=index,
                scene_count=scene_count,
                profile=profile,
                visual_director_enabled=(
                    visual_director_enabled
                ),
                previous_directives=(
                    previous_directives
                )
            )

            visual_director_elapsed += (
                elapsed
            )

            prompt = (
                self._compose_backend_prompt(
                    positive_prompt=prompt_metadata[
                        "positive_prompt"
                    ],
                    negative_prompt=prompt_metadata[
                        "negative_prompt"
                    ]
                )
            )

            image_path = (
                self._generate_image(
                    prompt=prompt,
                    scene_number=scene_number,
                    output_dir=output_dir,
                    width=width,
                    height=height
                )
            )

            generation_result = (
                LegacyGenerationResultAdapter.from_image_result(
                    image_path=image_path,
                    storyboard_scene=storyboard_scene,
                    width=width,
                    height=height
                )
            )

            generated_images.append({
                "scene": generation_result.scene_number,
                "prompt": prompt,
                "positive_prompt": (
                    prompt_metadata[
                        "positive_prompt"
                    ]
                ),
                "negative_prompt": (
                    prompt_metadata[
                        "negative_prompt"
                    ]
                ),
                "visual_director": (
                    prompt_metadata[
                        "visual_director"
                    ]
                ),
                "image": str(image_path),
                "width": generation_result.width,
                "height": generation_result.height,
                "duration": generation_result.duration
            })

            ProgressLogger.info(
                f"{index}/{scene_count} imágenes"
            )

        ProgressLogger.info(
            "Visual Director: "
            f"{visual_director_elapsed:.2f} segundos"
        )

        manifest_path = (
            project.images_manifest_path()
        )

        manifest_path.write_text(
            json.dumps(
                generated_images,
                ensure_ascii=False,
                indent=4
            ),
            encoding="utf-8"
        )

        if not manifest_path.exists():
            raise FileNotFoundError(
                "No se encontró el manifiesto "
                "de imágenes esperado: "
                f"{manifest_path}"
            )

        if manifest_path.stat().st_size <= 0:
            raise RuntimeError(
                "El manifiesto de imágenes "
                "está vacío."
            )

        total_elapsed = (
            time.perf_counter()
            - total_start
        )

        ProgressLogger.finish(
            "Finalizado",
            total_elapsed
        )

        return manifest_path

    def _get_image_dimensions(
        self,
        profile
    ):
        video_style = profile.get(
            "video_style",
            {}
        )

        width = video_style.get(
            "width"
        )

        height = video_style.get(
            "height"
        )

        if width is None:
            raise ValueError(
                "El perfil no contiene "
                "video_style.width."
            )

        if height is None:
            raise ValueError(
                "El perfil no contiene "
                "video_style.height."
            )

        try:
            width = int(
                width
            )

            height = int(
                height
            )

        except (
            TypeError,
            ValueError
        ) as error:
            raise ValueError(
                "La resolución del perfil "
                "no contiene valores válidos."
            ) from error

        if width <= 0 or height <= 0:
            raise ValueError(
                "La resolución debe contener "
                "valores superiores a cero."
            )

        return width, height

    def _is_visual_director_enabled(
        self,
        profile
    ):
        visual_director = profile.get(
            "visual_director",
            {}
        )

        if not isinstance(
            visual_director,
            dict
        ):
            return True

        return bool(
            visual_director.get(
                "enabled",
                True
            )
        )

    def _build_directed_prompt(
        self,
        storyboard_scene,
        visual_idea,
        scene_number,
        scene_index,
        scene_count,
        profile,
        visual_director_enabled,
        previous_directives
    ):
        legacy_prompt = self._build_prompt(
            visual_idea
        )

        if not visual_director_enabled:
            return (
                legacy_prompt,
                self._legacy_prompt_metadata(
                    legacy_prompt=legacy_prompt,
                    enabled=False,
                    fallback_reason=None
                ),
                previous_directives,
                0.0
            )

        start = time.perf_counter()

        try:
            directed_prompt = (
                self.visual_director.direct(
                    VisualDirectionContext(
                        scene_text=storyboard_scene.text,
                        visual_idea=visual_idea,
                        duration=float(
                            storyboard_scene.duration
                            or 0
                        ),
                        scene_index=scene_index,
                        scene_count=scene_count,
                        orientation=str(
                            profile.get(
                                "format",
                                ""
                            )
                        ).strip().lower(),
                        previous_directives=(
                            previous_directives
                        )
                    )
                )
            )

        except Exception as error:
            ProgressLogger.warning(
                "Visual Director falló en la escena "
                f"{scene_number}. Se usa prompt legacy. "
                f"Motivo: {error}"
            )

            elapsed = (
                time.perf_counter()
                - start
            )

            return (
                legacy_prompt,
                self._legacy_prompt_metadata(
                    legacy_prompt=legacy_prompt,
                    enabled=True,
                    fallback_reason=str(
                        error
                    )
                ),
                previous_directives,
                elapsed
            )

        elapsed = (
            time.perf_counter()
            - start
        )

        metadata = {
            "positive_prompt": (
                directed_prompt.positive_prompt
            ),
            "negative_prompt": (
                directed_prompt.negative_prompt
            ),
            "visual_director": {
                "enabled": True,
                "fallback": False,
                "scene": scene_number,
                "directives": (
                    directed_prompt.directives
                )
            }
        }

        return (
            directed_prompt.final_prompt,
            metadata,
            directed_prompt.directives,
            elapsed
        )

    def _legacy_prompt_metadata(
        self,
        legacy_prompt,
        enabled,
        fallback_reason
    ):
        return {
            "positive_prompt": legacy_prompt,
            "negative_prompt": "",
            "visual_director": {
                "enabled": enabled,
                "fallback": (
                    fallback_reason is not None
                ),
                "fallback_reason": fallback_reason,
                "directives": {}
            }
        }

    def _build_prompt(
        self,
        visual_idea
    ):
        return (
            f"{visual_idea}, "
            "ultra realistic cinematic image, "
            "photorealistic, documentary style, "
            "golden volumetric lighting, "
            "deep shadows, natural colors, "
            "high detail, sharp focus, "
            "epic composition, atmospheric depth, "
            "no cartoon, no anime, no illustration, "
            "premium film still, 8k, "
            "no text, no letters, no words, "
            "no typography, no captions, "
            "no subtitles, no logos, "
            "no watermarks, no signs, "
            "no readable characters, "
            "no handwritten text, "
            "no printed text, "
            "no text on books, "
            "no text on screens, "
            "no text on walls, "
            "no text on objects"
        )

    def _compose_backend_prompt(
        self,
        positive_prompt,
        negative_prompt=""
    ):
        prompt = ", ".join(
            self._dedupe_prompt_parts(
                (
                    positive_prompt,
                    self.base_visual_identity
                )
            )
        )

        if negative_prompt:
            prompt = (
                f"{prompt}, avoid: {negative_prompt}"
            )

        return prompt

    def _dedupe_prompt_parts(
        self,
        parts
    ):
        seen = set()
        result = []

        for part in parts:
            part = str(
                part
                or ""
            ).strip()

            if not part:
                continue

            key = part.lower()

            if key in seen:
                continue

            seen.add(
                key
            )
            result.append(
                part
            )

        return result

    def _generate_image(
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

        workflow = self._inject_prompt(
            workflow,
            prompt
        )

        workflow = self._inject_dimensions(
            workflow,
            width,
            height
        )

        client_id = str(
            uuid.uuid4()
        )

        prompt_id = self._queue_prompt(
            workflow,
            client_id
        )

        image_info = self._wait_for_image(
            prompt_id
        )

        return self._download_image(
            image_info=image_info,
            scene_number=scene_number,
            output_dir=output_dir
        )

    def _inject_dimensions(
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
                "No se encontró el nodo "
                "EmptySD3LatentImage "
                "en el workflow de ComfyUI."
            )

        if not sampling_updated:
            raise ValueError(
                "No se encontró el nodo "
                "ModelSamplingFlux "
                "en el workflow de ComfyUI."
            )

        return workflow

    def _queue_prompt(
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
            raise RuntimeError(
                "No se pudo enviar el workflow "
                "a ComfyUI."
            ) from error

        if "prompt_id" not in result:
            raise RuntimeError(
                "ComfyUI no devolvió prompt_id."
            )

        return result["prompt_id"]

    def _wait_for_image(
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
                raise RuntimeError(
                    "No se pudo consultar "
                    "el estado de ComfyUI."
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
                    raise RuntimeError(
                        "ComfyUI devolvió un error "
                        "durante la generación."
                    )

            time.sleep(
                1
            )

    def _download_image(
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
            raise RuntimeError(
                "No se pudo descargar "
                f"la imagen de la escena "
                f"{scene_number}."
            ) from error

        if not image_path.exists():
            raise FileNotFoundError(
                "No se guardó la imagen esperada: "
                f"{image_path}"
            )

        if image_path.stat().st_size <= 0:
            raise RuntimeError(
                "La imagen descargada está vacía: "
                f"{image_path}"
            )

        return image_path

    def _inject_prompt(
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
                "No se encontró ningún nodo de texto "
                "en el workflow de ComfyUI."
            )

        return workflow
