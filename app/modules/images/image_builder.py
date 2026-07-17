from pathlib import Path
import json
import time

from app.managers.project_manager import ProjectManager
from app.domain.adapters import (
    LegacyGenerationResultAdapter,
    LegacyStoryboardSceneAdapter
)
from app.modules.images.backends import ComfyUIBackend
from app.shared.config_manager import ConfigManager
from app.shared.progress_logger import ProgressLogger
from app.modules.visual_director import (
    VisualDirectionContext,
    VisualDirector
)
from app.modules.images.prompt_system import ImagePromptSystem


class ImageBuilder:

    base_visual_identity = ImagePromptSystem.base_visual_identity

    def __init__(
        self,
        comfyui_url="http://127.0.0.1:8188",
        workflow_path="config/comfyui_flux_workflow_api.json",
        visual_director=None,
        prompt_system=None,
        backend=None
    ):
        self.comfyui_url = comfyui_url

        self.workflow_path = Path(
            workflow_path
        )

        self.visual_director = (
            visual_director
            or VisualDirector()
        )

        self.prompt_system = (
            prompt_system
            or ImagePromptSystem()
        )

        self.backend = (
            backend
            or ComfyUIBackend(
                comfyui_url=self.comfyui_url,
                workflow_path=self.workflow_path
            )
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
                self.prompt_system.compose_backend_prompt(
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
        return self.prompt_system.build_legacy_prompt(
            visual_idea
        )

    def _compose_backend_prompt(
        self,
        positive_prompt,
        negative_prompt=""
    ):
        return self.prompt_system.compose_backend_prompt(
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt
        )

    def _dedupe_prompt_parts(
        self,
        parts
    ):
        return self.prompt_system.dedupe_prompt_parts(
            parts
        )

    def _generate_image(
        self,
        prompt,
        scene_number,
        output_dir,
        width,
        height
    ):
        return self.backend.generate(
            prompt=prompt,
            scene_number=scene_number,
            output_dir=output_dir,
            width=width,
            height=height
        )

    def _inject_dimensions(
        self,
        workflow,
        width,
        height
    ):
        return self.backend.inject_dimensions(
            workflow=workflow,
            width=width,
            height=height
        )

    def _queue_prompt(
        self,
        workflow,
        client_id
    ):
        return self.backend.queue_prompt(
            workflow=workflow,
            client_id=client_id
        )

    def _wait_for_image(
        self,
        prompt_id
    ):
        return self.backend.wait_for_image(
            prompt_id
        )

    def _download_image(
        self,
        image_info,
        scene_number,
        output_dir
    ):
        return self.backend.download_image(
            image_info=image_info,
            scene_number=scene_number,
            output_dir=output_dir
        )

    def _inject_prompt(
        self,
        workflow,
        prompt
    ):
        return self.backend.inject_prompt(
            workflow=workflow,
            prompt=prompt
        )
