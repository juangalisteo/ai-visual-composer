from pathlib import Path
import json
import hashlib
import time

from app.backend_adapters import ComfyUIAdapter
from app.cinematic_direction import CinematicDirectionOrchestrator
from app.managers.project_manager import ProjectManager
from app.domain.adapters import (
    GenerationResultAdapter,
    RuntimeCognitiveAdapter,
    StoryboardSceneAdapter
)
from app.modules.images.backends import ComfyUIBackend
from app.shared.config_manager import ConfigManager
from app.shared.progress_logger import ProgressLogger
from app.modules.images.manifest_writer import ImageManifestWriter
from app.modules.images.prompt_system import ImagePromptSystem
from app.prompt_translation import PromptTranslator
from app.visual_direction import (
    EffectiveVisualBrief,
    VisualBriefFieldOrigin,
    VisualBriefTrace
)
from app.visual_quality import ImageQualityFlowCoordinator


class ImageBuilder:

    base_visual_identity = ImagePromptSystem.base_visual_identity

    def __init__(
        self,
        comfyui_url="http://127.0.0.1:8188",
        workflow_path="config/comfyui_flux_workflow_api.json",
        prompt_system=None,
        backend=None,
        manifest_writer=None,
        prompt_translator=None,
        cinematic_orchestrator=None,
        backend_adapter=None,
        image_quality_flow=None
    ):
        self.comfyui_url = comfyui_url

        self.workflow_path = Path(
            workflow_path
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
        self.backend_adapter = backend_adapter
        self.image_quality_flow = image_quality_flow

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

        for index, scene in enumerate(
            scenes,
            start=1
        ):
            storyboard_scene = (
                StoryboardSceneAdapter.from_visual_truth(
                    scene=scene,
                    default_scene_number=index
                )
            )

            scene_number = (
                storyboard_scene.scene_number
            )

            if not RuntimeCognitiveAdapter.has_visual_truth_content(
                storyboard_scene
            ):
                raise ValueError(
                    f"La escena {scene_number} "
                    f"no contiene informacion visual."
                )

            runtime_metadata = (
                self._build_cinematic_runtime_metadata(
                    storyboard_scene=storyboard_scene,
                    profile=profile,
                )
            )
            prompt = (
                runtime_metadata[
                    "operational_prompt"
                ]
            )
            prompt_metadata = {
                "positive_prompt": (
                    runtime_metadata[
                        "backend_payload_prompt"
                    ]
                ),
                "negative_prompt": "",
                "visual_director": {
                    "enabled": False,
                    "fallback": False,
                    "directives": {}
                },
                "cinematic_runtime": (
                    runtime_metadata
                )
            }

            if scene_count:
                prompt_metadata[
                    "cinematic_runtime"
                ][
                    "scene_count"
                ] = scene_count
                prompt_metadata[
                    "cinematic_runtime"
                ][
                    "scene_index"
                ] = index

            image_path = (
                self._generate_image(
                    prompt=prompt,
                    scene_number=scene_number,
                    output_dir=output_dir,
                    width=width,
                    height=height
                )
            )

            if self._is_image_validation_enabled(
                profile
            ):
                retry_paths = {}

                def generate_quality_attempt(
                    attempt_number,
                    seed
                ):
                    attempt_dir = (
                        output_dir
                        / "_quality_attempts"
                        / f"scene_{scene_number:03d}"
                        / f"attempt_{attempt_number:03d}"
                    )
                    attempt_path = (
                        self._generate_image(
                            prompt=prompt,
                            scene_number=scene_number,
                            output_dir=attempt_dir,
                            width=width,
                            height=height
                        )
                    )
                    retry_paths[
                        attempt_number
                    ] = attempt_path
                    return attempt_path

                quality_result = (
                    self._image_quality_flow().evaluate(
                        image_path=image_path,
                        scene_number=scene_number,
                        width=width,
                        height=height,
                        generate_attempt=generate_quality_attempt
                    )
                )
                if quality_result.status != "approved":
                    raise RuntimeError(
                        "La validacion de imagen requiere "
                        "intervencion antes de continuar: "
                        f"{quality_result.status}"
                    )
                image_path = retry_paths.get(
                    quality_result.generated_asset.attempt_number,
                    image_path
                )

            generation_result = (
                GenerationResultAdapter.from_image_result(
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
        profile=None
    ):
        effective_visual_brief = (
            self._build_runtime_effective_visual_brief(
                storyboard_scene=storyboard_scene,
                profile=profile
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
                cinematic_direction_set=cinematic_direction_set
            )
        )
        payload = (
            self._backend_adapter().adapt(
                backend_prompt
            )
        )
        operational_prompt = (
            self.prompt_system.compose_cinematic_backend_prompt(
                payload.prompt
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
            ),
            "backend_adapter_payload_fingerprint": (
                payload.fingerprint
            ),
            "operational_prompt_fingerprint": (
                self._text_fingerprint(
                    operational_prompt
                )
            ),
            "backend_payload_prompt": payload.prompt,
            "operational_prompt": operational_prompt
        }

    def _build_runtime_effective_visual_brief(
        self,
        storyboard_scene,
        profile=None
    ):
        adaptation = (
            RuntimeCognitiveAdapter.from_storyboard_scene(
                storyboard_scene=storyboard_scene,
                orientation=str(
                    (
                        profile
                        or {}
                    ).get(
                        "format",
                        ""
                    )
                )
            )
        )
        source_id = (
            f"scene_{storyboard_scene.scene_number:03d}"
        )
        source_version = (
            "image-component-runtime-v1"
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
            trace=self._runtime_visual_brief_trace(
                adaptation=adaptation
            ),
            conflicts=(),
            fingerprint=fingerprint,
            source_id=source_id,
            source_version=source_version
        )

    def _runtime_visual_brief_trace(
        self,
        adaptation
    ):
        origins = []
        visual_brief = adaptation.visual_brief

        self._add_runtime_origin(
            origins,
            field="VisualBrief.visible_content",
            source_path=self._visible_content_source_path(
                visual_brief
            ),
            action=self._visible_content_origin_action(
                visual_brief
            )
        )
        direct_mappings = (
            (
                "VisualBrief.visible_subject",
                "StoryboardScene.visible_subject",
                visual_brief.visible_subject,
            ),
            (
                "VisualBrief.visible_action",
                "StoryboardScene.visible_action",
                visual_brief.visible_action,
            ),
            (
                "VisualBrief.visible_environment",
                "StoryboardScene.visible_environment",
                visual_brief.visible_environment,
            ),
            (
                "VisualBrief.time_context",
                "StoryboardScene.time_context",
                visual_brief.time_context,
            ),
            (
                "VisualBrief.key_objects",
                "StoryboardScene.key_objects",
                visual_brief.key_objects,
            ),
            (
                "VisualBrief.spatial_relationships",
                "StoryboardScene.spatial_relationships",
                visual_brief.spatial_relationships,
            ),
            (
                "VisualBrief.continuity_links",
                "StoryboardScene.continuity_links",
                visual_brief.continuity_links,
            ),
            (
                "VisualBrief.abstract_source",
                "StoryboardScene.abstract_source",
                visual_brief.abstract_source,
            ),
            (
                "VisualBrief.filmable_interpretation",
                "StoryboardScene.filmable_interpretation",
                visual_brief.filmable_interpretation,
            ),
            (
                "VisualBrief.visual_constraints",
                "StoryboardScene.visual_constraints",
                visual_brief.visual_constraints,
            ),
            (
                "VisualBrief.visual_truth_status",
                "StoryboardScene.visual_truth_status",
                visual_brief.visual_truth_status,
            ),
        )
        for field, source_path, value in direct_mappings:
            if value:
                self._add_runtime_origin(
                    origins,
                    field=field,
                    source_path=source_path,
                    action=self._source_path_action(
                        source_path
                    )
                )

        return VisualBriefTrace(
            field_origins=tuple(
                origins
            )
        )

    def _visible_content_source_path(
        self,
        visual_brief
    ):
        if visual_brief.filmable_interpretation:
            return "StoryboardScene.filmable_interpretation"
        if (
            visual_brief.visible_subject
            or visual_brief.visible_action
            or visual_brief.visible_environment
            or visual_brief.time_context
        ):
            return "StoryboardScene.visual_truth"
        return "StoryboardScene.text"

    def _visible_content_origin_action(
        self,
        visual_brief
    ):
        source_path = self._visible_content_source_path(
            visual_brief
        )
        return self._source_path_action(
            source_path
        )

    def _source_path_action(
        self,
        source_path
    ):
        return "preserve_visual_truth"

    def _add_runtime_origin(
        self,
        origins,
        field,
        source_path,
        action
    ):
        origins.append(
            VisualBriefFieldOrigin(
                field=field,
                source_layer="RuntimeCognitiveAdapter",
                source_path=source_path,
                action=action
            )
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

    def _backend_adapter(
        self
    ):
        if self.backend_adapter is None:
            self.backend_adapter = (
                ComfyUIAdapter()
            )

        return self.backend_adapter

    def _image_quality_flow(
        self
    ):
        if self.image_quality_flow is None:
            self.image_quality_flow = (
                ImageQualityFlowCoordinator()
            )

        return self.image_quality_flow

    def _text_fingerprint(
        self,
        value
    ):
        return hashlib.sha256(
            str(
                value
                or ""
            ).encode(
                "utf-8"
            )
        ).hexdigest()

    def _is_image_validation_enabled(
        self,
        profile
    ):
        image_validation = profile.get(
            "image_validation",
            {}
        )

        if not isinstance(
            image_validation,
            dict
        ):
            return False

        return bool(
            image_validation.get(
                "enabled",
                False
            )
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
