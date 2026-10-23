from dataclasses import FrozenInstanceError, fields, is_dataclass
from pathlib import Path
import unittest

from app.modules.video_component.contracts import (
    ComfyUIInputOwnership,
    ComfyUIInputRetention,
    StagedComfyInput,
    WanBatchResult,
    WanClipArtifact,
    WanDeliveryParameters,
    WanGenerationParameters,
    WanIntermediateOutput,
    WanPartialArtifact,
    WanSamplingParameters,
    WanVideoComponentDocument,
    WanWorkflowBinding,
    WanWorkflowInputRole,
    WanWorkflowNodeRole,
)
from app.shared.profile_identity import OperationalProfileKey


def _document():
    return WanVideoComponentDocument(
        kind="video_component",
        operational_profile=OperationalProfileKey(
            "video", "fixture_platform", "fixture_profile"
        ),
        platform="fixture_platform",
        generation=WanGenerationParameters(
            width=448,
            height=800,
            frames=49,
            fps=12,
            seed_mode="fixed",
            seed=7,
        ),
        delivery=WanDeliveryParameters(),
        sampling=WanSamplingParameters(
            steps=20,
            cfg=5.0,
            sampler="uni_pc",
            scheduler="simple",
        ),
    )


def _clip(scene_number=1):
    return WanClipArtifact(
        scene_number=scene_number,
        source_image=Path("source.png"),
        output_clip=Path("scene.mp4"),
        prompt_id="job-prompt",
        seed=7,
        frames=49,
        fps=12,
        generation_width=448,
        generation_height=800,
        steps=20,
        cfg=5.0,
        sampler="uni_pc",
        scheduler="simple",
        backend="comfyui",
        model="technical-model",
        workflow="technical-workflow",
        duration_seconds=49 / 12,
        fingerprint="abc123",
    )


class WanContractsTest(unittest.TestCase):

    def test_delivery_parameters_validate_supported_intermediate_outputs(self):
        lossless = WanDeliveryParameters(
            intermediate_output="lossless_ffv1",
        )
        legacy = WanDeliveryParameters(
            intermediate_output="savevideo_h264",
        )

        self.assertEqual(
            WanIntermediateOutput.LOSSLESS_FFV1,
            lossless.intermediate_output,
        )
        self.assertEqual(
            WanIntermediateOutput.SAVEVIDEO_H264,
            legacy.intermediate_output,
        )

    def test_delivery_parameters_adapt_legacy_absence_to_savevideo_h264(self):
        delivery = WanDeliveryParameters()

        self.assertEqual(
            WanIntermediateOutput.SAVEVIDEO_H264,
            delivery.intermediate_output,
        )

    def test_delivery_parameters_reject_invalid_intermediate_output(self):
        with self.assertRaisesRegex(ValueError, "intermediate_output"):
            WanDeliveryParameters(
                intermediate_output="unsupported_output",
            )

    def test_video_component_document_is_frozen_and_uses_operational_identity(self):
        document = _document()

        self.assertTrue(is_dataclass(document))
        self.assertTrue(document.__dataclass_params__.frozen)
        self.assertEqual("fixture_profile", document.operational_profile.profile_id)
        self.assertEqual("fixture_platform", document.platform)
        self.assertNotIn("display_name", {field.name for field in fields(document)})
        with self.assertRaises(FrozenInstanceError):
            document.platform = "other_platform"

    def test_document_requires_video_identity_and_matching_platform(self):
        values = _document()
        with self.assertRaises(ValueError):
            WanVideoComponentDocument(
                kind="video_component",
                operational_profile=OperationalProfileKey(
                    "imagen", "fixture_platform", "fixture_profile"
                ),
                platform="fixture_platform",
                generation=values.generation,
                delivery=values.delivery,
                sampling=values.sampling,
            )
        with self.assertRaises(ValueError):
            WanVideoComponentDocument(
                kind="video_component",
                operational_profile=values.operational_profile,
                platform="other_platform",
                generation=values.generation,
                delivery=values.delivery,
                sampling=values.sampling,
            )

    def test_staged_input_is_data_only_with_approved_retention_states(self):
        staged = StagedComfyInput(
            job_id="technical-job",
            source_path="input/source.png",
            relative_input_name="wan_i2v/technical-job/source.png",
            staged_path="ComfyUI/input/wan_i2v/technical-job/source.png",
            ownership=ComfyUIInputOwnership.BACKEND_OWNED,
            retention=ComfyUIInputRetention.PRESERVE_ON_FAILURE,
        )

        self.assertEqual(Path("input/source.png"), staged.source_path)
        self.assertEqual(
            ComfyUIInputRetention.PRESERVE_ON_FAILURE,
            staged.retention,
        )
        with self.assertRaises(ValueError):
            StagedComfyInput(
                job_id="technical-job",
                source_path="source.png",
                relative_input_name="../outside.png",
                staged_path="staged.png",
            )

    def test_workflow_binding_uses_semantic_roles_without_node_ids(self):
        binding = WanWorkflowBinding(
            node_roles=(
                WanWorkflowNodeRole("sampler", "KSampler"),
                WanWorkflowNodeRole("load_image", "LoadImage"),
            ),
            positive_prompt=WanWorkflowInputRole(
                "sampler", "positive", "CLIPTextEncode"
            ),
            negative_prompt=WanWorkflowInputRole(
                "sampler", "negative", "CLIPTextEncode"
            ),
        )

        self.assertTrue(binding.__dataclass_params__.frozen)
        self.assertNotIn("node_id", {field.name for field in fields(WanWorkflowNodeRole)})
        with self.assertRaises(ValueError):
            WanWorkflowBinding(
                node_roles=(
                    WanWorkflowNodeRole("sampler", "KSampler"),
                    WanWorkflowNodeRole("sampler", "OtherSampler"),
                ),
                positive_prompt=binding.positive_prompt,
                negative_prompt=binding.negative_prompt,
            )

    def test_batch_contract_distinguishes_complete_and_partial_artifacts(self):
        complete = WanBatchResult(status="complete", completed_clips=(_clip(),))
        partial = WanBatchResult(
            status="partial",
            completed_clips=(_clip(),),
            partial_artifacts=(
                WanPartialArtifact(
                    scene_number=2,
                    prompt_id="failed-prompt",
                    diagnostic_reference="diagnostics/job-2.json",
                ),
            ),
        )

        self.assertEqual("complete", complete.status)
        self.assertEqual("partial", partial.status)
        with self.assertRaises(ValueError):
            WanBatchResult(status="complete", completed_clips=(_clip(),), partial_artifacts=partial.partial_artifacts)


if __name__ == "__main__":
    unittest.main()
