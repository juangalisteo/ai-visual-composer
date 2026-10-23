from dataclasses import FrozenInstanceError, fields, is_dataclass
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.modules.video_component.contracts import WanIntermediateOutput
from app.modules.video_component.direct_i2v import (
    DirectI2VArtifactOwnership,
    DirectI2VGenerationResult,
    DirectI2VGenerationService,
    DirectI2VRequest,
)
from app.modules.video_component.models import VideoClipGenerationResult
from app.shared.profile_identity import (
    OperationalProfileKey,
    ProfileComponent,
)


def _video_identity():
    return OperationalProfileKey(
        ProfileComponent.VIDEO,
        "fixture_platform",
        "fixture_video_profile",
    )


def _video_component_profile(intermediate_output):
    return {
        "platform": "fixture_platform",
        "video_component": {
            "profile": "technical-profile",
            "generation": {"width": 448, "height": 800},
            "delivery": {"intermediate_output": intermediate_output},
            "frames": 49,
            "fps": 12,
            "seed_mode": "fixed",
            "seed": 7,
            "sampling": {
                "steps": 20,
                "cfg": 5.0,
                "sampler": "uni_pc",
                "scheduler": "simple",
            },
        },
    }


class _StaticResolver:
    def __init__(self, profile):
        self.profile = profile
        self.calls = []

    def load_video_component(self, profile_key):
        self.calls.append(profile_key)
        return self.profile


class _FakeDirectVideoBuilder:
    def __init__(self):
        self.calls = []

    def generate_clip(
        self,
        *,
        source_path,
        output_dir,
        output_name,
        **overrides,
    ):
        output_path = Path(output_dir) / output_name
        if overrides["intermediate_output"] == "lossless_ffv1":
            output_path = output_path.with_suffix(".mkv")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"generated-video")
        self.calls.append(
            {
                "source_path": Path(source_path),
                "output_dir": Path(output_dir),
                "output_name": output_name,
                "overrides": overrides,
            }
        )
        return VideoClipGenerationResult(
            source_image=source_path,
            output_clip=output_path,
            manifest_path=None,
            prompt_id="technical-prompt",
            backend="comfyui",
            model="technical-model",
            workflow="technical-workflow",
            seed=overrides["seed"],
            frames=overrides["frames"],
            fps=overrides["fps"],
            generation_width=overrides["generation_width"],
            generation_height=overrides["generation_height"],
            steps=overrides["steps"],
            cfg=overrides["cfg"],
            sampler=overrides["sampler"],
            scheduler=overrides["scheduler"],
            profile_name=overrides["profile_name"],
            duration_seconds=overrides["frames"] / overrides["fps"],
            fingerprint="technical-fingerprint",
        )


class DirectI2VRequestTest(unittest.TestCase):

    def _generation(self, root):
        source_image = root / "source.png"
        output_clip = root / "clip.mkv"
        source_image.write_bytes(b"png")
        output_clip.write_bytes(b"ffv1")
        return VideoClipGenerationResult(
            source_image=source_image,
            output_clip=output_clip,
            manifest_path=None,
            prompt_id="technical-prompt",
            backend="comfyui",
            model="technical-model",
            workflow="technical-workflow",
            seed=7,
            frames=49,
            fps=12.0,
            generation_width=448,
            generation_height=800,
            steps=20,
            cfg=5.0,
            sampler="uni_pc",
            scheduler="simple",
            profile_name="technical-profile",
            duration_seconds=49 / 12,
            fingerprint="technical-fingerprint",
        )

    def test_artifact_ownership_is_explicit_and_caller_owned(self):
        self.assertIsInstance(
            DirectI2VArtifactOwnership.CALLER_OWNED,
            DirectI2VArtifactOwnership,
        )
        self.assertEqual(
            "caller_owned",
            DirectI2VArtifactOwnership.CALLER_OWNED.value,
        )
        self.assertEqual(
            (DirectI2VArtifactOwnership.CALLER_OWNED,),
            tuple(DirectI2VArtifactOwnership),
        )

    def test_generation_result_is_frozen_and_preserves_approved_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            generation = self._generation(Path(directory))
            profile_key = _video_identity()
            result = DirectI2VGenerationResult(
                generation=generation,
                profile_key=profile_key,
                intermediate_output="lossless_ffv1",
                ownership="caller_owned",
            )

        self.assertTrue(is_dataclass(result))
        self.assertTrue(result.__dataclass_params__.frozen)
        self.assertEqual(
            (
                "generation",
                "profile_key",
                "intermediate_output",
                "ownership",
            ),
            tuple(field.name for field in fields(result)),
        )
        self.assertIs(generation, result.generation)
        self.assertIs(profile_key, result.profile_key)
        self.assertEqual(
            WanIntermediateOutput.LOSSLESS_FFV1,
            result.intermediate_output,
        )
        self.assertEqual(
            DirectI2VArtifactOwnership.CALLER_OWNED,
            result.ownership,
        )
        with self.assertRaises(FrozenInstanceError):
            result.ownership = DirectI2VArtifactOwnership.CALLER_OWNED

    def test_generation_result_rejects_invalid_generation_or_identity(self):
        with self.assertRaisesRegex(TypeError, "VideoClipGenerationResult"):
            DirectI2VGenerationResult(
                generation="clip.mkv",
                profile_key=_video_identity(),
                intermediate_output=WanIntermediateOutput.LOSSLESS_FFV1,
                ownership=DirectI2VArtifactOwnership.CALLER_OWNED,
            )

        with tempfile.TemporaryDirectory() as directory:
            generation = self._generation(Path(directory))
            with self.assertRaisesRegex(ValueError, "VIDEO"):
                DirectI2VGenerationResult(
                    generation=generation,
                    profile_key=OperationalProfileKey(
                        ProfileComponent.IMAGEN,
                        "fixture_platform",
                        "fixture_image_profile",
                    ),
                    intermediate_output=WanIntermediateOutput.LOSSLESS_FFV1,
                    ownership=DirectI2VArtifactOwnership.CALLER_OWNED,
                )

    def test_service_loads_declared_parameters_and_returns_lossless_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "source.png"
            source_path.write_bytes(b"png")
            resolver = _StaticResolver(
                _video_component_profile("lossless_ffv1")
            )
            builder = _FakeDirectVideoBuilder()
            request = DirectI2VRequest(
                source_image=source_path,
                profile_key=_video_identity(),
                output_dir=root / "output",
                output_stem="opaque_direct_clip",
            )

            result = DirectI2VGenerationService(
                profile_resolver=resolver,
                video_builder=builder,
            ).generate(request)

        self.assertEqual([request.profile_key], resolver.calls)
        self.assertEqual(1, len(builder.calls))
        call = builder.calls[0]
        self.assertEqual(source_path, call["source_path"])
        self.assertEqual(request.output_dir, call["output_dir"])
        self.assertEqual("opaque_direct_clip.mp4", call["output_name"])
        self.assertEqual("lossless_ffv1", call["overrides"]["intermediate_output"])
        self.assertEqual(7, call["overrides"]["seed"])
        self.assertEqual(".mkv", result.generation.output_clip.suffix)
        self.assertEqual(
            WanIntermediateOutput.LOSSLESS_FFV1,
            result.intermediate_output,
        )
        self.assertEqual(
            DirectI2VArtifactOwnership.CALLER_OWNED,
            result.ownership,
        )

    def test_service_preserves_savevideo_h264_and_builder_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "source.png"
            source_path.write_bytes(b"png")
            resolver = _StaticResolver(
                _video_component_profile("savevideo_h264")
            )
            builder = _FakeDirectVideoBuilder()
            request = DirectI2VRequest(
                source_image=source_path,
                profile_key=_video_identity(),
                output_dir=root / "output",
                output_stem="opaque_direct_clip",
            )
            result = DirectI2VGenerationService(
                profile_resolver=resolver,
                video_builder=builder,
            ).generate(request)

        self.assertEqual(".mp4", result.generation.output_clip.suffix)
        self.assertEqual(
            WanIntermediateOutput.SAVEVIDEO_H264,
            result.intermediate_output,
        )

        failing_builder = _FakeDirectVideoBuilder()
        with patch.object(
            failing_builder,
            "generate_clip",
            side_effect=RuntimeError("builder failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "builder failure"):
                DirectI2VGenerationService(
                    profile_resolver=resolver,
                    video_builder=failing_builder,
                ).generate(request)

    def test_is_frozen_data_contract_with_opaque_technical_identity(self):
        profile_key = _video_identity()
        request = DirectI2VRequest(
            source_image=Path("outside-repository/source.png"),
            profile_key=profile_key,
            output_dir=Path("outside-repository/output"),
            output_stem="technical_output_stem",
        )

        self.assertTrue(is_dataclass(request))
        self.assertTrue(request.__dataclass_params__.frozen)
        self.assertEqual(
            ("source_image", "profile_key", "output_dir", "output_stem"),
            tuple(field.name for field in fields(request)),
        )
        self.assertIs(profile_key, request.profile_key)
        self.assertEqual("fixture_platform", request.profile_key.platform)
        self.assertEqual(
            "fixture_video_profile",
            request.profile_key.profile_id,
        )
        self.assertEqual(Path("outside-repository/source.png"), request.source_image)
        self.assertEqual(Path("outside-repository/output"), request.output_dir)
        self.assertEqual("technical_output_stem", request.output_stem)
        with self.assertRaises(FrozenInstanceError):
            request.output_stem = "other_stem"

    def test_accepts_pathlike_values_without_filesystem_access(self):
        request = DirectI2VRequest(
            source_image="missing/source.png",
            profile_key=_video_identity(),
            output_dir="missing/output",
            output_stem="clip",
        )

        self.assertEqual(Path("missing/source.png"), request.source_image)
        self.assertEqual(Path("missing/output"), request.output_dir)

    def test_rejects_empty_or_non_text_output_stem(self):
        for output_stem, error_type in (
            ("", ValueError),
            ("   ", ValueError),
            (None, TypeError),
            (123, TypeError),
        ):
            with self.subTest(output_stem=output_stem):
                with self.assertRaises(error_type):
                    DirectI2VRequest(
                        source_image=Path("source.png"),
                        profile_key=_video_identity(),
                        output_dir=Path("output"),
                        output_stem=output_stem,
                    )

    def test_rejects_non_operational_or_non_video_identity(self):
        with self.assertRaisesRegex(TypeError, "OperationalProfileKey"):
            DirectI2VRequest(
                source_image=Path("source.png"),
                profile_key="video_instagram",
                output_dir=Path("output"),
                output_stem="clip",
            )

        with self.assertRaisesRegex(ValueError, "VIDEO"):
            DirectI2VRequest(
                source_image=Path("source.png"),
                profile_key=OperationalProfileKey(
                    ProfileComponent.IMAGEN,
                    "fixture_platform",
                    "fixture_image_profile",
                ),
                output_dir=Path("output"),
                output_stem="clip",
            )


if __name__ == "__main__":
    unittest.main()
