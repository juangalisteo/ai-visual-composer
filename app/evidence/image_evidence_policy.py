from dataclasses import dataclass
from pathlib import Path


EVIDENCE_DIRECTORY_NAME = "evidence"
SCENE_DIRECTORY_PREFIX = "scene_"
EVIDENCE_INDEX_FILENAME = "evidence_index.json"

ARTIFACT_FILENAMES = {
    "source_scene": "source_scene.json",
    "visual_truth_scene": "visual_truth_scene.json",
    "visual_analysis_result": "visual_analysis_result.json",
    "visual_reasoning_result": "visual_reasoning_result.json",
    "visual_conflict_report": "visual_conflict_report.json",
    "effective_visual_brief": "effective_visual_brief.json",
    "visual_intelligence_trace": "visual_intelligence_trace.json",
    "visual_synthesis_result": "visual_synthesis_result.json",
    "visual_quality_result": "visual_quality_result.json",
    "cinematic_direction_set": "cinematic_direction_set.json",
    "prompt_translation_observation": "prompt_translation_observation.json",
    "operational_prompt_observation": "operational_prompt_observation.json",
    "backend_prompt": "backend_prompt.json",
    "comfyui_payload": "comfyui_payload.json",
    "final_prompt_segments": "final_prompt_segments.json",
    "effective_workflow": "effective_workflow.json",
}


@dataclass(frozen=True)
class ImageEvidencePathPolicy:
    root_directory_name: str = EVIDENCE_DIRECTORY_NAME
    scene_directory_prefix: str = SCENE_DIRECTORY_PREFIX
    scene_number_width: int = 3

    def scene_directory(
        self,
        output_dir: Path | str,
        scene_number: int,
    ) -> Path:
        return (
            Path(
                output_dir
            )
            / self.root_directory_name
            / self.scene_directory_name(
                scene_number
            )
        )

    def artifact_path(
        self,
        output_dir: Path | str,
        scene_number: int,
        artifact_id: str,
    ) -> Path:
        return (
            self.scene_directory(
                output_dir,
                scene_number,
            )
            / self.artifact_filename(
                artifact_id
            )
        )

    def index_path(
        self,
        output_dir: Path | str,
        scene_number: int,
    ) -> Path:
        return (
            self.scene_directory(
                output_dir,
                scene_number,
            )
            / EVIDENCE_INDEX_FILENAME
        )

    def scene_directory_relative(
        self,
        scene_number: int,
    ) -> Path:
        return (
            Path(
                self.root_directory_name
            )
            / self.scene_directory_name(
                scene_number
            )
        )

    def artifact_relative_path(
        self,
        scene_number: int,
        artifact_id: str,
    ) -> Path:
        return (
            self.scene_directory_relative(
                scene_number
            )
            / self.artifact_filename(
                artifact_id
            )
        )

    def index_relative_path(
        self,
        scene_number: int,
    ) -> Path:
        return (
            self.scene_directory_relative(
                scene_number
            )
            / EVIDENCE_INDEX_FILENAME
        )

    def scene_directory_name(
        self,
        scene_number: int,
    ) -> str:
        _validate_scene_number(
            scene_number
        )
        return (
            f"{self.scene_directory_prefix}"
            f"{scene_number:0{self.scene_number_width}d}"
        )

    def artifact_filename(
        self,
        artifact_id: str,
    ) -> str:
        try:
            return ARTIFACT_FILENAMES[
                artifact_id
            ]
        except KeyError as exc:
            raise ValueError(
                f"Unknown image evidence artifact: {artifact_id}"
            ) from exc


def _validate_scene_number(
    scene_number: int
) -> None:
    if not isinstance(
        scene_number,
        int
    ) or scene_number <= 0:
        raise ValueError(
            "scene_number must be a positive integer."
        )
