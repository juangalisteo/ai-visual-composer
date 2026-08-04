import tempfile
import unittest
from pathlib import Path

from app.benchmarks.ovb_001 import (
    BENCHMARK_ID,
    BENCHMARK_VERSION,
    BenchmarkExecutionConfig,
    OVB001BenchmarkHarness,
    load_ovb_001_scenes,
)
from app.benchmarks.ovb_001.image import (
    DeterministicBenchmarkImageGenerator,
    RealBackendBenchmarkImageGenerator,
)
from app.benchmarks.ovb_001.pipeline import OVB001ExecutionPipeline
from app.benchmarks.ovb_001.serialization import read_json


class OVB001BenchmarkHarnessTest(unittest.TestCase):

    def harness(self):
        return OVB001BenchmarkHarness(
            baseline_pipeline=OVB001ExecutionPipeline(
                image_generator=DeterministicBenchmarkImageGenerator()
            ),
            candidate_pipeline=OVB001ExecutionPipeline(
                image_generator=DeterministicBenchmarkImageGenerator()
            ),
        )

    def test_loads_all_official_scenes_with_stable_version(self):
        scenes = load_ovb_001_scenes()

        self.assertEqual(
            12,
            len(
                scenes
            ),
        )
        self.assertEqual(
            tuple(
                f"OVB-001-S{index:02d}"
                for index in range(
                    1,
                    13,
                )
            ),
            tuple(
                scene.identifier
                for scene in scenes
            ),
        )
        self.assertEqual(
            {
                BENCHMARK_VERSION
            },
            {
                scene.version
                for scene in scenes
            },
        )
        self.assertTrue(
            all(
                scene.visual_truth_categories
                for scene in scenes
            )
        )

    def test_executes_every_official_scene_and_persists_artifacts(self):
        with tempfile.TemporaryDirectory() as temp:
            report = self.harness().run(
                temp
            )
            root = Path(
                temp
            ) / BENCHMARK_ID

            self.assertEqual(
                12,
                report.scene_count,
            )
            self.assertEqual(
                "accepted",
                report.acceptance_decision,
            )
            for scene in load_ovb_001_scenes():
                scene_root = root / scene.identifier
                for variant in (
                    "baseline",
                    "candidate",
                ):
                    variant_root = scene_root / variant
                    self.assertTrue(
                        (
                            variant_root / "scene.json"
                        ).exists()
                    )
                    self.assertTrue(
                        (
                            variant_root / "visual_analysis_result.json"
                        ).exists()
                    )
                    self.assertTrue(
                        (
                            variant_root / "visual_reasoning_result.json"
                        ).exists()
                    )
                    self.assertTrue(
                        (
                            variant_root / "visual_conflict_report.json"
                        ).exists()
                    )
                    self.assertTrue(
                        (
                            variant_root / "effective_visual_brief.json"
                        ).exists()
                    )
                    self.assertTrue(
                        (
                            variant_root / "visual_synthesis_result.json"
                        ).exists()
                    )
                    self.assertTrue(
                        (
                            variant_root / "prompt_translation_observation.json"
                        ).exists()
                    )
                    self.assertTrue(
                        (
                            variant_root / "backend_prompt.json"
                        ).exists()
                    )
                    self.assertTrue(
                        (
                            variant_root / "compiled_prompt.txt"
                        ).exists()
                    )
                    self.assertTrue(
                        (
                            variant_root / "comfyui_payload.json"
                        ).exists()
                    )
                    self.assertTrue(
                        (
                            variant_root / "generation_metadata.json"
                        ).exists()
                    )
                    self.assertTrue(
                        (
                            variant_root / "generated_image.png"
                        ).exists()
                    )
                    self.assertTrue(
                        (
                            variant_root / "visual_quality_result.json"
                        ).exists()
                    )
                self.assertTrue(
                    (
                        scene_root / "comparison" / "comparison.json"
                    ).exists()
                )
                self.assertTrue(
                    (
                        scene_root / "scene-report" / "scene-report.json"
                    ).exists()
                )
            self.assertTrue(
                (
                    root / "summary" / "benchmark-report.json"
                ).exists()
            )

    def test_comparison_report_detects_identical_baseline_and_candidate(self):
        with tempfile.TemporaryDirectory() as temp:
            report = self.harness().run(
                temp
            )

            self.assertEqual(
                12,
                report.scenes_unchanged,
            )
            self.assertEqual(
                0,
                report.scenes_regressed,
            )
            self.assertTrue(
                all(
                    difference.status == "identical"
                    for scene in report.scene_reports
                    for difference in scene.differences
                )
            )

    def test_generation_metadata_persists_reproducibility_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            config = BenchmarkExecutionConfig(
                workflow_id="workflow-a",
                backend_id="backend-a",
                model_id="model-a",
                scheduler="scheduler-a",
                seed=42,
                width=128,
                height=72,
                sampler="sampler-a",
                cfg=2.5,
                steps=9,
                negative_prompt="negative-a",
            )
            self.harness().run(
                temp,
                config=config,
                scenes=load_ovb_001_scenes()[
                    :1
                ],
            )
            metadata = read_json(
                Path(
                    temp
                )
                / BENCHMARK_ID
                / "OVB-001-S01"
                / "baseline"
                / "generation_metadata.json"
            )

            self.assertEqual(
                "workflow-a",
                metadata[
                    "workflow"
                ],
            )
            self.assertEqual(
                "backend-a",
                metadata[
                    "backend"
                ],
            )
            self.assertEqual(
                "model-a",
                metadata[
                    "model"
                ],
            )
            self.assertEqual(
                "42",
                metadata[
                    "seed"
                ],
            )
            self.assertEqual(
                "128x72",
                metadata[
                    "resolution"
                ],
            )
            self.assertEqual(
                "negative-a",
                metadata[
                    "negative_prompt"
                ],
            )

    def test_visual_quality_result_is_evaluated_by_pipeline(self):
        with tempfile.TemporaryDirectory() as temp:
            self.harness().run(
                temp,
                scenes=load_ovb_001_scenes()[
                    :1
                ],
            )
            quality_result = read_json(
                Path(
                    temp
                )
                / BENCHMARK_ID
                / "OVB-001-S01"
                / "baseline"
                / "visual_quality_result.json"
            )

        self.assertEqual(
            "approved",
            quality_result["status"],
        )
        self.assertEqual(
            "accepted",
            quality_result["validation_report"]["status"],
        )
        self.assertTrue(
            quality_result["validation_report"]["checks"],
        )

    def test_repeated_execution_with_identical_settings_is_reproducible(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_report = self.harness().run(
                first,
                scenes=load_ovb_001_scenes()[
                    :2
                ],
            )
            second_report = self.harness().run(
                second,
                scenes=load_ovb_001_scenes()[
                    :2
                ],
            )

            self.assertEqual(
                tuple(
                    scene.differences
                    for scene in first_report.scene_reports
                ),
                tuple(
                    scene.differences
                    for scene in second_report.scene_reports
                ),
            )
            self.assertEqual(
                first_report.acceptance_decision,
                second_report.acceptance_decision,
            )

    def test_summary_report_files_are_generated(self):
        with tempfile.TemporaryDirectory() as temp:
            self.harness().run(
                temp,
                scenes=load_ovb_001_scenes()[
                    :1
                ],
            )
            summary_root = Path(
                temp
            ) / BENCHMARK_ID / "summary"

            self.assertTrue(
                (
                    summary_root / "benchmark-report.json"
                ).exists()
            )
            self.assertTrue(
                (
                    summary_root / "engineering-summary.json"
                ).exists()
            )
            self.assertTrue(
                (
                    summary_root / "acceptance-summary.json"
                ).exists()
            )
            self.assertTrue(
                (
                    summary_root / "regression-summary.json"
                ).exists()
            )

    def test_runner_rejects_empty_scene_collection(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(
                ValueError
            ):
                self.harness().run(
                    temp,
                    scenes=(),
                )

    def test_real_backend_generator_reuses_image_builder_generation(self):
        with tempfile.TemporaryDirectory() as temp:
            builder = RecordingImageBuilder()
            scene = load_ovb_001_scenes()[0]
            payload = FakePayload(
                prompt="real backend prompt",
                fingerprint="payload-fingerprint",
            )

            result = RealBackendBenchmarkImageGenerator(
                image_builder=builder
            ).generate(
                scene,
                payload,
                BenchmarkExecutionConfig(
                    width=320,
                    height=180,
                ),
                Path(
                    temp
                ),
            )

            self.assertTrue(
                Path(
                    result.path
                ).exists()
            )
            self.assertEqual(
                {
                    "prompt": "real backend prompt",
                    "scene_number": 1,
                    "width": 320,
                    "height": 180,
                },
                builder.calls[0],
            )
            metadata = read_json(
                Path(
                    temp
                ) / "generation_metadata.json"
            )
            self.assertEqual(
                "real-backend-image-generator",
                metadata[
                    "generator_id"
                ],
            )


class RecordingImageBuilder:

    def __init__(
        self
    ):
        self.calls = []

    def _generate_image(
        self,
        prompt,
        scene_number,
        output_dir,
        width,
        height,
    ):
        self.calls.append(
            {
                "prompt": prompt,
                "scene_number": scene_number,
                "width": width,
                "height": height,
            }
        )
        path = Path(
            output_dir
        ) / f"scene_{scene_number:03d}.png"
        path.write_bytes(
            b"real-backend-image"
        )
        return path


class FakePayload:

    def __init__(
        self,
        prompt,
        fingerprint,
    ):
        self.prompt = prompt
        self.fingerprint = fingerprint


if __name__ == "__main__":
    unittest.main()
