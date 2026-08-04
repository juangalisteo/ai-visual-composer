import unittest
from dataclasses import FrozenInstanceError, is_dataclass

from app.visual_quality import (
    ConfidenceBand,
    FailureClassification,
    ImageValidator,
    SeverityDefinition,
    ValidationProfileConfig,
    ValidationThresholds,
    create_confidence_band,
    create_failure_classification,
    create_generated_asset,
    create_severity_definition,
    create_validation_context,
    create_validation_failure,
    create_validation_profile_config,
    create_validation_thresholds,
)


def generated_asset():
    return create_generated_asset(
        asset_id="asset-1",
        scene_id="scene-001",
        sequence_id="sequence-001",
        asset_type="image",
        path="scene_001.png",
        attempt_number=1,
        generation_attempt_id="scene-001-attempt-1",
        width=1024,
        height=576,
    )


def validation_context():
    return create_validation_context(
        scene_id="scene-001",
        sequence_id="sequence-001",
        validation_profile="image-v1",
    )


def severity_definition():
    return create_severity_definition(
        severity="high",
        blocks_acceptance=True,
        score_penalty=0.5,
        retry_relevant_by_default=True,
        description="Blocking product-quality failure.",
    )


def confidence_band():
    return create_confidence_band(
        band_id="high",
        minimum=0.8,
        maximum=1.0,
        review_recommended=False,
        description="High-confidence validation result.",
    )


def failure_classification():
    return create_failure_classification(
        failure_type="watermark_detected",
        category="artifact",
        default_severity="high",
        retry_relevant_by_default=True,
        description="Visible watermark or provider mark.",
    )


def thresholds():
    return create_validation_thresholds(
        thresholds_id="image-foundation",
        blocking_confidence=0.8,
        manual_review_confidence=0.4,
        high_confidence=0.8,
    )


class VisualQualityFoundationTest(unittest.TestCase):

    def test_foundation_models_are_passive_frozen_dataclasses(self):
        for model in (
            SeverityDefinition,
            ConfidenceBand,
            FailureClassification,
            ValidationThresholds,
            ValidationProfileConfig,
        ):
            with self.subTest(
                model=model.__name__
            ):
                self.assertTrue(
                    is_dataclass(
                        model
                    )
                )
                self.assertTrue(
                    model.__dataclass_params__.frozen
                )

    def test_foundation_models_are_immutable(self):
        definition = severity_definition()

        with self.assertRaises(
            FrozenInstanceError
        ):
            definition.description = "changed"

    def test_extended_failure_taxonomy_accepts_m1_product_quality_types(self):
        for failure_type in (
            "watermark_detected",
            "hands_error",
            "face_error",
            "object_missing",
            "unexpected_object",
            "composition_failure",
            "cropping_error",
            "readability_failure",
            "background_artifact",
            "style_drift",
            "lighting_mismatch",
        ):
            with self.subTest(
                failure_type=failure_type
            ):
                failure = create_validation_failure(
                    failure_type=failure_type,
                    severity="medium",
                    confidence=0.75,
                    evidence="contract-level evidence",
                    technical_message="passive taxonomy validation",
                    retry_relevant=True,
                )

                self.assertEqual(
                    failure.failure_type,
                    failure_type
                )
                self.assertTrue(
                    failure.failure_fingerprint
                )

    def test_validation_profile_config_has_deterministic_fingerprint(self):
        first = create_validation_profile_config(
            profile_id="image-product-quality",
            enabled_checks=(
                "watermark_detected",
            ),
            failure_classifications=(
                failure_classification(),
            ),
            severity_definitions=(
                severity_definition(),
            ),
            confidence_bands=(
                confidence_band(),
            ),
            thresholds=thresholds(),
        )
        second = create_validation_profile_config(
            profile_id="image-product-quality",
            enabled_checks=(
                "watermark_detected",
            ),
            failure_classifications=(
                failure_classification(),
            ),
            severity_definitions=(
                severity_definition(),
            ),
            confidence_bands=(
                confidence_band(),
            ),
            thresholds=thresholds(),
        )

        self.assertEqual(
            first.profile_fingerprint,
            second.profile_fingerprint
        )

    def test_validation_profile_config_fingerprint_changes_on_effective_change(self):
        first = create_validation_profile_config(
            profile_id="image-product-quality",
            enabled_checks=(
                "watermark_detected",
            ),
            failure_classifications=(
                failure_classification(),
            ),
            severity_definitions=(
                severity_definition(),
            ),
            confidence_bands=(
                confidence_band(),
            ),
            thresholds=thresholds(),
        )
        second = create_validation_profile_config(
            profile_id="image-product-quality",
            enabled_checks=(
                "watermark_detected",
                "hands_error",
            ),
            failure_classifications=(
                failure_classification(),
            ),
            severity_definitions=(
                severity_definition(),
            ),
            confidence_bands=(
                confidence_band(),
            ),
            thresholds=thresholds(),
        )

        self.assertNotEqual(
            first.profile_fingerprint,
            second.profile_fingerprint
        )

    def test_validation_profile_config_rejects_duplicate_enabled_checks(self):
        with self.assertRaises(
            ValueError
        ):
            create_validation_profile_config(
                profile_id="image-product-quality",
                enabled_checks=(
                    "watermark_detected",
                    "watermark_detected",
                ),
                failure_classifications=(
                    failure_classification(),
                ),
                severity_definitions=(
                    severity_definition(),
                ),
                confidence_bands=(
                    confidence_band(),
                ),
                thresholds=thresholds(),
            )

    def test_confidence_contract_rejects_invalid_range(self):
        with self.assertRaises(
            ValueError
        ):
            create_confidence_band(
                band_id="invalid",
                minimum=0.9,
                maximum=0.2,
                review_recommended=True,
                description="invalid band",
            )

    def test_threshold_contract_rejects_out_of_range_values(self):
        with self.assertRaises(
            ValueError
        ):
            create_validation_thresholds(
                thresholds_id="invalid",
                blocking_confidence=1.2,
                manual_review_confidence=0.4,
                high_confidence=0.8,
            )

    def test_foundation_contracts_do_not_activate_validation_logic(self):
        report = ImageValidator(
            checks=()
        ).validate(
            generated_asset(),
            validation_context()
        )

        self.assertEqual(
            report.status,
            "accepted"
        )
        self.assertEqual(
            report.checks,
            ()
        )
        self.assertEqual(
            report.failures,
            ()
        )


if __name__ == "__main__":
    unittest.main()
