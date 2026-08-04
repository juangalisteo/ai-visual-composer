from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain import StoryboardScene


BENCHMARK_ID = "OVB-001"
BENCHMARK_VERSION = "1.0.0"


@dataclass(frozen=True)
class BenchmarkScene:
    identifier: str
    title: str
    purpose: str
    scenario: str
    prompt_source: str
    expected_category: str
    semantic_characteristics: tuple[str, ...]
    visual_truth_categories: tuple[str, ...]
    expected_prompt_challenges: tuple[str, ...]
    expected_visual_challenges: tuple[str, ...]
    regression_risks: tuple[str, ...]
    reason_for_inclusion: str
    scene: StoryboardScene
    version: str = BENCHMARK_VERSION


@dataclass(frozen=True)
class BenchmarkExecutionConfig:
    benchmark_id: str = BENCHMARK_ID
    benchmark_version: str = BENCHMARK_VERSION
    workflow_id: str = "certified-image-workflow"
    backend_id: str = "comfyui-compatible"
    model_id: str = "certified-image-model"
    scheduler: str = "fixed"
    seed: int = 1001
    width: int = 640
    height: int = 360
    sampler: str = "certified-sampler"
    cfg: float = 1.0
    steps: int = 20
    negative_prompt: str = ""
    generator_id: str = "deterministic-placeholder-image-generator"


@dataclass(frozen=True)
class GeneratedBenchmarkImage:
    path: str
    fingerprint: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class BenchmarkSceneRun:
    scene: BenchmarkScene
    variant: str
    artifacts: dict[str, str]
    fingerprints: dict[str, str]
    compiled_prompt: str
    generation_metadata: dict[str, str]
    generated_image: GeneratedBenchmarkImage
    visual_quality_result: dict[str, Any]


@dataclass(frozen=True)
class BenchmarkDifference:
    artifact: str
    status: str
    baseline_fingerprint: str = ""
    candidate_fingerprint: str = ""
    detail: str = ""


@dataclass(frozen=True)
class BenchmarkSceneComparison:
    scene_id: str
    differences: tuple[BenchmarkDifference, ...]
    semantic_preservation: str
    continuity_preservation: str
    object_consistency: str
    spatial_consistency: str
    prompt_richness: str
    visual_richness: str
    composition: str
    lighting: str
    atmosphere: str
    cinematic_quality: str
    prompt_density: str
    redundancy: str
    detected_improvements: tuple[str, ...] = field(default_factory=tuple)
    detected_regressions: tuple[str, ...] = field(default_factory=tuple)
    acceptance_decision: str = "accepted"


@dataclass(frozen=True)
class BenchmarkReport:
    benchmark_id: str
    benchmark_version: str
    scene_count: int
    scenes_improved: int
    scenes_unchanged: int
    scenes_regressed: int
    overall_semantic_survival: str
    overall_continuity_survival: str
    overall_visual_improvement: str
    prompt_density_variation: str
    regression_summary: tuple[str, ...]
    acceptance_decision: str
    scene_reports: tuple[BenchmarkSceneComparison, ...]
    artifacts_root: str
