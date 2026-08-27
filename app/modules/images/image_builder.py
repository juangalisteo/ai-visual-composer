from pathlib import Path
from dataclasses import replace
import json
import hashlib
import time

from app.backend_adapters import ComfyUIAdapter
from app.cinematic_direction import CinematicDirectionOrchestrator
from app.evidence import ImageEvidenceWriter
from app.managers.project_manager import ProjectManager
from app.domain.adapters import (
    GenerationResultAdapter,
    StoryboardSceneAdapter
)
from app.modules.images.backends import ComfyUIBackend
from app.shared.config_manager import ConfigManager
from app.shared.progress_logger import ProgressLogger
from app.modules.images.manifest_writer import ImageManifestWriter
from app.modules.images.prompt_system import ImagePromptSystem
from app.prompt_translation import PromptTranslator
from app.visual_intelligence import (
    VisualAnalysisOrchestrator,
    VisualReasoningOrchestrator,
    VisualSynthesisOrchestrator,
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
        visual_analysis_orchestrator=None,
        visual_reasoning_orchestrator=None,
        visual_synthesis_orchestrator=None,
        backend_adapter=None,
        image_quality_flow=None,
        evidence_writer=None
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
        self.visual_analysis_orchestrator = visual_analysis_orchestrator
        self.visual_reasoning_orchestrator = visual_reasoning_orchestrator
        self.visual_synthesis_orchestrator = visual_synthesis_orchestrator
        self.backend_adapter = backend_adapter
        self.image_quality_flow = image_quality_flow
        self.evidence_writer = evidence_writer

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

            if not self._has_visual_truth_content(
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
                    evidence_output_dir=output_dir,
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
                if self._is_visual_quality_result(
                    quality_result
                ):
                    self._evidence_writer().write_visual_quality_result(
                        output_dir=output_dir,
                        scene_number=scene_number,
                        visual_quality_result=quality_result,
                    )
                if quality_result.status != "approved":
                    raise RuntimeError(
                        "La validación de imagen requiere "
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
        profile=None,
        evidence_output_dir=None
    ):
        visual_synthesis_result = (
            self._build_runtime_visual_synthesis_result(
                storyboard_scene=storyboard_scene,
                profile=profile,
                evidence_output_dir=evidence_output_dir
            )
        )
        effective_brief = visual_synthesis_result.brief
        cinematic_direction_set = (
            self._cinematic_orchestrator().resolve(
                effective_brief
            )
        )
        prompt_translator = self._prompt_translator()
        backend_prompt = (
            prompt_translator.translate_visual_synthesis_result(
                visual_synthesis_result,
                cinematic_direction_set=cinematic_direction_set
            )
        )
        prompt_translation_observation = getattr(
            prompt_translator,
            "last_observation",
            None,
        )
        if (
            evidence_output_dir is not None
            and prompt_translation_observation is not None
        ):
            self._evidence_writer().write_prompt_translation_observation(
                output_dir=evidence_output_dir,
                scene_number=storyboard_scene.scene_number,
                prompt_translation_observation=prompt_translation_observation,
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
            "visual_synthesis_result_fingerprint": (
                visual_synthesis_result.fingerprint
            ),
            "visual_intelligence_trace_fingerprint": (
                visual_synthesis_result.trace.fingerprint
            ),
            "visual_conflict_report_fingerprint": (
                visual_synthesis_result.conflicts.fingerprint
            ),
            "effective_brief_fingerprint": (
                effective_brief.fingerprint
            ),
            "cinematic_direction_set_fingerprint": (
                cinematic_direction_set.fingerprint
            ),
            "backend_prompt_fingerprint": (
                backend_prompt.fingerprint
            ),
            "prompt_translation_metrics": {
                "prompt_char_count": (
                    backend_prompt.metrics.prompt_char_count
                ),
                "prompt_word_count": (
                    backend_prompt.metrics.prompt_word_count
                ),
                "prompt_token_count": (
                    backend_prompt.metrics.prompt_token_count
                ),
                "token_count_method": (
                    backend_prompt.metrics.token_count_method
                ),
                "target_budget": (
                    backend_prompt.metrics.target_budget
                ),
                "warning_threshold": (
                    backend_prompt.metrics.warning_threshold
                ),
                "hard_limit": (
                    backend_prompt.metrics.hard_limit
                ),
                "compactation_applied": (
                    backend_prompt.metrics.compactation_applied
                ),
                "compactation_stages": (
                    backend_prompt.metrics.compactation_stages
                ),
                "duplicate_fragments_removed": (
                    backend_prompt.metrics.duplicate_fragments_removed
                ),
                "non_visual_fields_removed": (
                    backend_prompt.metrics.non_visual_fields_removed
                ),
                "semantic_duplicates_removed": (
                    backend_prompt.metrics.semantic_duplicates_removed
                ),
                "budget_policy": (
                    backend_prompt.budget_policy.policy_id
                ),
                "model": (
                    backend_prompt.budget_policy.model_id
                ),
                "encoder": (
                    backend_prompt.budget_policy.encoder_id
                ),
            },
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

    def _build_runtime_visual_synthesis_result(
        self,
        storyboard_scene,
        profile=None,
        evidence_output_dir=None
    ):
        storyboard_scene = self._with_profile_visual_constraints(
            storyboard_scene,
            profile
        )
        analysis = (
            self._visual_analysis_orchestrator().analyze(
                storyboard_scene
            )
        )
        if evidence_output_dir is not None:
            self._evidence_writer().write_visual_analysis_result(
                output_dir=evidence_output_dir,
                scene_number=storyboard_scene.scene_number,
                visual_analysis_result=analysis,
            )
        reasoning = (
            self._visual_reasoning_orchestrator().reason(
                analysis
            )
        )
        if evidence_output_dir is not None:
            self._evidence_writer().write_visual_reasoning_result(
                output_dir=evidence_output_dir,
                scene_number=storyboard_scene.scene_number,
                visual_reasoning_result=reasoning,
            )
        synthesis_result = self._visual_synthesis_orchestrator().synthesize(
            analysis,
            reasoning,
        )
        if evidence_output_dir is not None:
            self._evidence_writer().write_visual_conflict_report(
                output_dir=evidence_output_dir,
                scene_number=storyboard_scene.scene_number,
                visual_conflict_report=synthesis_result.conflicts,
            )
            self._evidence_writer().write_effective_visual_brief(
                output_dir=evidence_output_dir,
                scene_number=storyboard_scene.scene_number,
                effective_visual_brief=synthesis_result.brief,
            )
            self._evidence_writer().write_visual_synthesis_result(
                output_dir=evidence_output_dir,
                scene_number=storyboard_scene.scene_number,
                visual_synthesis_result=synthesis_result,
            )
        return synthesis_result

    def _with_profile_visual_constraints(
        self,
        storyboard_scene,
        profile=None
    ):
        guidance = self._profile_format_guidance(
            profile
        )
        if (
            not guidance
            or guidance in storyboard_scene.visual_constraints
        ):
            return storyboard_scene
        return replace(
            storyboard_scene,
            visual_constraints=(
                storyboard_scene.visual_constraints
                + (
                    guidance,
                )
            ),
        )

    def _profile_format_guidance(
        self,
        profile=None
    ):
        if not profile:
            return ""
        video_style = profile.get(
            "video_style",
            {}
        )
        image_format = str(
            profile.get(
                "format",
                ""
            )
            or ""
        ).lower()
        width = video_style.get(
            "width"
        )
        height = video_style.get(
            "height"
        )
        if image_format == "vertical":
            return "vertical 9:16"
        if image_format == "horizontal":
            return "wide horizontal 16:9"
        if width and height:
            if int(
                height
            ) > int(
                width
            ):
                return "vertical 9:16"
            if int(
                width
            ) > int(
                height
            ):
                return "wide horizontal 16:9"
        return ""

    def _has_visual_truth_content(
        self,
        storyboard_scene
    ):
        values = (
            storyboard_scene.visible_subject,
            storyboard_scene.visible_action,
            storyboard_scene.visible_environment,
            storyboard_scene.time_context,
            storyboard_scene.abstract_source,
            storyboard_scene.filmable_interpretation,
        )
        sequences = (
            storyboard_scene.key_objects,
            storyboard_scene.spatial_relationships,
            storyboard_scene.continuity_links,
            storyboard_scene.visual_constraints,
        )
        return any(
            str(
                value
                or ""
            ).strip()
            for value in values
        ) or any(
            sequence
            for sequence in sequences
        )

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

    def _visual_analysis_orchestrator(
        self
    ):
        if self.visual_analysis_orchestrator is None:
            self.visual_analysis_orchestrator = (
                VisualAnalysisOrchestrator()
            )

        return self.visual_analysis_orchestrator

    def _visual_reasoning_orchestrator(
        self
    ):
        if self.visual_reasoning_orchestrator is None:
            self.visual_reasoning_orchestrator = (
                VisualReasoningOrchestrator()
            )

        return self.visual_reasoning_orchestrator

    def _visual_synthesis_orchestrator(
        self
    ):
        if self.visual_synthesis_orchestrator is None:
            self.visual_synthesis_orchestrator = (
                VisualSynthesisOrchestrator()
            )

        return self.visual_synthesis_orchestrator

    def _backend_adapter(
        self
    ):
        if self.backend_adapter is None:
            self.backend_adapter = (
                ComfyUIAdapter()
            )

        return self.backend_adapter

    def _evidence_writer(
        self
    ):
        if self.evidence_writer is None:
            self.evidence_writer = (
                ImageEvidenceWriter()
            )

        return self.evidence_writer

    def _image_quality_flow(
        self
    ):
        if self.image_quality_flow is None:
            self.image_quality_flow = (
                ImageQualityFlowCoordinator()
            )

        return self.image_quality_flow

    def _is_visual_quality_result(
        self,
        quality_result
    ):
        return (
            hasattr(
                quality_result,
                "result_fingerprint"
            )
            and hasattr(
                quality_result,
                "history"
            )
        )

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
