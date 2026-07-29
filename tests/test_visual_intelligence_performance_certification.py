import gc
import statistics
import sys
import time
import tracemalloc
import unittest
from dataclasses import fields, is_dataclass

from app.backend_adapters import ComfyUIAdapter
from app.cinematic_direction import CinematicDirectionOrchestrator
from app.domain import StoryboardScene
from app.domain.adapters import RuntimeCognitiveAdapter
from app.modules.images.image_builder import ImageBuilder
from app.prompt_translation import PromptTranslator
from app.visual_intelligence import (
    VisualAnalysisOrchestrator,
    VisualReasoningOrchestrator,
    VisualSynthesisOrchestrator,
)
from app.visual_intelligence.synthesis.brief import EffectiveVisualBriefSynthesizer
from app.visual_intelligence.synthesis.conflicts import VisualConflictResolver
from app.visual_intelligence.synthesis.trace import VisualIntelligenceTraceBuilder


def small_scene() -> StoryboardScene:
    return StoryboardScene(
        scene_number=1,
        text="Un objeto antiguo aparece sobre una mesa.",
        visible_subject="llave antigua sobre mesa de madera",
        visible_action="permanece inmovil esperando ser tomada",
        visible_environment="habitacion silenciosa",
        filmable_interpretation="una llave antigua espera sobre la mesa",
        visual_truth_status="structured",
    )


def medium_scene() -> StoryboardScene:
    return StoryboardScene(
        scene_number=7,
        text="Una investigadora recibe una llave antigua en un archivo.",
        visible_subject="investigadora con abrigo gris",
        visible_action="recibe una llave antigua",
        visible_environment="archivo subterraneo silencioso",
        time_context="noche lluviosa",
        key_objects=(
            "llave antigua",
            "sobre lacrado",
        ),
        spatial_relationships=(
            "la llave queda suspendida entre ambas manos",
        ),
        continuity_links=(
            "misma investigadora",
            "misma llave antigua",
        ),
        abstract_source="confianza entregada",
        filmable_interpretation="una llave antigua cambia de manos en silencio",
        visual_constraints=(
            "sin texto legible",
            "sin logos",
        ),
        visual_truth_status="structured",
    )


def complex_scene() -> StoryboardScene:
    return StoryboardScene(
        scene_number=18,
        text="La investigadora cruza un laboratorio abandonado con la llave.",
        visible_subject="investigadora con abrigo gris y expresion contenida",
        visible_action="avanza lentamente sosteniendo la llave antigua",
        visible_environment=(
            "laboratorio subterraneo abandonado con vitrinas rotas"
        ),
        time_context="madrugada fria despues de la lluvia",
        key_objects=(
            "llave antigua",
            "sobre lacrado",
            "vitrina rota",
            "lampara parpadeante",
            "cuaderno cerrado",
        ),
        spatial_relationships=(
            "la investigadora queda al fondo del pasillo",
            "la llave permanece visible en primer termino",
            "las vitrinas crean lineas profundas hacia la puerta",
        ),
        continuity_links=(
            "misma investigadora",
            "misma llave antigua",
            "mismo archivo subterraneo",
            "continuidad nocturna",
        ),
        abstract_source="responsabilidad que se vuelve irreversible",
        filmable_interpretation=(
            "la investigadora cruza el laboratorio con la llave como unica guia"
        ),
        visual_constraints=(
            "sin texto legible",
            "sin logos",
            "sin cambio de vestuario",
            "mantener la misma llave",
        ),
        visual_truth_status="structured",
    )


def collect_performance_baseline(
    iterations: int = 12
) -> dict:
    scenes = {
        "small": small_scene(),
        "medium": medium_scene(),
        "complex": complex_scene(),
    }
    pipeline_samples = [
        _measure_complete_pipeline(
            scenes["medium"]
        )
        for _ in range(
            iterations
        )
    ]
    stage_samples = _measure_stage_breakdown(
        scenes["medium"]
    )
    scalability = {
        name: _measure_complete_pipeline(
            scene
        )
        for name, scene in scenes.items()
    }
    fingerprints = {
        sample["fingerprints"]["payload"]
        for sample in pipeline_samples
    }

    return {
        "iterations": iterations,
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "pipeline": _summarize_samples(
            pipeline_samples
        ),
        "stages": stage_samples,
        "scalability": scalability,
        "deterministic_payload_fingerprints": len(
            fingerprints
        ),
        "fingerprints_per_pipeline": pipeline_samples[0][
            "fingerprint_count"
        ],
        "contracts_per_pipeline": pipeline_samples[0][
            "contract_count"
        ],
    }


def _measure_complete_pipeline(
    scene: StoryboardScene
) -> dict:
    def run_pipeline():
        builder = ImageBuilder()
        synthesis_result = builder._build_runtime_visual_synthesis_result(
            storyboard_scene=scene,
            profile={
                "format": "horizontal",
            },
        )
        direction_set = CinematicDirectionOrchestrator().resolve(
            synthesis_result.brief
        )
        backend_prompt = PromptTranslator().translate_visual_synthesis_result(
            synthesis_result,
            cinematic_direction_set=direction_set,
        )
        payload = ComfyUIAdapter().adapt(
            backend_prompt
        )
        return synthesis_result, direction_set, backend_prompt, payload

    measurement = _measure(
        run_pipeline
    )
    synthesis_result, direction_set, backend_prompt, payload = (
        measurement["result"]
    )
    return {
        "seconds": measurement["seconds"],
        "memory_peak_bytes": measurement["memory_peak_bytes"],
        "memory_current_bytes": measurement["memory_current_bytes"],
        "objects_created": measurement["objects_created"],
        "fingerprints": {
            "synthesis": synthesis_result.fingerprint,
            "trace": synthesis_result.trace.fingerprint,
            "conflicts": synthesis_result.conflicts.fingerprint,
            "brief": synthesis_result.brief.fingerprint,
            "direction_set": direction_set.fingerprint,
            "backend_prompt": backend_prompt.fingerprint,
            "payload": payload.fingerprint,
        },
        "fingerprint_count": _fingerprint_count(
            measurement["result"]
        ),
        "contract_count": _contract_count(
            measurement["result"]
        ),
    }


def _measure_stage_breakdown(
    scene: StoryboardScene
) -> dict:
    transitional_visual_brief = (
        RuntimeCognitiveAdapter.from_storyboard_scene(
            scene,
            orientation="horizontal"
        ).visual_brief
    )
    analysis = _measure(
        lambda: VisualAnalysisOrchestrator().analyze(
            scene
        )
    )
    reasoning = _measure(
        lambda: VisualReasoningOrchestrator().reason(
            analysis["result"]
        )
    )
    conflict = _measure(
        lambda: VisualConflictResolver().resolve(
            analysis["result"],
            reasoning["result"],
        )
    )
    brief = _measure(
        lambda: EffectiveVisualBriefSynthesizer().synthesize(
            analysis["result"],
            reasoning["result"],
            conflict["result"],
            visual_brief=transitional_visual_brief,
            source_id=f"scene_{scene.scene_number:03d}",
            source_version="image-component-runtime-v1",
        )
    )
    trace = _measure(
        lambda: VisualIntelligenceTraceBuilder().build(
            analysis["result"],
            reasoning["result"],
            conflict["result"],
            brief["result"],
        )
    )
    synthesis = _measure(
        lambda: VisualSynthesisOrchestrator().synthesize(
            analysis["result"],
            reasoning["result"],
            visual_brief=transitional_visual_brief,
            source_id=f"scene_{scene.scene_number:03d}",
            source_version="image-component-runtime-v1",
        )
    )
    direction_set = _measure(
        lambda: CinematicDirectionOrchestrator().resolve(
            synthesis["result"].brief
        )
    )
    prompt = _measure(
        lambda: PromptTranslator().translate_visual_synthesis_result(
            synthesis["result"],
            cinematic_direction_set=direction_set["result"],
        )
    )
    payload = _measure(
        lambda: ComfyUIAdapter().adapt(
            prompt["result"]
        )
    )
    runtime = _measure(
        lambda: ImageBuilder()._build_runtime_visual_synthesis_result(
            storyboard_scene=scene,
            profile={
                "format": "horizontal",
            },
        )
    )
    return {
        "visual_analysis": _stage_summary(
            analysis
        ),
        "visual_reasoning": _stage_summary(
            reasoning
        ),
        "conflict_resolution": _stage_summary(
            conflict
        ),
        "effective_visual_brief_synthesis": _stage_summary(
            brief
        ),
        "visual_intelligence_trace": _stage_summary(
            trace
        ),
        "visual_synthesis_orchestrator": _stage_summary(
            synthesis
        ),
        "cinematic_direction": _stage_summary(
            direction_set
        ),
        "prompt_translation": _stage_summary(
            prompt
        ),
        "backend_adapter_payload": _stage_summary(
            payload
        ),
        "runtime_visual_synthesis_entry": _stage_summary(
            runtime
        ),
    }


def _measure(
    function
) -> dict:
    gc.collect()
    objects_before = len(
        gc.get_objects()
    )
    tracemalloc.start()
    start = time.perf_counter()
    result = function()
    seconds = time.perf_counter() - start
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    objects_after = len(
        gc.get_objects()
    )
    return {
        "result": result,
        "seconds": seconds,
        "memory_current_bytes": current,
        "memory_peak_bytes": peak,
        "objects_created": max(
            0,
            objects_after - objects_before
        ),
    }


def _stage_summary(
    measurement: dict
) -> dict:
    return {
        "seconds": measurement["seconds"],
        "memory_peak_bytes": measurement["memory_peak_bytes"],
        "memory_current_bytes": measurement["memory_current_bytes"],
        "objects_created": measurement["objects_created"],
        "fingerprint_count": _fingerprint_count(
            measurement["result"]
        ),
        "contract_count": _contract_count(
            measurement["result"]
        ),
    }


def _summarize_samples(
    samples: list[dict]
) -> dict:
    seconds = [
        sample["seconds"]
        for sample in samples
    ]
    peaks = [
        sample["memory_peak_bytes"]
        for sample in samples
    ]
    objects = [
        sample["objects_created"]
        for sample in samples
    ]
    return {
        "seconds_min": min(
            seconds
        ),
        "seconds_max": max(
            seconds
        ),
        "seconds_mean": statistics.fmean(
            seconds
        ),
        "seconds_stdev": statistics.pstdev(
            seconds
        ),
        "seconds_p95": _percentile(
            seconds,
            95
        ),
        "seconds_p99": _percentile(
            seconds,
            99
        ),
        "memory_peak_max_bytes": max(
            peaks
        ),
        "memory_peak_mean_bytes": statistics.fmean(
            peaks
        ),
        "objects_created_mean": statistics.fmean(
            objects
        ),
    }


def _percentile(
    values: list[float],
    percentile: int
) -> float:
    ordered = sorted(
        values
    )
    index = round(
        (
            len(
                ordered
            )
            - 1
        )
        * percentile
        / 100
    )
    return ordered[
        index
    ]


def _fingerprint_count(
    value
) -> int:
    return len(
        _fingerprints(
            value,
            set()
        )
    )


def _fingerprints(
    value,
    visited: set[int]
) -> set[str]:
    if id(
        value
    ) in visited:
        return set()
    visited.add(
        id(
            value
        )
    )
    found = set()
    fingerprint = getattr(
        value,
        "fingerprint",
        ""
    )
    if fingerprint:
        found.add(
            fingerprint
        )
    if is_dataclass(
        value
    ):
        for field in fields(
            value
        ):
            found.update(
                _fingerprints(
                    getattr(
                        value,
                        field.name
                    ),
                    visited
                )
            )
    elif isinstance(
        value,
        (
            tuple,
            list,
        )
    ):
        for item in value:
            found.update(
                _fingerprints(
                    item,
                    visited
                )
            )
    elif isinstance(
        value,
        dict
    ):
        for item in value.values():
            found.update(
                _fingerprints(
                    item,
                    visited
                )
            )
    return found


def _contract_count(
    value
) -> int:
    return _contracts(
        value,
        set()
    )


def _contracts(
    value,
    visited: set[int]
) -> int:
    if id(
        value
    ) in visited:
        return 0
    visited.add(
        id(
            value
        )
    )
    total = 1 if is_dataclass(
        value
    ) else 0
    if is_dataclass(
        value
    ):
        for field in fields(
            value
        ):
            total += _contracts(
                getattr(
                    value,
                    field.name
                ),
                visited
            )
    elif isinstance(
        value,
        (
            tuple,
            list,
        )
    ):
        for item in value:
            total += _contracts(
                item,
                visited
            )
    elif isinstance(
        value,
        dict
    ):
        for item in value.values():
            total += _contracts(
                item,
                visited
            )
    return total


class VisualIntelligencePerformanceCertificationTest(unittest.TestCase):

    def test_collects_complete_performance_baseline(self):
        baseline = collect_performance_baseline(
            iterations=5
        )

        self.assertEqual(
            5,
            baseline["iterations"],
        )
        for key in (
            "seconds_min",
            "seconds_max",
            "seconds_mean",
            "seconds_stdev",
            "seconds_p95",
            "seconds_p99",
            "memory_peak_max_bytes",
            "memory_peak_mean_bytes",
            "objects_created_mean",
        ):
            with self.subTest(
                key=key
            ):
                self.assertIn(
                    key,
                    baseline["pipeline"],
                )
                self.assertGreaterEqual(
                    baseline["pipeline"][key],
                    0,
                )

    def test_measures_required_orchestrators_and_runtime_stages(self):
        stages = collect_performance_baseline(
            iterations=3
        )["stages"]

        expected = {
            "visual_analysis",
            "visual_reasoning",
            "conflict_resolution",
            "effective_visual_brief_synthesis",
            "visual_intelligence_trace",
            "visual_synthesis_orchestrator",
            "cinematic_direction",
            "prompt_translation",
            "backend_adapter_payload",
            "runtime_visual_synthesis_entry",
        }
        self.assertTrue(
            expected.issubset(
                stages
            )
        )
        for name in expected:
            with self.subTest(
                name=name
            ):
                self.assertGreaterEqual(
                    stages[name]["seconds"],
                    0,
                )
                self.assertGreaterEqual(
                    stages[name]["memory_peak_bytes"],
                    0,
                )

    def test_certifies_temporal_determinism(self):
        baseline = collect_performance_baseline(
            iterations=8
        )

        self.assertEqual(
            1,
            baseline["deterministic_payload_fingerprints"],
        )
        self.assertGreater(
            baseline["fingerprints_per_pipeline"],
            0,
        )
        self.assertGreater(
            baseline["contracts_per_pipeline"],
            0,
        )

    def test_certifies_scalability_load_levels(self):
        baseline = collect_performance_baseline(
            iterations=3
        )

        self.assertEqual(
            {
                "small",
                "medium",
                "complex",
            },
            set(
                baseline["scalability"]
            ),
        )
        for name, sample in baseline["scalability"].items():
            with self.subTest(
                name=name
            ):
                self.assertGreaterEqual(
                    sample["seconds"],
                    0,
                )
                self.assertTrue(
                    sample["fingerprints"]["payload"],
                )


if __name__ == "__main__":
    unittest.main()
