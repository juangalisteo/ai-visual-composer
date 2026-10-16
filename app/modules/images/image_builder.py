from pathlib import Path
from dataclasses import asdict, replace
import json
import shutil
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
from app.shared.config_contract import (
    require_bool,
    require_mapping,
    require_text,
)
from app.shared.config_manager import ConfigManager
from app.shared.progress_logger import ProgressLogger
from app.shared.error_context import (
    ErrorContext,
    ErrorSeverity,
    ExitKind,
)
from app.shared.operational_error import OperationalError
from app.modules.images.manifest_writer import ImageManifestWriter
from app.modules.images.prompt_system import ImagePromptSystem
from app.prompt_translation import (
    PromptTranslator,
    build_operational_prompt_observation,
    prompt_fingerprint,
    validate_operational_prompt,
)
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
        evidence_writer=None,
        profile=None
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
        self.profile = profile

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

        profile = (
            self.profile
            if self.profile is not None
            else ConfigManager().get_profile_config()
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
                self._generate_validated_image(
                    prompt=prompt,
                    scene_number=scene_number,
                    output_dir=output_dir,
                    width=width,
                    height=height,
                    operational_prompt_observation=(
                        runtime_metadata[
                            "_operational_prompt_observation"
                        ]
                    ),
                )
            )

            if (
                self._is_image_validation_enabled(
                    profile
                )
                or self._is_nudity_safety_enabled()
            ):
                retry_paths = {}

                def generate_quality_attempt(
                    attempt_number,
                    seed
                ):
                    retry_number = attempt_number - 1
                    attempt_dir = (
                        output_dir
                        / "_quality_attempts"
                        / f"scene_{scene_number:03d}"
                        / f"attempt_{retry_number:03d}"
                    )
                    attempt_dir.mkdir(
                        parents=True,
                        exist_ok=True,
                    )
                    attempt_path = (
                        self._generate_validated_image(
                            prompt=prompt,
                            scene_number=scene_number,
                            output_dir=attempt_dir,
                            width=width,
                            height=height,
                            operational_prompt_observation=(
                                runtime_metadata[
                                    "_operational_prompt_observation"
                                ]
                            ),
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
                quality_evidence = None
                if self._is_visual_quality_result(
                    quality_result
                ):
                    quality_evidence = (
                        self._evidence_writer().write_visual_quality_result(
                            output_dir=output_dir,
                            scene_number=scene_number,
                            visual_quality_result=quality_result,
                        )
                    )
                if hasattr(quality_result, "history"):
                    prompt_metadata["visual_quality"] = (
                        self._visual_quality_trace(quality_result)
                )
                if quality_result.status == "manual_review":
                    raise self._manual_review_required_error(
                        quality_result=quality_result,
                        quality_evidence=quality_evidence,
                        scene_number=scene_number,
                    )
                if quality_result.status != "approved":
                    raise RuntimeError(
                        "La validación de imagen requiere "
                        "intervencion antes de continuar: "
                        f"{quality_result.status}"
                    )
                accepted_retry_path = retry_paths.get(
                    quality_result.generated_asset.attempt_number,
                )
                if accepted_retry_path is not None:
                    shutil.copy2(
                        accepted_retry_path,
                        image_path,
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
        operational_prompt_composition = (
            self.prompt_system.compose_cinematic_backend_prompt_with_parts(
                payload.prompt
            )
        )
        operational_prompt_observation = (
            build_operational_prompt_observation(
                compiled_prompt=payload.prompt,
                operational_prompt=(
                    operational_prompt_composition.prompt
                ),
                budget_policy=backend_prompt.budget_policy,
                composition_parts=(
                    operational_prompt_composition.parts
                ),
            )
        )
        if evidence_output_dir is not None:
            self._evidence_writer().write_operational_prompt_observation(
                output_dir=evidence_output_dir,
                scene_number=storyboard_scene.scene_number,
                operational_prompt_observation=(
                    operational_prompt_observation
                ),
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
                operational_prompt_observation.operational_prompt.fingerprint
            ),
            "operational_prompt_observation": asdict(
                operational_prompt_observation
            ),
            "backend_payload_prompt": payload.prompt,
            "operational_prompt": (
                operational_prompt_composition.prompt
            ),
            "_operational_prompt_observation": (
                operational_prompt_observation
            ),
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
        image_format = require_text(
            profile,
            "format",
            "format"
        ).lower()
        if image_format == "vertical":
            return "vertical 9:16"
        if image_format == "horizontal":
            return "wide horizontal 16:9"
        raise ValueError(
            "La configuracion format debe ser vertical "
            "u horizontal."
        )

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

    def _manual_review_required_error(
        self,
        *,
        quality_result,
        quality_evidence,
        scene_number,
    ):
        """Translate a review outcome without turning it into approval."""
        asset = getattr(
            quality_result,
            "generated_asset",
            None,
        )
        history = getattr(
            quality_result,
            "history",
            None,
        )
        marker = getattr(
            quality_result,
            "manual_review_marker",
            None,
        )
        scene_id = getattr(
            asset,
            "scene_id",
            f"scene_{scene_number:03d}",
        )
        resource = getattr(asset, "path", None)
        technical_metadata = {
            "validation_status": "manual_review",
            "scene_id": scene_id,
            "attempt_count": len(
                getattr(history, "generated_assets", ())
            ),
            "history_fingerprint": getattr(
                history,
                "history_fingerprint",
                "",
            ),
            "manual_review_marker": getattr(
                marker,
                "marker_id",
                "",
            ),
            "quality_result_fingerprint": getattr(
                quality_result,
                "result_fingerprint",
                "",
            ),
        }
        if quality_evidence is not None:
            technical_metadata["evidence_index"] = str(
                quality_evidence.index_path
            )

        return OperationalError(
            ErrorContext(
                family="VALIDATION",
                severity=ErrorSeverity.FATAL_OPERATIONAL,
                user_message=(
                    "La imagen candidata requiere revision manual "
                    "antes de continuar."
                ),
                recommended_action=(
                    "Revise la imagen candidata y la evidencia de "
                    "validacion; no se ha aprobado como asset final."
                ),
                operation=(
                    "Validar calidad visual de "
                    f"{scene_id}"
                ),
                resource=str(resource) if resource else None,
                diagnostic_reference=(
                    str(quality_evidence.artifact_path)
                    if quality_evidence is not None
                    else None
                ),
                technical_metadata=technical_metadata,
                exit_kind=ExitKind.OPERATIONAL_ERROR,
            )
        )

    def _generate_validated_image(
        self,
        prompt,
        scene_number,
        output_dir,
        width,
        height,
        operational_prompt_observation,
    ):
        if (
            operational_prompt_observation.operational_prompt.fingerprint
            != prompt_fingerprint(
                prompt
            )
        ):
            raise RuntimeError(
                "El prompt operativo cambió después de su observación "
                "y antes de enviarlo a ComfyUI."
            )
        validate_operational_prompt(
            operational_prompt_observation
        )
        return self._generate_image(
            prompt=prompt,
            scene_number=scene_number,
            output_dir=output_dir,
            width=width,
            height=height,
        )

    def _is_image_validation_enabled(
        self,
        profile
    ):
        image_validation = require_mapping(
            profile,
            "image_validation",
            "image_validation"
        )
        return require_bool(
            image_validation,
            "enabled",
            "image_validation.enabled"
        )

    def _is_nudity_safety_enabled(
        self
    ):
        return True

    def _visual_quality_trace(
        self,
        quality_result,
    ):
        latest_report = (
            quality_result.history.validation_reports[-1]
        )
        return {
            "status": quality_result.status,
            "attempts": len(
                quality_result.history.generated_assets
            ),
            "checks": latest_report.checks,
            "failure_types": tuple(
                failure.failure_type
                for failure in latest_report.failures
            ),
            "decision": (
                quality_result.history.regeneration_decisions[-1].reason
            ),
            "nudity_detected": any(
                failure.failure_type == "nudity_detected"
                for failure in latest_report.failures
            ),
            "forced_accept": (
                quality_result.history.regeneration_decisions[-1]
                .forced_accept
            ),
        }

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
