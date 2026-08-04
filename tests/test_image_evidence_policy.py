import unittest
from pathlib import Path

from app.evidence import (
    ARTIFACT_FILENAMES,
    ImageEvidencePathPolicy,
)


class ImageEvidencePathPolicyTest(unittest.TestCase):

    def test_scene_directory_is_deterministic(self):
        policy = ImageEvidencePathPolicy()

        first = policy.scene_directory(
            Path(
                "output/images"
            ),
            1,
        )
        second = policy.scene_directory(
            Path(
                "output/images"
            ),
            1,
        )

        self.assertEqual(
            Path(
                "output/images/evidence/scene_001"
            ),
            first,
        )
        self.assertEqual(
            first,
            second,
        )

    def test_artifact_paths_use_official_filenames(self):
        policy = ImageEvidencePathPolicy()

        self.assertEqual(
            Path(
                "build/evidence/scene_012/effective_visual_brief.json"
            ),
            policy.artifact_path(
                "build",
                12,
                "effective_visual_brief",
            ),
        )
        self.assertEqual(
            Path(
                "build/evidence/scene_012/effective_workflow.json"
            ),
            policy.artifact_path(
                "build",
                12,
                "effective_workflow",
            ),
        )

    def test_all_artifact_filenames_are_stable_json_names(self):
        self.assertEqual(
            (
                "backend_prompt",
                "cinematic_direction_set",
                "comfyui_payload",
                "effective_visual_brief",
                "effective_workflow",
                "final_prompt_segments",
                "prompt_translation_observation",
                "source_scene",
                "visual_analysis_result",
                "visual_conflict_report",
                "visual_intelligence_trace",
                "visual_quality_result",
                "visual_reasoning_result",
                "visual_synthesis_result",
                "visual_truth_scene",
            ),
            tuple(
                sorted(
                    ARTIFACT_FILENAMES
                )
            ),
        )
        self.assertTrue(
            all(
                filename.endswith(
                    ".json"
                )
                for filename in ARTIFACT_FILENAMES.values()
            )
        )

    def test_scene_number_must_be_positive_integer(self):
        policy = ImageEvidencePathPolicy()

        for scene_number in (
            0,
            -1,
            1.5,
            "1",
        ):
            with self.subTest(
                scene_number=scene_number
            ):
                with self.assertRaises(
                    ValueError
                ):
                    policy.scene_directory_name(
                        scene_number
                    )

    def test_unknown_artifact_id_is_rejected(self):
        with self.assertRaises(
            ValueError
        ):
            ImageEvidencePathPolicy().artifact_filename(
                "unknown"
            )

    def test_policy_does_not_create_directories(self):
        temporary_root = Path(
            "this_directory_must_not_be_created"
        )

        path = ImageEvidencePathPolicy().artifact_path(
            temporary_root,
            1,
            "source_scene",
        )

        self.assertEqual(
            temporary_root
            / "evidence"
            / "scene_001"
            / "source_scene.json",
            path,
        )
        self.assertFalse(
            temporary_root.exists()
        )


if __name__ == "__main__":
    unittest.main()
