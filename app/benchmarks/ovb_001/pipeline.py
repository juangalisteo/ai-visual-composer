from pathlib import Path

from app.backend_adapters import ComfyUIAdapter
from app.benchmarks.ovb_001.image import RealBackendBenchmarkImageGenerator
from app.benchmarks.ovb_001.models import (
    BenchmarkExecutionConfig,
    BenchmarkScene,
    BenchmarkSceneRun,
)
from app.benchmarks.ovb_001.serialization import fingerprint, write_json
from app.prompt_translation import PromptTranslator
from app.visual_quality import ImageQualityFlowCoordinator
from app.visual_intelligence import (
    VisualAnalysisOrchestrator,
    VisualReasoningOrchestrator,
    VisualSynthesisOrchestrator,
)


class OVB001ExecutionPipeline:
    def __init__(
        self,
        prompt_translator: PromptTranslator | None = None,
        image_generator: RealBackendBenchmarkImageGenerator | None = None,
        image_quality_flow: ImageQualityFlowCoordinator | None = None,
    ) -> None:
        self.prompt_translator = prompt_translator or PromptTranslator()
        self.image_generator = (
            image_generator
            or RealBackendBenchmarkImageGenerator()
        )
        self.analysis_orchestrator = VisualAnalysisOrchestrator()
        self.reasoning_orchestrator = VisualReasoningOrchestrator()
        self.synthesis_orchestrator = VisualSynthesisOrchestrator()
        self.backend_adapter = ComfyUIAdapter()
        self.image_quality_flow = (
            image_quality_flow
            or ImageQualityFlowCoordinator()
        )

    def execute(
        self,
        scene: BenchmarkScene,
        variant: str,
        config: BenchmarkExecutionConfig,
        output_dir: Path,
    ) -> BenchmarkSceneRun:
        variant_dir = output_dir / variant
        variant_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        analysis = self.analysis_orchestrator.analyze(
            scene.scene
        )
        reasoning = self.reasoning_orchestrator.reason(
            analysis
        )
        synthesis = self.synthesis_orchestrator.synthesize(
            analysis,
            reasoning,
        )
        backend_prompt = self.prompt_translator.translate_visual_synthesis_result(
            synthesis
        )
        prompt_observation = self.prompt_translator.last_observation
        payload = self.backend_adapter.adapt(
            backend_prompt
        )
        generated_image = self.image_generator.generate(
            scene,
            payload,
            config,
            variant_dir,
        )
        quality_flow_result = self.image_quality_flow.evaluate(
            image_path=Path(
                generated_image.path
            ),
            scene_number=scene.scene.scene_number,
            width=config.width,
            height=config.height,
            sequence_id=scene.identifier,
        )
        visual_quality_result = _quality_result_payload(
            quality_flow_result
        )

        artifacts = {
            "scene": (variant_dir / "scene.json").as_posix(),
            "visual_analysis_result": (variant_dir / "visual_analysis_result.json").as_posix(),
            "visual_reasoning_result": (variant_dir / "visual_reasoning_result.json").as_posix(),
            "visual_conflict_report": (variant_dir / "visual_conflict_report.json").as_posix(),
            "effective_visual_brief": (variant_dir / "effective_visual_brief.json").as_posix(),
            "visual_synthesis_result": (variant_dir / "visual_synthesis_result.json").as_posix(),
            "prompt_translation_observation": (variant_dir / "prompt_translation_observation.json").as_posix(),
            "backend_prompt": (variant_dir / "backend_prompt.json").as_posix(),
            "compiled_prompt": (variant_dir / "compiled_prompt.txt").as_posix(),
            "comfyui_payload": (variant_dir / "comfyui_payload.json").as_posix(),
            "generation_metadata": (variant_dir / "generation_metadata.json").as_posix(),
            "generated_image": generated_image.path,
            "visual_quality_result": (variant_dir / "visual_quality_result.json").as_posix(),
        }

        fingerprints = {
            "scene": write_json(
                variant_dir / "scene.json",
                scene,
            ),
            "visual_analysis_result": write_json(
                variant_dir / "visual_analysis_result.json",
                analysis,
            ),
            "visual_reasoning_result": write_json(
                variant_dir / "visual_reasoning_result.json",
                reasoning,
            ),
            "visual_conflict_report": write_json(
                variant_dir / "visual_conflict_report.json",
                synthesis.conflicts,
            ),
            "effective_visual_brief": write_json(
                variant_dir / "effective_visual_brief.json",
                synthesis.brief,
            ),
            "visual_synthesis_result": write_json(
                variant_dir / "visual_synthesis_result.json",
                synthesis,
            ),
            "prompt_translation_observation": write_json(
                variant_dir / "prompt_translation_observation.json",
                prompt_observation,
            ),
            "backend_prompt": write_json(
                variant_dir / "backend_prompt.json",
                backend_prompt,
            ),
            "comfyui_payload": write_json(
                variant_dir / "comfyui_payload.json",
                payload,
            ),
            "generation_metadata": fingerprint(
                "generation_metadata",
                generated_image.metadata,
            ),
            "generated_image": generated_image.fingerprint,
            "visual_quality_result": write_json(
                variant_dir / "visual_quality_result.json",
                visual_quality_result,
            ),
        }
        (variant_dir / "compiled_prompt.txt").write_text(
            backend_prompt.compiled_prompt,
            encoding="utf-8",
        )
        fingerprints[
            "compiled_prompt"
        ] = fingerprint(
            "compiled_prompt",
            backend_prompt.compiled_prompt,
        )

        return BenchmarkSceneRun(
            scene=scene,
            variant=variant,
            artifacts=artifacts,
            fingerprints=fingerprints,
            compiled_prompt=backend_prompt.compiled_prompt,
            generation_metadata=generated_image.metadata,
            generated_image=generated_image,
            visual_quality_result=visual_quality_result,
        )


def _quality_result_payload(
    quality_result
) -> dict:
    report = quality_result.history.validation_reports[-1]
    decision = quality_result.history.regeneration_decisions[-1]
    return {
        "status": quality_result.status,
        "result_fingerprint": quality_result.result_fingerprint,
        "generated_asset": {
            "asset_id": quality_result.generated_asset.asset_id,
            "scene_id": quality_result.generated_asset.scene_id,
            "attempt_number": quality_result.generated_asset.attempt_number,
            "asset_type": quality_result.generated_asset.asset_type,
            "width": quality_result.generated_asset.width,
            "height": quality_result.generated_asset.height,
            "generation_fingerprint": (
                quality_result.generated_asset.generation_fingerprint
            ),
        },
        "history": {
            "status": quality_result.history.status,
            "history_fingerprint": quality_result.history.history_fingerprint,
            "generated_assets": len(
                quality_result.history.generated_assets
            ),
            "validation_reports": len(
                quality_result.history.validation_reports
            ),
            "regeneration_decisions": len(
                quality_result.history.regeneration_decisions
            ),
        },
        "validation_report": {
            "status": report.status,
            "score": report.score,
            "severity": report.severity,
            "checks": report.checks,
            "failures": tuple(
                failure.failure_type
                for failure in report.failures
            ),
            "validation_fingerprint": report.validation_fingerprint,
        },
        "decision": {
            "action": decision.action,
            "reason": decision.reason,
            "decision_fingerprint": decision.decision_fingerprint,
        },
    }
