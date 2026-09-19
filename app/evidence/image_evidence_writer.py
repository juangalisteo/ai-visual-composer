import json
from dataclasses import asdict, dataclass, is_dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Any

from app.domain import (
    EffectiveVisualBrief,
    VisualAnalysisResult,
    VisualConflictReport,
    VisualReasoningResult,
    VisualSynthesisResult,
)
from app.evidence.image_evidence_index import (
    EvidenceArtifactReference,
    EvidenceArtifactStatus,
    ImageEvidenceIndex,
    build_image_evidence_index,
    deterministic_fingerprint,
)
from app.evidence.image_evidence_policy import ImageEvidencePathPolicy
from app.prompt_translation import (
    OperationalPromptObservation,
    PromptTranslationObservation,
)


@dataclass(frozen=True)
class EvidenceWriteResult:
    artifact_path: Path
    index_path: Path
    artifact_fingerprint: str
    index_fingerprint: str


class ImageEvidenceWriter:
    def __init__(
        self,
        policy: ImageEvidencePathPolicy | None = None,
    ) -> None:
        self.policy = policy or ImageEvidencePathPolicy()

    def write_visual_analysis_result(
        self,
        output_dir: Path | str,
        scene_number: int,
        visual_analysis_result: VisualAnalysisResult,
    ) -> EvidenceWriteResult:
        if not isinstance(
            visual_analysis_result,
            VisualAnalysisResult,
        ):
            raise TypeError(
                "ImageEvidenceWriter expects a VisualAnalysisResult."
            )

        return self._write_runtime_artifact(
            output_dir=output_dir,
            scene_number=scene_number,
            artifact_id="visual_analysis_result",
            artifact_payload=_canonical_mapping(
                visual_analysis_result
            ),
            fingerprint_label="visual_analysis_result_artifact",
        )

    def write_visual_reasoning_result(
        self,
        output_dir: Path | str,
        scene_number: int,
        visual_reasoning_result: VisualReasoningResult,
    ) -> EvidenceWriteResult:
        if not isinstance(
            visual_reasoning_result,
            VisualReasoningResult,
        ):
            raise TypeError(
                "ImageEvidenceWriter expects a VisualReasoningResult."
            )

        return self._write_runtime_artifact(
            output_dir=output_dir,
            scene_number=scene_number,
            artifact_id="visual_reasoning_result",
            artifact_payload=_canonical_mapping(
                visual_reasoning_result
            ),
            fingerprint_label="visual_reasoning_result_artifact",
        )

    def write_visual_conflict_report(
        self,
        output_dir: Path | str,
        scene_number: int,
        visual_conflict_report: VisualConflictReport,
    ) -> EvidenceWriteResult:
        if not isinstance(
            visual_conflict_report,
            VisualConflictReport,
        ):
            raise TypeError(
                "ImageEvidenceWriter expects a VisualConflictReport."
            )

        return self._write_runtime_artifact(
            output_dir=output_dir,
            scene_number=scene_number,
            artifact_id="visual_conflict_report",
            artifact_payload=_canonical_mapping(
                visual_conflict_report
            ),
            fingerprint_label="visual_conflict_report_artifact",
        )

    def write_effective_visual_brief(
        self,
        output_dir: Path | str,
        scene_number: int,
        effective_visual_brief: EffectiveVisualBrief,
    ) -> EvidenceWriteResult:
        if not isinstance(
            effective_visual_brief,
            EffectiveVisualBrief,
        ):
            raise TypeError(
                "ImageEvidenceWriter expects an EffectiveVisualBrief."
            )

        return self._write_runtime_artifact(
            output_dir=output_dir,
            scene_number=scene_number,
            artifact_id="effective_visual_brief",
            artifact_payload=_canonical_mapping(
                effective_visual_brief
            ),
            fingerprint_label="effective_visual_brief_artifact",
        )

    def write_visual_synthesis_result(
        self,
        output_dir: Path | str,
        scene_number: int,
        visual_synthesis_result: VisualSynthesisResult,
    ) -> EvidenceWriteResult:
        if not isinstance(
            visual_synthesis_result,
            VisualSynthesisResult,
        ):
            raise TypeError(
                "ImageEvidenceWriter expects a VisualSynthesisResult."
            )

        return self._write_runtime_artifact(
            output_dir=output_dir,
            scene_number=scene_number,
            artifact_id="visual_synthesis_result",
            artifact_payload=_canonical_mapping(
                visual_synthesis_result
            ),
            fingerprint_label="visual_synthesis_result_artifact",
        )

    def write_prompt_translation_observation(
        self,
        output_dir: Path | str,
        scene_number: int,
        prompt_translation_observation: PromptTranslationObservation,
    ) -> EvidenceWriteResult:
        if not isinstance(
            prompt_translation_observation,
            PromptTranslationObservation,
        ):
            raise TypeError(
                "ImageEvidenceWriter expects a PromptTranslationObservation."
            )

        return self._write_runtime_artifact(
            output_dir=output_dir,
            scene_number=scene_number,
            artifact_id="prompt_translation_observation",
            artifact_payload=_canonical_mapping(
                prompt_translation_observation
            ),
            fingerprint_label="prompt_translation_observation_artifact",
        )

    def write_operational_prompt_observation(
        self,
        output_dir: Path | str,
        scene_number: int,
        operational_prompt_observation: OperationalPromptObservation,
    ) -> EvidenceWriteResult:
        if not isinstance(
            operational_prompt_observation,
            OperationalPromptObservation,
        ):
            raise TypeError(
                "ImageEvidenceWriter expects an "
                "OperationalPromptObservation."
            )

        return self._write_runtime_artifact(
            output_dir=output_dir,
            scene_number=scene_number,
            artifact_id="operational_prompt_observation",
            artifact_payload=_canonical_mapping(
                operational_prompt_observation
            ),
            fingerprint_label="operational_prompt_observation_artifact",
        )

    def write_visual_quality_result(
        self,
        output_dir: Path | str,
        scene_number: int,
        visual_quality_result: Any,
    ) -> EvidenceWriteResult:
        return self._write_runtime_artifact(
            output_dir=output_dir,
            scene_number=scene_number,
            artifact_id="visual_quality_result",
            artifact_payload=_canonical_mapping(
                visual_quality_result
            ),
            fingerprint_label="visual_quality_result_artifact",
        )

    def _write_runtime_artifact(
        self,
        output_dir: Path | str,
        scene_number: int,
        artifact_id: str,
        artifact_payload: dict[str, Any],
        fingerprint_label: str,
    ) -> EvidenceWriteResult:
        artifact_path = self.policy.artifact_path(
            output_dir,
            scene_number,
            artifact_id,
        )
        index_path = self.policy.index_path(
            output_dir,
            scene_number,
        )
        artifact_fingerprint = deterministic_fingerprint(
            fingerprint_label,
            artifact_payload,
        )

        _write_json(
            artifact_path,
            artifact_payload,
        )
        index = _mark_artifact_available(
            _load_or_build_index(
                index_path=index_path,
                scene_number=scene_number,
                policy=self.policy,
            ),
            artifact_id,
            artifact_fingerprint,
        )
        _write_json(
            index_path,
            index.to_dict(),
        )

        return EvidenceWriteResult(
            artifact_path=artifact_path,
            index_path=index_path,
            artifact_fingerprint=artifact_fingerprint,
            index_fingerprint=index.fingerprint,
        )


def _mark_artifact_available(
    index: ImageEvidenceIndex,
    artifact_id: str,
    artifact_fingerprint: str,
) -> ImageEvidenceIndex:
    artifacts = tuple(
        _available_reference(
            artifact,
            artifact_fingerprint,
        )
        if artifact.artifact_id == artifact_id
        else artifact
        for artifact in index.artifacts
    )
    return replace(
        index,
        artifacts=artifacts,
    )


def _load_or_build_index(
    index_path: Path,
    scene_number: int,
    policy: ImageEvidencePathPolicy,
) -> ImageEvidenceIndex:
    if not index_path.exists():
        return build_image_evidence_index(
            scene_number,
            policy=policy,
        )
    return _merge_existing_index(
        build_image_evidence_index(
            scene_number,
            policy=policy,
        ),
        json.loads(
            index_path.read_text(
                encoding="utf-8"
            )
        ),
    )


def _merge_existing_index(
    base_index: ImageEvidenceIndex,
    existing_payload: dict[str, Any],
) -> ImageEvidenceIndex:
    existing_artifacts = {
        artifact.get(
            "artifact_id",
            ""
        ): artifact
        for artifact in existing_payload.get(
            "artifacts",
            []
        )
        if isinstance(
            artifact,
            dict,
        )
    }
    artifacts = tuple(
        _reference_from_existing(
            artifact,
            existing_artifacts.get(
                artifact.artifact_id
            )
        )
        for artifact in base_index.artifacts
    )
    return replace(
        base_index,
        artifacts=artifacts,
    )


def _reference_from_existing(
    base_artifact: EvidenceArtifactReference,
    existing_artifact: dict[str, Any] | None,
) -> EvidenceArtifactReference:
    if not existing_artifact:
        return base_artifact
    status = EvidenceArtifactStatus(
        existing_artifact.get(
            "status",
            base_artifact.status.value,
        )
    )
    return EvidenceArtifactReference(
        artifact_id=base_artifact.artifact_id,
        filename=base_artifact.filename,
        relative_path=base_artifact.relative_path,
        status=status,
        fingerprint=str(
            existing_artifact.get(
                "fingerprint",
                base_artifact.fingerprint,
            )
            or ""
        ),
    )


def _available_reference(
    artifact: EvidenceArtifactReference,
    artifact_fingerprint: str,
) -> EvidenceArtifactReference:
    return EvidenceArtifactReference(
        artifact_id=artifact.artifact_id,
        filename=artifact.filename,
        relative_path=artifact.relative_path,
        status=EvidenceArtifactStatus.AVAILABLE,
        fingerprint=artifact_fingerprint,
    )


def _write_json(
    path: Path,
    payload: Any,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=4,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _canonical_mapping(
    value: Any
) -> Any:
    if isinstance(
        value,
        Enum,
    ):
        return value.value
    if is_dataclass(
        value
    ):
        return {
            key: _canonical_mapping(
                item
            )
            for key, item in asdict(
                value
            ).items()
            if key != "local_artifact_path"
        }
    if isinstance(
        value,
        dict,
    ):
        return {
            key: _canonical_mapping(
                item
            )
            for key, item in sorted(
                value.items()
            )
            if key != "local_artifact_path"
        }
    if isinstance(
        value,
        (
            tuple,
            list,
        ),
    ):
        return [
            _canonical_mapping(
                item
            )
            for item in value
        ]
    return value
