import json
import tempfile
import unittest
from dataclasses import asdict, fields
from enum import Enum
from pathlib import Path

from app.domain import EffectiveVisualBrief, StoryboardScene
from app.domain import VisualSynthesisResult
from app.evidence import EvidenceArtifactStatus, ImageEvidenceWriter
from app.prompt_translation import PromptTranslationObservation, PromptTranslator
from app.visual_intelligence import (
    VisualAnalysisOrchestrator,
    VisualSynthesisOrchestrator,
    VisualReasoningOrchestrator,
)


class ImageEvidenceWriterTest(unittest.TestCase):

    def test_writes_visual_analysis_result_and_index(self):
        analysis = _analysis_result()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            result = ImageEvidenceWriter().write_visual_analysis_result(
                output_dir=root,
                scene_number=1,
                visual_analysis_result=analysis,
            )

            artifact = json.loads(
                result.artifact_path.read_text(
                    encoding="utf-8"
                )
            )
            index = json.loads(
                result.index_path.read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(
            "evidence/scene_001",
            index["scene_directory"],
        )
        self.assertEqual(
            analysis.fingerprint,
            artifact["fingerprint"],
        )
        visual_analysis_entry = [
            artifact
            for artifact in index["artifacts"]
            if artifact["artifact_id"] == "visual_analysis_result"
        ][0]
        self.assertEqual(
            EvidenceArtifactStatus.AVAILABLE.value,
            visual_analysis_entry["status"],
        )
        self.assertEqual(
            result.artifact_fingerprint,
            visual_analysis_entry["fingerprint"],
        )

    def test_repeated_serialization_produces_identical_output(self):
        analysis = _analysis_result()

        with tempfile.TemporaryDirectory() as first_dir:
            with tempfile.TemporaryDirectory() as second_dir:
                first = ImageEvidenceWriter().write_visual_analysis_result(
                    output_dir=Path(
                        first_dir
                    ),
                    scene_number=2,
                    visual_analysis_result=analysis,
                )
                second = ImageEvidenceWriter().write_visual_analysis_result(
                    output_dir=Path(
                        second_dir
                    ),
                    scene_number=2,
                    visual_analysis_result=analysis,
                )

                self.assertEqual(
                    first.artifact_path.read_text(
                        encoding="utf-8"
                    ),
                    second.artifact_path.read_text(
                        encoding="utf-8"
                    ),
                )
                self.assertEqual(
                    first.index_path.read_text(
                        encoding="utf-8"
                    ),
                    second.index_path.read_text(
                        encoding="utf-8"
                    ),
                )
                self.assertEqual(
                    first.artifact_fingerprint,
                    second.artifact_fingerprint,
                )
                self.assertEqual(
                    first.index_fingerprint,
                    second.index_fingerprint,
                )

    def test_rejects_non_visual_analysis_result(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(
                TypeError
            ):
                ImageEvidenceWriter().write_visual_analysis_result(
                    output_dir=Path(
                        temp_dir
                    ),
                    scene_number=1,
                    visual_analysis_result=object(),
                )

    def test_writes_visual_reasoning_result_and_preserves_existing_index(self):
        analysis = _analysis_result()
        reasoning = _reasoning_result(
            analysis
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            writer = ImageEvidenceWriter()
            analysis_write = writer.write_visual_analysis_result(
                output_dir=root,
                scene_number=1,
                visual_analysis_result=analysis,
            )
            reasoning_write = writer.write_visual_reasoning_result(
                output_dir=root,
                scene_number=1,
                visual_reasoning_result=reasoning,
            )

            artifact = json.loads(
                reasoning_write.artifact_path.read_text(
                    encoding="utf-8"
                )
            )
            index = json.loads(
                reasoning_write.index_path.read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(
            reasoning.fingerprint,
            artifact["fingerprint"],
        )
        entries = {
            artifact["artifact_id"]: artifact
            for artifact in index["artifacts"]
        }
        self.assertEqual(
            EvidenceArtifactStatus.AVAILABLE.value,
            entries["visual_analysis_result"]["status"],
        )
        self.assertEqual(
            analysis_write.artifact_fingerprint,
            entries["visual_analysis_result"]["fingerprint"],
        )
        self.assertEqual(
            EvidenceArtifactStatus.AVAILABLE.value,
            entries["visual_reasoning_result"]["status"],
        )
        self.assertEqual(
            reasoning_write.artifact_fingerprint,
            entries["visual_reasoning_result"]["fingerprint"],
        )

    def test_repeated_visual_reasoning_serialization_is_deterministic(self):
        reasoning = _reasoning_result(
            _analysis_result()
        )

        with tempfile.TemporaryDirectory() as first_dir:
            with tempfile.TemporaryDirectory() as second_dir:
                first = ImageEvidenceWriter().write_visual_reasoning_result(
                    output_dir=Path(
                        first_dir
                    ),
                    scene_number=3,
                    visual_reasoning_result=reasoning,
                )
                second = ImageEvidenceWriter().write_visual_reasoning_result(
                    output_dir=Path(
                        second_dir
                    ),
                    scene_number=3,
                    visual_reasoning_result=reasoning,
                )

                self.assertEqual(
                    first.artifact_path.read_text(
                        encoding="utf-8"
                    ),
                    second.artifact_path.read_text(
                        encoding="utf-8"
                    ),
                )
                self.assertEqual(
                    first.index_path.read_text(
                        encoding="utf-8"
                    ),
                    second.index_path.read_text(
                        encoding="utf-8"
                    ),
                )
                self.assertEqual(
                    first.artifact_fingerprint,
                    second.artifact_fingerprint,
                )
                self.assertEqual(
                    first.index_fingerprint,
                    second.index_fingerprint,
                )

    def test_rejects_non_visual_reasoning_result(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(
                TypeError
            ):
                ImageEvidenceWriter().write_visual_reasoning_result(
                    output_dir=Path(
                        temp_dir
                    ),
                    scene_number=1,
                    visual_reasoning_result=object(),
                )

    def test_writes_visual_conflict_report_and_preserves_existing_index(self):
        analysis = _analysis_result()
        reasoning = _reasoning_result(
            analysis
        )
        conflicts = _conflict_report(
            analysis,
            reasoning,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            writer = ImageEvidenceWriter()
            analysis_write = writer.write_visual_analysis_result(
                output_dir=root,
                scene_number=1,
                visual_analysis_result=analysis,
            )
            reasoning_write = writer.write_visual_reasoning_result(
                output_dir=root,
                scene_number=1,
                visual_reasoning_result=reasoning,
            )
            conflict_write = writer.write_visual_conflict_report(
                output_dir=root,
                scene_number=1,
                visual_conflict_report=conflicts,
            )

            artifact = json.loads(
                conflict_write.artifact_path.read_text(
                    encoding="utf-8"
                )
            )
            index = json.loads(
                conflict_write.index_path.read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(
            conflicts.fingerprint,
            artifact["fingerprint"],
        )
        entries = {
            artifact["artifact_id"]: artifact
            for artifact in index["artifacts"]
        }
        self.assertEqual(
            analysis_write.artifact_fingerprint,
            entries["visual_analysis_result"]["fingerprint"],
        )
        self.assertEqual(
            reasoning_write.artifact_fingerprint,
            entries["visual_reasoning_result"]["fingerprint"],
        )
        self.assertEqual(
            EvidenceArtifactStatus.AVAILABLE.value,
            entries["visual_conflict_report"]["status"],
        )
        self.assertEqual(
            conflict_write.artifact_fingerprint,
            entries["visual_conflict_report"]["fingerprint"],
        )

    def test_repeated_visual_conflict_report_serialization_is_deterministic(self):
        analysis = _analysis_result()
        reasoning = _reasoning_result(
            analysis
        )
        conflicts = _conflict_report(
            analysis,
            reasoning,
        )

        with tempfile.TemporaryDirectory() as first_dir:
            with tempfile.TemporaryDirectory() as second_dir:
                first = ImageEvidenceWriter().write_visual_conflict_report(
                    output_dir=Path(
                        first_dir
                    ),
                    scene_number=4,
                    visual_conflict_report=conflicts,
                )
                second = ImageEvidenceWriter().write_visual_conflict_report(
                    output_dir=Path(
                        second_dir
                    ),
                    scene_number=4,
                    visual_conflict_report=conflicts,
                )

                self.assertEqual(
                    first.artifact_path.read_text(
                        encoding="utf-8"
                    ),
                    second.artifact_path.read_text(
                        encoding="utf-8"
                    ),
                )
                self.assertEqual(
                    first.index_path.read_text(
                        encoding="utf-8"
                    ),
                    second.index_path.read_text(
                        encoding="utf-8"
                    ),
                )
                self.assertEqual(
                    first.artifact_fingerprint,
                    second.artifact_fingerprint,
                )
                self.assertEqual(
                    first.index_fingerprint,
                    second.index_fingerprint,
                )

    def test_rejects_non_visual_conflict_report(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(
                TypeError
            ):
                ImageEvidenceWriter().write_visual_conflict_report(
                    output_dir=Path(
                        temp_dir
                    ),
                    scene_number=1,
                    visual_conflict_report=object(),
                )

    def test_writes_effective_visual_brief_and_preserves_complete_fields(self):
        analysis = _analysis_result()
        reasoning = _reasoning_result(
            analysis
        )
        conflicts = _conflict_report(
            analysis,
            reasoning,
        )
        brief = _effective_visual_brief(
            analysis,
            reasoning,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            writer = ImageEvidenceWriter()
            analysis_write = writer.write_visual_analysis_result(
                output_dir=root,
                scene_number=1,
                visual_analysis_result=analysis,
            )
            reasoning_write = writer.write_visual_reasoning_result(
                output_dir=root,
                scene_number=1,
                visual_reasoning_result=reasoning,
            )
            conflict_write = writer.write_visual_conflict_report(
                output_dir=root,
                scene_number=1,
                visual_conflict_report=conflicts,
            )
            brief_write = writer.write_effective_visual_brief(
                output_dir=root,
                scene_number=1,
                effective_visual_brief=brief,
            )

            artifact = json.loads(
                brief_write.artifact_path.read_text(
                    encoding="utf-8"
                )
            )
            index = json.loads(
                brief_write.index_path.read_text(
                    encoding="utf-8"
                )
            )

        expected_fields = {
            field.name
            for field in fields(
                EffectiveVisualBrief
            )
        }
        self.assertEqual(
            expected_fields,
            set(
                artifact
            ),
        )
        self.assertEqual(
            _json_compatible(
                asdict(
                    brief
                )
            ),
            artifact,
        )
        self.assertEqual(
            brief.fingerprint,
            artifact["fingerprint"],
        )
        entries = {
            artifact["artifact_id"]: artifact
            for artifact in index["artifacts"]
        }
        self.assertEqual(
            analysis_write.artifact_fingerprint,
            entries["visual_analysis_result"]["fingerprint"],
        )
        self.assertEqual(
            reasoning_write.artifact_fingerprint,
            entries["visual_reasoning_result"]["fingerprint"],
        )
        self.assertEqual(
            conflict_write.artifact_fingerprint,
            entries["visual_conflict_report"]["fingerprint"],
        )
        self.assertEqual(
            EvidenceArtifactStatus.AVAILABLE.value,
            entries["effective_visual_brief"]["status"],
        )
        self.assertEqual(
            brief_write.artifact_fingerprint,
            entries["effective_visual_brief"]["fingerprint"],
        )

    def test_repeated_effective_visual_brief_serialization_is_deterministic(self):
        analysis = _analysis_result()
        reasoning = _reasoning_result(
            analysis
        )
        brief = _effective_visual_brief(
            analysis,
            reasoning,
        )

        with tempfile.TemporaryDirectory() as first_dir:
            with tempfile.TemporaryDirectory() as second_dir:
                first = ImageEvidenceWriter().write_effective_visual_brief(
                    output_dir=Path(
                        first_dir
                    ),
                    scene_number=5,
                    effective_visual_brief=brief,
                )
                second = ImageEvidenceWriter().write_effective_visual_brief(
                    output_dir=Path(
                        second_dir
                    ),
                    scene_number=5,
                    effective_visual_brief=brief,
                )

                self.assertEqual(
                    first.artifact_path.read_text(
                        encoding="utf-8"
                    ),
                    second.artifact_path.read_text(
                        encoding="utf-8"
                    ),
                )
                self.assertEqual(
                    first.index_path.read_text(
                        encoding="utf-8"
                    ),
                    second.index_path.read_text(
                        encoding="utf-8"
                    ),
                )
                self.assertEqual(
                    first.artifact_fingerprint,
                    second.artifact_fingerprint,
                )
                self.assertEqual(
                    first.index_fingerprint,
                    second.index_fingerprint,
                )

    def test_rejects_non_effective_visual_brief(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(
                TypeError
            ):
                ImageEvidenceWriter().write_effective_visual_brief(
                    output_dir=Path(
                        temp_dir
                    ),
                    scene_number=1,
                    effective_visual_brief=object(),
                )

    def test_writes_visual_synthesis_result_and_preserves_complete_fields(self):
        analysis = _analysis_result()
        reasoning = _reasoning_result(
            analysis
        )
        conflicts = _conflict_report(
            analysis,
            reasoning,
        )
        synthesis_result = _visual_synthesis_result(
            analysis,
            reasoning,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            writer = ImageEvidenceWriter()
            analysis_write = writer.write_visual_analysis_result(
                output_dir=root,
                scene_number=1,
                visual_analysis_result=analysis,
            )
            reasoning_write = writer.write_visual_reasoning_result(
                output_dir=root,
                scene_number=1,
                visual_reasoning_result=reasoning,
            )
            conflict_write = writer.write_visual_conflict_report(
                output_dir=root,
                scene_number=1,
                visual_conflict_report=conflicts,
            )
            brief_write = writer.write_effective_visual_brief(
                output_dir=root,
                scene_number=1,
                effective_visual_brief=synthesis_result.brief,
            )
            synthesis_write = writer.write_visual_synthesis_result(
                output_dir=root,
                scene_number=1,
                visual_synthesis_result=synthesis_result,
            )

            artifact = json.loads(
                synthesis_write.artifact_path.read_text(
                    encoding="utf-8"
                )
            )
            index = json.loads(
                synthesis_write.index_path.read_text(
                    encoding="utf-8"
                )
            )

        expected_fields = {
            field.name
            for field in fields(
                VisualSynthesisResult
            )
        }
        self.assertEqual(
            expected_fields,
            set(
                artifact
            ),
        )
        self.assertEqual(
            _json_compatible(
                asdict(
                    synthesis_result
                )
            ),
            artifact,
        )
        self.assertEqual(
            synthesis_result.fingerprint,
            artifact["fingerprint"],
        )
        self.assertEqual(
            synthesis_result.brief.fingerprint,
            artifact["brief"]["fingerprint"],
        )
        self.assertEqual(
            synthesis_result.conflicts.fingerprint,
            artifact["conflicts"]["fingerprint"],
        )
        self.assertEqual(
            synthesis_result.trace.fingerprint,
            artifact["trace"]["fingerprint"],
        )
        entries = {
            artifact["artifact_id"]: artifact
            for artifact in index["artifacts"]
        }
        self.assertEqual(
            analysis_write.artifact_fingerprint,
            entries["visual_analysis_result"]["fingerprint"],
        )
        self.assertEqual(
            reasoning_write.artifact_fingerprint,
            entries["visual_reasoning_result"]["fingerprint"],
        )
        self.assertEqual(
            conflict_write.artifact_fingerprint,
            entries["visual_conflict_report"]["fingerprint"],
        )
        self.assertEqual(
            brief_write.artifact_fingerprint,
            entries["effective_visual_brief"]["fingerprint"],
        )
        self.assertEqual(
            EvidenceArtifactStatus.AVAILABLE.value,
            entries["visual_synthesis_result"]["status"],
        )
        self.assertEqual(
            synthesis_write.artifact_fingerprint,
            entries["visual_synthesis_result"]["fingerprint"],
        )

    def test_repeated_visual_synthesis_result_serialization_is_deterministic(self):
        analysis = _analysis_result()
        reasoning = _reasoning_result(
            analysis
        )
        synthesis_result = _visual_synthesis_result(
            analysis,
            reasoning,
        )

        with tempfile.TemporaryDirectory() as first_dir:
            with tempfile.TemporaryDirectory() as second_dir:
                first = ImageEvidenceWriter().write_visual_synthesis_result(
                    output_dir=Path(
                        first_dir
                    ),
                    scene_number=6,
                    visual_synthesis_result=synthesis_result,
                )
                second = ImageEvidenceWriter().write_visual_synthesis_result(
                    output_dir=Path(
                        second_dir
                    ),
                    scene_number=6,
                    visual_synthesis_result=synthesis_result,
                )

                self.assertEqual(
                    first.artifact_path.read_text(
                        encoding="utf-8"
                    ),
                    second.artifact_path.read_text(
                        encoding="utf-8"
                    ),
                )
                self.assertEqual(
                    first.index_path.read_text(
                        encoding="utf-8"
                    ),
                    second.index_path.read_text(
                        encoding="utf-8"
                    ),
                )
                self.assertEqual(
                    first.artifact_fingerprint,
                    second.artifact_fingerprint,
                )
                self.assertEqual(
                    first.index_fingerprint,
                    second.index_fingerprint,
                )

    def test_rejects_non_visual_synthesis_result(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(
                TypeError
            ):
                ImageEvidenceWriter().write_visual_synthesis_result(
                    output_dir=Path(
                        temp_dir
                    ),
                    scene_number=1,
                    visual_synthesis_result=object(),
                )

    def test_writes_prompt_translation_observation_and_preserves_complete_fields(self):
        analysis = _analysis_result()
        reasoning = _reasoning_result(
            analysis
        )
        synthesis_result = _visual_synthesis_result(
            analysis,
            reasoning,
        )
        observation = _prompt_translation_observation(
            synthesis_result
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            writer = ImageEvidenceWriter()
            synthesis_write = writer.write_visual_synthesis_result(
                output_dir=root,
                scene_number=1,
                visual_synthesis_result=synthesis_result,
            )
            observation_write = writer.write_prompt_translation_observation(
                output_dir=root,
                scene_number=1,
                prompt_translation_observation=observation,
            )

            artifact = json.loads(
                observation_write.artifact_path.read_text(
                    encoding="utf-8"
                )
            )
            index = json.loads(
                observation_write.index_path.read_text(
                    encoding="utf-8"
                )
            )

        expected_fields = {
            field.name
            for field in fields(
                PromptTranslationObservation
            )
        }
        self.assertEqual(
            expected_fields,
            set(
                artifact
            ),
        )
        self.assertEqual(
            _json_compatible(
                asdict(
                    observation
                )
            ),
            artifact,
        )
        self.assertEqual(
            observation.fingerprint,
            artifact["fingerprint"],
        )
        self.assertEqual(
            "VisualSynthesisResult",
            artifact["source_contract"],
        )
        self.assertIn(
            "compiled_prompt",
            {
                stage["stage_id"]
                for stage in artifact["stages"]
            },
        )
        entries = {
            artifact["artifact_id"]: artifact
            for artifact in index["artifacts"]
        }
        self.assertEqual(
            synthesis_write.artifact_fingerprint,
            entries["visual_synthesis_result"]["fingerprint"],
        )
        self.assertEqual(
            EvidenceArtifactStatus.AVAILABLE.value,
            entries["prompt_translation_observation"]["status"],
        )
        self.assertEqual(
            observation_write.artifact_fingerprint,
            entries["prompt_translation_observation"]["fingerprint"],
        )

    def test_repeated_prompt_translation_observation_serialization_is_deterministic(self):
        analysis = _analysis_result()
        reasoning = _reasoning_result(
            analysis
        )
        observation = _prompt_translation_observation(
            _visual_synthesis_result(
                analysis,
                reasoning,
            )
        )

        with tempfile.TemporaryDirectory() as first_dir:
            with tempfile.TemporaryDirectory() as second_dir:
                first = (
                    ImageEvidenceWriter().write_prompt_translation_observation(
                        output_dir=Path(
                            first_dir
                        ),
                        scene_number=7,
                        prompt_translation_observation=observation,
                    )
                )
                second = (
                    ImageEvidenceWriter().write_prompt_translation_observation(
                        output_dir=Path(
                            second_dir
                        ),
                        scene_number=7,
                        prompt_translation_observation=observation,
                    )
                )

                self.assertEqual(
                    first.artifact_path.read_text(
                        encoding="utf-8"
                    ),
                    second.artifact_path.read_text(
                        encoding="utf-8"
                    ),
                )
                self.assertEqual(
                    first.index_path.read_text(
                        encoding="utf-8"
                    ),
                    second.index_path.read_text(
                        encoding="utf-8"
                    ),
                )
                self.assertEqual(
                    first.artifact_fingerprint,
                    second.artifact_fingerprint,
                )
                self.assertEqual(
                    first.index_fingerprint,
                    second.index_fingerprint,
                )

    def test_rejects_non_prompt_translation_observation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(
                TypeError
            ):
                ImageEvidenceWriter().write_prompt_translation_observation(
                    output_dir=Path(
                        temp_dir
                    ),
                    scene_number=1,
                    prompt_translation_observation=object(),
                )

    def test_writes_visual_quality_result_and_updates_index(self):
        quality_result = {
            "status": "approved",
            "result_fingerprint": "quality-fingerprint",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            result = ImageEvidenceWriter().write_visual_quality_result(
                output_dir=Path(
                    temp_dir
                ),
                scene_number=1,
                visual_quality_result=quality_result,
            )

            artifact = json.loads(
                result.artifact_path.read_text(
                    encoding="utf-8"
                )
            )
            index = json.loads(
                result.index_path.read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(
            quality_result,
            artifact
        )
        entries = {
            artifact["artifact_id"]: artifact
            for artifact in index["artifacts"]
        }
        self.assertEqual(
            EvidenceArtifactStatus.AVAILABLE.value,
            entries["visual_quality_result"]["status"],
        )
        self.assertEqual(
            result.artifact_fingerprint,
            entries["visual_quality_result"]["fingerprint"],
        )


def _analysis_result():
    return VisualAnalysisOrchestrator().analyze(
        StoryboardScene(
            scene_number=1,
            text="La escena conserva su texto.",
            visible_subject="quiet valley",
            visible_action="dawn light spreads slowly",
            visible_environment="mountain landscape",
            time_context="dawn",
            key_objects=(
                "mist",
            ),
            spatial_relationships=(
                "mist rests below the ridge",
            ),
            filmable_interpretation="A quiet dawn over a valley",
            visual_constraints=(
                "no readable text",
            ),
            visual_truth_status="structured",
        )
    )


def _reasoning_result(
    analysis
):
    return VisualReasoningOrchestrator().reason(
        analysis
    )


def _conflict_report(
    analysis,
    reasoning
):
    return VisualSynthesisOrchestrator().conflict_resolver.resolve(
        analysis,
        reasoning,
    )


def _effective_visual_brief(
    analysis,
    reasoning
):
    return _visual_synthesis_result(
        analysis,
        reasoning,
    ).brief


def _visual_synthesis_result(
    analysis,
    reasoning
):
    return VisualSynthesisOrchestrator().synthesize(
        analysis,
        reasoning,
    )


def _prompt_translation_observation(
    synthesis_result
):
    translator = PromptTranslator()
    translator.translate_visual_synthesis_result(
        synthesis_result
    )
    return translator.last_observation


def _json_compatible(
    value
):
    if isinstance(
        value,
        Enum,
    ):
        return value.value
    if isinstance(
        value,
        dict,
    ):
        return {
            key: _json_compatible(
                item
            )
            for key, item in sorted(
                value.items()
            )
        }
    if isinstance(
        value,
        (
            tuple,
            list,
        ),
    ):
        return [
            _json_compatible(
                item
            )
            for item in value
        ]
    return value


if __name__ == "__main__":
    unittest.main()
