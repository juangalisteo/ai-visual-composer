from pathlib import Path

from app.benchmarks.ovb_001.comparison import OVB001ComparisonEngine
from app.benchmarks.ovb_001.dataset import load_ovb_001_scenes
from app.benchmarks.ovb_001.models import (
    BENCHMARK_ID,
    BENCHMARK_VERSION,
    BenchmarkExecutionConfig,
    BenchmarkReport,
    BenchmarkScene,
    BenchmarkSceneRun,
)
from app.benchmarks.ovb_001.pipeline import OVB001ExecutionPipeline
from app.benchmarks.ovb_001.serialization import write_json


class OVB001BenchmarkHarness:
    def __init__(
        self,
        baseline_pipeline: OVB001ExecutionPipeline | None = None,
        candidate_pipeline: OVB001ExecutionPipeline | None = None,
        comparison_engine: OVB001ComparisonEngine | None = None,
    ) -> None:
        self.baseline_pipeline = (
            baseline_pipeline
            or OVB001ExecutionPipeline()
        )
        self.candidate_pipeline = (
            candidate_pipeline
            or OVB001ExecutionPipeline()
        )
        self.comparison_engine = (
            comparison_engine
            or OVB001ComparisonEngine()
        )

    def run(
        self,
        output_root: str | Path,
        config: BenchmarkExecutionConfig | None = None,
        scenes: tuple[BenchmarkScene, ...] | None = None,
    ) -> BenchmarkReport:
        benchmark_config = config or BenchmarkExecutionConfig()
        benchmark_scenes = (
            load_ovb_001_scenes()
            if scenes is None
            else scenes
        )
        if not benchmark_scenes:
            raise ValueError(
                "OVB-001 runner requires at least one benchmark scene."
            )
        root = Path(
            output_root
        ) / BENCHMARK_ID
        root.mkdir(
            parents=True,
            exist_ok=True,
        )
        write_json(
            root / "benchmark_config.json",
            benchmark_config,
        )
        scene_reports = []
        for scene in benchmark_scenes:
            scene_dir = root / scene.identifier
            baseline = self.baseline_pipeline.execute(
                scene,
                "baseline",
                benchmark_config,
                scene_dir,
            )
            candidate = self.candidate_pipeline.execute(
                scene,
                "candidate",
                benchmark_config,
                scene_dir,
            )
            comparison = self.comparison_engine.compare_scene(
                baseline,
                candidate,
            )
            self._persist_scene_reports(
                scene_dir,
                baseline,
                candidate,
                comparison,
            )
            scene_reports.append(
                comparison
            )
        report = self.comparison_engine.global_report(
            tuple(
                scene_reports
            ),
            artifacts_root=root.as_posix(),
            benchmark_id=BENCHMARK_ID,
            benchmark_version=BENCHMARK_VERSION,
        )
        summary_dir = root / "summary"
        summary_dir.mkdir(
            parents=True,
            exist_ok=True,
        )
        write_json(
            summary_dir / "benchmark-report.json",
            report,
        )
        write_json(
            summary_dir / "engineering-summary.json",
            {
                "benchmark_id": report.benchmark_id,
                "benchmark_version": report.benchmark_version,
                "scene_count": report.scene_count,
                "acceptance_decision": report.acceptance_decision,
                "scenes_unchanged": report.scenes_unchanged,
                "scenes_regressed": report.scenes_regressed,
            },
        )
        write_json(
            summary_dir / "acceptance-summary.json",
            {
                "accepted": report.acceptance_decision == "accepted",
                "regression_summary": report.regression_summary,
            },
        )
        write_json(
            summary_dir / "regression-summary.json",
            {
                "regressions": report.regression_summary,
            },
        )
        return report

    def _persist_scene_reports(
        self,
        scene_dir: Path,
        baseline: BenchmarkSceneRun,
        candidate: BenchmarkSceneRun,
        comparison,
    ) -> None:
        comparison_dir = scene_dir / "comparison"
        scene_report_dir = scene_dir / "scene-report"
        comparison_dir.mkdir(
            parents=True,
            exist_ok=True,
        )
        scene_report_dir.mkdir(
            parents=True,
            exist_ok=True,
        )
        write_json(
            comparison_dir / "comparison.json",
            comparison,
        )
        write_json(
            scene_report_dir / "scene-report.json",
            {
                "scene_id": comparison.scene_id,
                "baseline_artifacts": baseline.artifacts,
                "candidate_artifacts": candidate.artifacts,
                "comparison": comparison,
            },
        )
