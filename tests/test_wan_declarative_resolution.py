import json
import tempfile
import unittest
from pathlib import Path

from app.shared.operational_error import OperationalError
from app.shared.profile_identity import OperationalProfileKey, ProfileComponent
from app.shared.profile_resolver import ProfileResolver
from app.modules.video_component.contracts import WanIntermediateOutput


class WanDeclarativeResolutionTest(unittest.TestCase):
    LEGACY_COMPONENTS = {
        "instagram": {
            "profile": "Instagram",
            "generation": {"width": 448, "height": 800},
            "target": {"width": 1080, "height": 1920},
            "delivery": {"intermediate_output": "lossless_ffv1"},
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
        "youtube": {
            "profile": "YouTube",
            "generation": {"width": 800, "height": 448},
            "target": {"width": 1920, "height": 1080},
            "delivery": {"intermediate_output": "lossless_ffv1"},
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

    def _write_document(self, root, platform, filename, document):
        path = root / "video" / platform / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document), encoding="utf-8")
        return path

    @staticmethod
    def _document(profile_id, platform, **overrides):
        document = {
            "kind": "video_component",
            "operational_profile_id": profile_id,
            "platform": platform,
            "display_name": "Etiqueta que no participa en la resolucion",
            "video_component": {
                "generation": {"width": 448, "height": 800},
                "target": {"width": 1080, "height": 1920},
                "delivery": {
                    "intermediate_output": "lossless_ffv1",
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
        document.update(overrides)
        return document

    def test_resolves_exact_operational_identity_without_filename_or_label(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = self._write_document(
                root,
                "instagram",
                "arbitrary-document-name.json",
                self._document("opaque_video_identity", "instagram"),
            )

            resolved = ProfileResolver(root).resolve_video_component(
                OperationalProfileKey(
                    ProfileComponent.VIDEO,
                    "instagram",
                    "opaque_video_identity",
                )
            )

        self.assertEqual(expected, resolved)

    def test_declarative_resolution_isolated_by_platform(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            instagram = self._write_document(
                root,
                "instagram",
                "instagram-document.json",
                self._document("shared_opaque_identity", "instagram"),
            )
            youtube = self._write_document(
                root,
                "youtube",
                "youtube-document.json",
                self._document("shared_opaque_identity", "youtube"),
            )
            resolver = ProfileResolver(root)

            instagram_resolved = resolver.resolve_video_component(
                OperationalProfileKey(
                    ProfileComponent.VIDEO,
                    "instagram",
                    "shared_opaque_identity",
                )
            )
            youtube_resolved = resolver.resolve_video_component(
                OperationalProfileKey(
                    ProfileComponent.VIDEO,
                    "youtube",
                    "shared_opaque_identity",
                )
            )

        self.assertEqual(instagram, instagram_resolved)
        self.assertEqual(youtube, youtube_resolved)

    def test_legacy_filename_without_declarative_contract_raises_configuration_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = self._write_document(
                root,
                "instagram",
                "wan_i2v_instagram.json",
                {"platform": "video", "video_component": {}},
            )
            self._write_document(
                root,
                "instagram",
                "other-declarative-document.json",
                self._document("different_opaque_identity", "instagram"),
            )

            with self.assertRaises(OperationalError) as caught:
                ProfileResolver(root).resolve_video_component(
                    OperationalProfileKey(
                        ProfileComponent.VIDEO,
                        "instagram",
                        "requested_opaque_identity",
                    )
                )

        self.assertEqual("CONFIG", caught.exception.context.family)
        self.assertEqual(str(root / "video" / "instagram"), caught.exception.context.resource)
        self.assertEqual(
            "requested_opaque_identity",
            caught.exception.context.technical_metadata["profile_id"],
        )

    def test_duplicate_declarative_documents_raise_configuration_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_document(
                root,
                "instagram",
                "first.json",
                self._document("duplicate_identity", "instagram"),
            )
            self._write_document(
                root,
                "instagram",
                "second.json",
                self._document("duplicate_identity", "instagram"),
            )

            with self.assertRaises(OperationalError) as caught:
                ProfileResolver(root).resolve_video_component(
                    OperationalProfileKey(
                        ProfileComponent.VIDEO,
                        "instagram",
                        "duplicate_identity",
                    )
                )

        self.assertEqual("CONFIG", caught.exception.context.family)
        self.assertEqual(
            "Resolver componente Wan declarativo",
            caught.exception.context.operation,
        )

    def test_invalid_declarative_document_raises_without_legacy_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_document(
                root,
                "instagram",
                "wan_i2v_instagram.json",
                {"platform": "video", "video_component": {}},
            )
            invalid = self._write_document(
                root,
                "instagram",
                "invalid-declarative-document.json",
                {
                    "kind": "video_component",
                    "operational_profile_id": "opaque_identity",
                    "platform": "instagram",
                },
            )

            with self.assertRaises(OperationalError) as caught:
                ProfileResolver(root).resolve_video_component(
                    OperationalProfileKey(
                        ProfileComponent.VIDEO,
                        "instagram",
                        "opaque_identity",
                    )
                )

        self.assertEqual("CONFIG", caught.exception.context.family)
        self.assertEqual(str(invalid), caught.exception.context.resource)

    def test_declarative_validation_requires_and_transports_intermediate_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resolver = ProfileResolver(root)
            key = OperationalProfileKey(
                ProfileComponent.VIDEO,
                "instagram",
                "opaque_identity",
            )

            for value, expected in (
                ("lossless_ffv1", WanIntermediateOutput.LOSSLESS_FFV1),
                ("savevideo_h264", WanIntermediateOutput.SAVEVIDEO_H264),
            ):
                with self.subTest(intermediate_output=value):
                    document = self._document(
                        "opaque_identity",
                        "instagram",
                    )
                    document["video_component"]["delivery"] = {
                        "intermediate_output": value,
                    }
                    path = self._write_document(
                        root,
                        "instagram",
                        f"delivery-{value}.json",
                        document,
                    )

                    validated = resolver._validate_declarative_video_component_document(
                        document,
                        path,
                        key,
                    )

                    self.assertEqual(expected, validated.delivery.intermediate_output)
                    self.assertEqual(448, validated.generation.width)
                    self.assertEqual(1920, validated.delivery.height)
                    self.assertEqual("uni_pc", validated.sampling.sampler)

    def test_missing_delivery_raises_configuration_error_without_legacy_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document("opaque_identity", "instagram")
            del document["video_component"]["delivery"]
            invalid = self._write_document(
                root,
                "instagram",
                "missing-delivery.json",
                document,
            )

            with self.assertRaises(OperationalError) as caught:
                ProfileResolver(root).resolve_video_component(
                    OperationalProfileKey(
                        ProfileComponent.VIDEO,
                        "instagram",
                        "opaque_identity",
                    )
                )

        self.assertEqual("CONFIG", caught.exception.context.family)
        self.assertEqual(str(invalid), caught.exception.context.resource)
        self.assertIn(
            "video_component.delivery",
            caught.exception.context.technical_metadata["validation_error"],
        )

    def test_missing_intermediate_output_raises_configuration_error_without_legacy_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document("opaque_identity", "instagram")
            document["video_component"]["delivery"] = {}
            invalid = self._write_document(
                root,
                "instagram",
                "missing-intermediate-output.json",
                document,
            )

            with self.assertRaises(OperationalError) as caught:
                ProfileResolver(root).resolve_video_component(
                    OperationalProfileKey(
                        ProfileComponent.VIDEO,
                        "instagram",
                        "opaque_identity",
                    )
                )

        self.assertEqual("CONFIG", caught.exception.context.family)
        self.assertEqual(str(invalid), caught.exception.context.resource)
        self.assertIn(
            "video_component.delivery.intermediate_output",
            caught.exception.context.technical_metadata["validation_error"],
        )

    def test_invalid_intermediate_output_raises_without_legacy_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document("opaque_identity", "instagram")
            document["video_component"]["delivery"] = {
                "intermediate_output": "unsupported_output",
            }
            invalid = self._write_document(
                root,
                "instagram",
                "invalid-delivery.json",
                document,
            )

            with self.assertRaises(OperationalError) as caught:
                ProfileResolver(root).resolve_video_component(
                    OperationalProfileKey(
                        ProfileComponent.VIDEO,
                        "instagram",
                        "opaque_identity",
                    )
                )

        self.assertEqual("CONFIG", caught.exception.context.family)
        self.assertEqual(str(invalid), caught.exception.context.resource)

    def test_non_video_identity_is_rejected(self):
        with self.assertRaises(ValueError):
            ProfileResolver().resolve_video_component(
                OperationalProfileKey(
                    ProfileComponent.IMAGEN,
                    "instagram",
                    "opaque_image_identity",
                )
            )

    def test_official_wan_documents_resolve_declaratively_without_fallback(self):
        resolver = ProfileResolver()
        cases = (
            ("instagram", "video_instagram", "wan_i2v_instagram.json"),
            ("youtube", "video_youtube", "wan_i2v_youtube.json"),
        )

        for platform, profile_id, filename in cases:
            with self.subTest(platform=platform):
                key = OperationalProfileKey(
                    ProfileComponent.VIDEO,
                    platform,
                    profile_id,
                )
                path = resolver.resolve_video_component(key)
                component = resolver.load_video_component(key)
                validated = resolver._validate_declarative_video_component_document(
                    component,
                    path,
                    key,
                )

                self.assertEqual(filename, path.name)
                self.assertEqual("video_component", component["kind"])
                self.assertEqual(profile_id, component["operational_profile_id"])
                self.assertEqual(platform, component["platform"])
                self.assertEqual(
                    self.LEGACY_COMPONENTS[platform],
                    component["video_component"],
                )
                self.assertEqual(
                    WanIntermediateOutput.LOSSLESS_FFV1,
                    validated.delivery.intermediate_output,
                )

    def test_wrong_operational_identity_does_not_resolve_official_document(self):
        with self.assertRaises(OperationalError) as caught:
            ProfileResolver().resolve_video_component(
                OperationalProfileKey(
                    ProfileComponent.VIDEO,
                    "instagram",
                    "wrong_opaque_identity",
                )
            )

        self.assertEqual("CONFIG", caught.exception.context.family)
        self.assertEqual(
            "wrong_opaque_identity",
            caught.exception.context.technical_metadata["profile_id"],
        )

    def test_custom_declarative_savevideo_document_resolves_without_filename_convention(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document("custom_opaque_identity", "test_platform")
            document["video_component"]["delivery"] = {
                "intermediate_output": "savevideo_h264",
            }
            expected = self._write_document(
                root,
                "test_platform",
                "arbitrary-custom-name.json",
                document,
            )
            key = OperationalProfileKey(
                ProfileComponent.VIDEO,
                "test_platform",
                "custom_opaque_identity",
            )

            resolved = ProfileResolver(root).resolve_video_component(key)
            validated = ProfileResolver(root)._validate_declarative_video_component_document(
                document,
                expected,
                key,
            )

        self.assertEqual(expected, resolved)
        self.assertEqual(
            WanIntermediateOutput.SAVEVIDEO_H264,
            validated.delivery.intermediate_output,
        )


if __name__ == "__main__":
    unittest.main()
