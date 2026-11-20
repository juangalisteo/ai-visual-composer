import inspect
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.modules.video_component import WanIntermediateOutput
from app.modules.video_component.profile_parameters import (
    build_video_backend_overrides,
    load_video_component_parameters,
)
from app.shared.operational_error import OperationalError
from app.shared.profile_identity import (
    OperationalProfileKey,
    ProfileComponent,
)
from app.shared.profile_resolver import ProfileResolver


class VideoComponentProfileParametersTest(unittest.TestCase):

    def _document(self, profile_id, profile_format, intermediate_output):
        return {
            "kind": "video_component",
            "operational_profile_id": profile_id,
            "format": profile_format,
            "display_name": "Presentation-only label",
            "video_component": {
                "profile": "Technical profile label",
                "generation": {"width": 448, "height": 800},
                "delivery": {
                    "intermediate_output": intermediate_output,
                },
                "frames": 49,
                "fps": 12,
                "seed_mode": "random",
                "sampling": {
                    "steps": 20,
                    "cfg": 5.0,
                    "sampler": "uni_pc",
                    "scheduler": "simple",
                },
            },
        }

    def _write_document(self, root, profile_format, filename, document):
        path = root / "video" / profile_format / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document), encoding="utf-8")
        return path

    def test_official_documents_load_and_preserve_lossless_parameters(self):
        expected = {
            "vertical": ("video_vertical", 448, 800),
            "horizontal": ("video_horizontal", 800, 448),
        }

        for profile_format, values in expected.items():
            with self.subTest(profile_format=profile_format), patch(
                "app.modules.video_component.profile_parameters._random_video_seed",
                return_value=123,
            ):
                profile_id, width, height = values
                profile = load_video_component_parameters(
                    OperationalProfileKey(
                        ProfileComponent.VIDEO,
                        profile_format,
                        profile_id,
                    )
                )
                overrides = build_video_backend_overrides(profile)

            self.assertEqual(width, overrides["generation_width"])
            self.assertEqual(height, overrides["generation_height"])
            self.assertEqual(81, overrides["frames"])
            self.assertEqual(12.0, overrides["fps"])
            self.assertEqual(20, overrides["steps"])
            self.assertEqual(5.0, overrides["cfg"])
            self.assertEqual("uni_pc", overrides["sampler"])
            self.assertEqual("simple", overrides["scheduler"])
            self.assertEqual("lossless_ffv1", overrides["intermediate_output"])

    def test_non_video_identity_is_rejected_before_resolution(self):
        with self.assertRaisesRegex(ValueError, "componente video"):
            load_video_component_parameters(
                OperationalProfileKey(
                    ProfileComponent.IMAGEN,
                    "vertical",
                    "opaque_image_identity",
                )
            )

    def test_custom_declarative_document_uses_identity_not_filename_or_label(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_document(
                root,
                "custom_format",
                "arbitrary-file-name.json",
                self._document(
                    "opaque_video_identity",
                    "custom_format",
                    "savevideo_h264",
                ),
            )
            with patch(
                "app.modules.video_component.profile_parameters._random_video_seed",
                return_value=7,
            ):
                profile = load_video_component_parameters(
                    OperationalProfileKey(
                        ProfileComponent.VIDEO,
                        "custom_format",
                        "opaque_video_identity",
                    ),
                    resolver=ProfileResolver(root),
                )
                overrides = build_video_backend_overrides(profile)

        self.assertEqual("savevideo_h264", overrides["intermediate_output"])
        self.assertEqual(7, overrides["seed"])
        self.assertEqual(
            WanIntermediateOutput.SAVEVIDEO_H264,
            WanIntermediateOutput(overrides["intermediate_output"]),
        )

    def test_random_and_fixed_seed_modes_preserve_current_behavior(self):
        random_profile = self._document(
            "opaque_video_identity",
            "custom_format",
            "lossless_ffv1",
        )
        fixed_profile = self._document(
            "opaque_video_identity",
            "custom_format",
            "lossless_ffv1",
        )
        fixed_profile["video_component"].update(
            {"seed_mode": "fixed", "seed": 987654321}
        )

        with patch(
            "app.modules.video_component.profile_parameters._random_video_seed",
            return_value=123,
        ) as random_seed:
            random_overrides = build_video_backend_overrides(random_profile)
            fixed_overrides = build_video_backend_overrides(fixed_profile)

        random_seed.assert_called_once_with()
        self.assertEqual(123, random_overrides["seed"])
        self.assertEqual(987654321, fixed_overrides["seed"])

    def test_invalid_seed_mode_preserves_value_error_contract(self):
        profile = self._document(
            "opaque_video_identity",
            "custom_format",
            "lossless_ffv1",
        )
        profile["video_component"]["seed_mode"] = "unsupported"

        with self.assertRaisesRegex(ValueError, "seed_mode"):
            build_video_backend_overrides(profile)

    def test_missing_declarative_document_preserves_configuration_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(OperationalError) as caught:
                load_video_component_parameters(
                    OperationalProfileKey(
                        ProfileComponent.VIDEO,
                        "custom_format",
                        "opaque_video_identity",
                    ),
                    resolver=ProfileResolver(root),
                )

        self.assertEqual("CONFIG", caught.exception.context.family)

    def test_module_has_no_pipeline_mode_dependency(self):
        import app.modules.video_component.profile_parameters as module

        self.assertNotIn("MC_PIPELINE_MODE", inspect.getsource(module))


if __name__ == "__main__":
    unittest.main()
