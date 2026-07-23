from pathlib import Path
import json
import hashlib
import time

from app.cinematic_direction import CinematicDirectionOrchestrator
from app.managers.project_manager import ProjectManager
from app.domain.adapters import (
    LegacyCognitiveAdapter,
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
from app.modules.images.manifest_writer import ImageManifestWriter
from app.modules.images.prompt_system import ImagePromptSystem
from app.prompt_translation import PromptTranslator
from app.visual_direction import (
    EffectiveVisualBrief,
    VisualBriefTrace
)


class ImageBuilder:

    base_visual_identity = ImagePromptSystem.base_visual_identity

    def __init__(
        self,
        comfyui_url="http://127.0.0.1:8188",
        workflow_path="config/comfyui_flux_workflow_api.json",
        visual_director=None,
        prompt_system=None,
        backend=None,
        manifest_writer=None,
        prompt_translator=None,
        cinematic_orchestrator=None
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

        self.manifest_writer = (
            manifest_writer
            or ImageManifestWriter()
        )

        self.prompt_translator = prompt_translator
        self.cinematic_orchestrator = cinematic_orchestrator

    def build(
        self,
        storyboard_path=None,
        output_dir=None,
        cinematic_enabled=False
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

            cinematic_runtime = (
                self._build_cinematic_runtime_metadata(
                    storyboard_scene=storyboard_scene,
                    visual_idea=visual_idea,
                    cinematic_enabled=cinematic_enabled
                )
            )

            if cinematic_runtime is not None:
                prompt_metadata[
                    "cinematic_runtime"
                ] = cinematic_runtime

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

            generated_images.append(
                self.manifest_writer.build_entry(
                    generation_result=generation_result,
                    prompt=prompt,
                    prompt_metadata=prompt_metadata,
                    image_path=image_path
                )
            )

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

        manifest_path = (
            self.manifest_writer.write(
                manifest_path=manifest_path,
                entries=generated_images
            )
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

    def _build_cinematic_runtime_metadata(
        self,
        storyboard_scene,
        visual_idea,
        cinematic_enabled
    ):
        if not cinematic_enabled:
            return None

        effective_visual_brief = (
            self._build_runtime_effective_visual_brief(
                storyboard_scene=storyboard_scene,
                visual_idea=visual_idea
            )
        )
        cinematic_direction_set = (
            self._cinematic_orchestrator().resolve(
                effective_visual_brief
            )
        )
        backend_prompt = (
            self._prompt_translator().translate(
                effective_visual_brief,
                cinematic_direction_set=cinematic_direction_set,
                cinematic_enabled=True
            )
        )

        return {
            "enabled": True,
            "effective_visual_brief_fingerprint": (
                effective_visual_brief.fingerprint
            ),
            "cinematic_direction_set_fingerprint": (
                cinematic_direction_set.fingerprint
            ),
            "backend_prompt_fingerprint": (
                backend_prompt.fingerprint
            )
        }

    def _build_runtime_effective_visual_brief(
        self,
        storyboard_scene,
        visual_idea
    ):
        adaptation = (
            LegacyCognitiveAdapter.from_storyboard_scene(
                storyboard_scene=storyboard_scene,
                visual_idea=visual_idea
            )
        )
        source_id = (
            f"scene_{storyboard_scene.scene_number:03d}"
        )
        source_version = (
            "legacy-runtime-v1"
        )
        fingerprint = (
            self._runtime_visual_brief_fingerprint(
                visual_brief=adaptation.visual_brief,
                source_id=source_id,
                source_version=source_version
            )
        )

        return EffectiveVisualBrief(
            visual_brief=adaptation.visual_brief,
            trace=VisualBriefTrace(),
            conflicts=(),
            fingerprint=fingerprint,
            source_id=source_id,
            source_version=source_version
        )

    def _runtime_visual_brief_fingerprint(
        self,
        visual_brief,
        source_id,
        source_version
    ):
        canonical = {
            "visual_brief": visual_brief,
            "source_id": source_id,
            "source_version": source_version
        }
        return hashlib.sha256(
            json.dumps(
                canonical,
                default=_json_default,
                sort_keys=True,
                separators=(
                    ",",
                    ":"
                )
            ).encode(
                "utf-8"
            )
        ).hexdigest()

    def _prompt_translator(
        self
    ):
        if self.prompt_translator is None:
            self.prompt_translator = (
                PromptTranslator()
            )

        return self.prompt_translator

    def _cinematic_orchestrator(
        self
    ):
        if self.cinematic_orchestrator is None:
            self.cinematic_orchestrator = (
                CinematicDirectionOrchestrator()
            )

        return self.cinematic_orchestrator

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


def _json_default(
    value
):
    if hasattr(
        value,
        "__dataclass_fields__"
    ):
        return {
            field: getattr(
                value,
                field
            )
            for field in value.__dataclass_fields__
        }

    raise TypeError(
        f"Object of type {type(value).__name__} "
        "is not JSON serializable"
    )
