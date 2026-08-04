import unittest

from app.evidence import (
    ARTIFACT_FILENAMES,
    EvidenceArtifactReference,
    EvidenceArtifactStatus,
    ImageEvidenceIndex,
    ImageEvidencePathPolicy,
    build_image_evidence_index,
)


class ImageEvidenceIndexTest(unittest.TestCase):

    def test_builds_deterministic_scene_index(self):
        first = build_image_evidence_index(
            1
        )
        second = build_image_evidence_index(
            1
        )

        self.assertEqual(
            first,
            second,
        )
        self.assertEqual(
            first.fingerprint,
            second.fingerprint,
        )
        self.assertEqual(
            "evidence/scene_001",
            first.scene_directory,
        )
        self.assertEqual(
            tuple(
                sorted(
                    ARTIFACT_FILENAMES
                )
            ),
            tuple(
                artifact.artifact_id
                for artifact in first.artifacts
            ),
        )

    def test_index_uses_relative_paths_only(self):
        index = build_image_evidence_index(
            12
        )

        self.assertEqual(
            "evidence/scene_012",
            index.scene_directory,
        )
        self.assertTrue(
            all(
                artifact.relative_path.startswith(
                    "evidence/scene_012/"
                )
                for artifact in index.artifacts
            )
        )
        self.assertFalse(
            any(
                ":" in artifact.relative_path
                for artifact in index.artifacts
            )
        )

    def test_index_supports_explicit_artifact_subset(self):
        index = build_image_evidence_index(
            2,
            artifact_ids=(
                "source_scene",
                "backend_prompt",
            ),
        )

        self.assertEqual(
            (
                "source_scene",
                "backend_prompt",
            ),
            tuple(
                artifact.artifact_id
                for artifact in index.artifacts
            ),
        )
        self.assertEqual(
            "source_scene.json",
            index.artifacts[
                0
            ].filename,
        )

    def test_custom_policy_changes_relative_index_shape(self):
        policy = ImageEvidencePathPolicy(
            root_directory_name="proof",
            scene_directory_prefix="shot_",
            scene_number_width=4,
        )

        index = build_image_evidence_index(
            3,
            policy=policy,
            artifact_ids=(
                "effective_workflow",
            ),
        )

        self.assertEqual(
            "proof/shot_0003",
            index.scene_directory,
        )
        self.assertEqual(
            "proof/shot_0003/effective_workflow.json",
            index.artifacts[
                0
            ].relative_path,
        )

    def test_fingerprint_changes_when_artifact_status_changes(self):
        expected = build_image_evidence_index(
            1,
            artifact_ids=(
                "source_scene",
            ),
        )
        available = ImageEvidenceIndex(
            scene_number=1,
            scene_directory="evidence/scene_001",
            artifacts=(
                EvidenceArtifactReference(
                    artifact_id="source_scene",
                    filename="source_scene.json",
                    relative_path="evidence/scene_001/source_scene.json",
                    status=EvidenceArtifactStatus.AVAILABLE,
                ),
            ),
        )

        self.assertNotEqual(
            expected.fingerprint,
            available.fingerprint,
        )

    def test_rejects_absolute_paths(self):
        with self.assertRaises(
            ValueError
        ):
            EvidenceArtifactReference(
                artifact_id="source_scene",
                filename="source_scene.json",
                relative_path="C:/tmp/source_scene.json",
            )

    def test_rejects_unknown_artifact_id(self):
        with self.assertRaises(
            ValueError
        ):
            build_image_evidence_index(
                1,
                artifact_ids=(
                    "unknown",
                ),
            )

    def test_index_serializes_to_canonical_dict(self):
        index = build_image_evidence_index(
            1,
            artifact_ids=(
                "source_scene",
            ),
        )

        self.assertEqual(
            {
                "scene_number": 1,
                "scene_directory": "evidence/scene_001",
                "artifacts": [
                    {
                        "artifact_id": "source_scene",
                        "filename": "source_scene.json",
                        "relative_path": "evidence/scene_001/source_scene.json",
                        "status": "expected",
                        "fingerprint": "",
                    },
                ],
                "schema_version": "1.0.0",
                "version": "image-evidence-index-v1",
                "fingerprint": index.fingerprint,
            },
            index.to_dict(),
        )


if __name__ == "__main__":
    unittest.main()
