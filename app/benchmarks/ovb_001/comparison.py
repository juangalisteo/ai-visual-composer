from app.benchmarks.ovb_001.models import (
    BenchmarkDifference,
    BenchmarkReport,
    BenchmarkSceneComparison,
    BenchmarkSceneRun,
)


COMPARABLE_ARTIFACTS = (
    "visual_analysis_result",
    "visual_reasoning_result",
    "visual_conflict_report",
    "effective_visual_brief",
    "visual_synthesis_result",
    "prompt_translation_observation",
    "backend_prompt",
    "compiled_prompt",
    "generation_metadata",
    "generated_image",
    "visual_quality_result",
)


class OVB001ComparisonEngine:
    def compare_scene(
        self,
        baseline: BenchmarkSceneRun,
        candidate: BenchmarkSceneRun,
    ) -> BenchmarkSceneComparison:
        differences = tuple(
            self._difference(
                artifact,
                baseline,
                candidate,
            )
            for artifact in COMPARABLE_ARTIFACTS
        )
        regressions = tuple(
            difference.artifact
            for difference in differences
            if difference.status == "different"
            and difference.artifact in MANDATORY_STABLE_ARTIFACTS
        )
        prompt_density = _prompt_density_status(
            baseline.compiled_prompt,
            candidate.compiled_prompt,
        )
        acceptance = (
            "rejected"
            if regressions
            else "accepted"
        )
        return BenchmarkSceneComparison(
            scene_id=baseline.scene.identifier,
            differences=differences,
            semantic_preservation=_status_for(
                differences,
                "backend_prompt",
            ),
            continuity_preservation=_status_for(
                differences,
                "prompt_translation_observation",
            ),
            object_consistency=_status_for(
                differences,
                "compiled_prompt",
            ),
            spatial_consistency=_status_for(
                differences,
                "compiled_prompt",
            ),
            prompt_richness=_status_for(
                differences,
                "backend_prompt",
            ),
            visual_richness=_status_for(
                differences,
                "generated_image",
            ),
            composition=_status_for(
                differences,
                "effective_visual_brief",
            ),
            lighting=_status_for(
                differences,
                "effective_visual_brief",
            ),
            atmosphere=_status_for(
                differences,
                "effective_visual_brief",
            ),
            cinematic_quality=_status_for(
                differences,
                "generated_image",
            ),
            prompt_density=prompt_density,
            redundancy=_status_for(
                differences,
                "prompt_translation_observation",
            ),
            detected_regressions=regressions,
            acceptance_decision=acceptance,
        )

    def global_report(
        self,
        scene_reports: tuple[BenchmarkSceneComparison, ...],
        artifacts_root: str,
        benchmark_id: str,
        benchmark_version: str,
    ) -> BenchmarkReport:
        scenes_regressed = sum(
            1
            for scene in scene_reports
            if scene.acceptance_decision == "rejected"
        )
        scenes_changed = sum(
            1
            for scene in scene_reports
            if any(
                difference.status == "different"
                for difference in scene.differences
            )
        )
        scenes_unchanged = len(
            scene_reports
        ) - scenes_changed
        acceptance = (
            "rejected"
            if scenes_regressed
            else "accepted"
        )
        regression_summary = tuple(
            f"{scene.scene_id}:{regression}"
            for scene in scene_reports
            for regression in scene.detected_regressions
        )
        return BenchmarkReport(
            benchmark_id=benchmark_id,
            benchmark_version=benchmark_version,
            scene_count=len(
                scene_reports
            ),
            scenes_improved=0,
            scenes_unchanged=scenes_unchanged,
            scenes_regressed=scenes_regressed,
            overall_semantic_survival=(
                "stable"
                if not regression_summary
                else "regressed"
            ),
            overall_continuity_survival=(
                "stable"
                if not regression_summary
                else "regressed"
            ),
            overall_visual_improvement="not_measured_by_deterministic_harness",
            prompt_density_variation=(
                "stable"
                if scenes_changed == 0
                else "changed"
            ),
            regression_summary=regression_summary,
            acceptance_decision=acceptance,
            scene_reports=scene_reports,
            artifacts_root=artifacts_root,
        )

    def _difference(
        self,
        artifact: str,
        baseline: BenchmarkSceneRun,
        candidate: BenchmarkSceneRun,
    ) -> BenchmarkDifference:
        baseline_fingerprint = baseline.fingerprints.get(
            artifact,
            "",
        )
        candidate_fingerprint = candidate.fingerprints.get(
            artifact,
            "",
        )
        status = (
            "identical"
            if baseline_fingerprint == candidate_fingerprint
            else "different"
        )
        return BenchmarkDifference(
            artifact=artifact,
            status=status,
            baseline_fingerprint=baseline_fingerprint,
            candidate_fingerprint=candidate_fingerprint,
            detail=(
                "fingerprints match"
                if status == "identical"
                else "fingerprints differ"
            ),
        )


MANDATORY_STABLE_ARTIFACTS = (
    "visual_analysis_result",
    "visual_reasoning_result",
    "visual_conflict_report",
    "effective_visual_brief",
    "visual_synthesis_result",
    "generation_metadata",
)


def _status_for(
    differences: tuple[BenchmarkDifference, ...],
    artifact: str,
) -> str:
    for difference in differences:
        if difference.artifact == artifact:
            return (
                "stable"
                if difference.status == "identical"
                else "changed"
            )
    return "not_available"


def _prompt_density_status(
    baseline_prompt: str,
    candidate_prompt: str,
) -> str:
    baseline_words = len(
        baseline_prompt.split()
    )
    candidate_words = len(
        candidate_prompt.split()
    )
    if baseline_words == candidate_words:
        return "stable"
    return (
        "increased"
        if candidate_words > baseline_words
        else "decreased"
    )
