import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from app.modules.images.image_builder import ImageBuilder
from app.prompt_translation import PromptBudgetPolicy, PromptTranslator


class ImageBuilderRuntimePromptTest(unittest.TestCase):

    def test_build_uses_single_cinematic_runtime_without_changing_manifest_contract(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            storyboard_path = self._write_storyboard(
                root
            )
            manifest_path = root / "images_manifest.json"
            output_dir = root / "images"
            workflow_path = self._write_workflow(
                root
            )

            with self._patched_environment(
                manifest_path=manifest_path,
                profile={
                    "format": "horizontal",
                    "video_style": {
                        "width": 640,
                        "height": 360
                    },
                    "image_validation": {
                        "enabled": False
                    }
                }
            ):
                builder = ImageBuilder(
                    workflow_path=workflow_path,
                    prompt_translator=self._wide_encoder_prompt_translator(),
                )

                with patch.object(
                    ImageBuilder,
                    "_generate_image",
                    side_effect=self._fake_generate_image
                ) as generate_image:
                    result_path = builder.build(
                        storyboard_path=storyboard_path,
                        output_dir=output_dir
                    )

            self.assertEqual(
                manifest_path,
                result_path
            )
            self.assertEqual(
                2,
                generate_image.call_count
            )

            manifest = json.loads(
                manifest_path.read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                2,
                len(manifest)
            )
            self.assertEqual(
                {
                    "scene",
                    "prompt",
                    "positive_prompt",
                    "negative_prompt",
                    "visual_director",
                    "image",
                    "width",
                    "height",
                    "duration"
                },
                set(
                    manifest[0].keys()
                )
            )
            self.assertIn(
                "wide valley under first morning light",
                manifest[0]["prompt"]
            )
            self.assertIn(
                "wide horizontal 16:9",
                manifest[0]["prompt"]
            )
            self.assertIn(
                "professional photorealism",
                manifest[0]["prompt"]
            )
            self.assertIn(
                "No people or faces unless explicitly described",
                manifest[0]["prompt"]
            )
            self.assertFalse(
                manifest[0]["visual_director"]["fallback"]
            )
            self.assertEqual(
                {},
                manifest[0]["visual_director"]["directives"]
            )

    def test_vertical_profile_adds_vertical_runtime_guidance(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            storyboard_path = self._write_storyboard(
                root
            )
            manifest_path = root / "images_manifest.json"
            output_dir = root / "images"
            workflow_path = self._write_workflow(
                root
            )

            with self._patched_environment(
                manifest_path=manifest_path,
                profile={
                    "format": "vertical",
                    "video_style": {
                        "width": 360,
                        "height": 640
                    },
                    "image_validation": {
                        "enabled": False
                    }
                }
            ):
                builder = ImageBuilder(
                    workflow_path=workflow_path,
                    prompt_translator=self._wide_encoder_prompt_translator(),
                )

                with patch.object(
                    ImageBuilder,
                    "_generate_image",
                    side_effect=self._fake_generate_image
                ):
                    builder.build(
                        storyboard_path=storyboard_path,
                        output_dir=output_dir
                    )

            manifest = json.loads(
                manifest_path.read_text(
                    encoding="utf-8"
                )
            )

            self.assertIn(
                "vertical 9:16",
                manifest[0]["prompt"]
            )

    def test_explicit_profile_bypasses_global_profile_resolution(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            storyboard_path = self._write_storyboard(
                root
            )
            manifest_path = root / "images_manifest.json"
            output_dir = root / "images"
            workflow_path = self._write_workflow(
                root
            )
            profile = {
                "format": "horizontal",
                "video_style": {
                    "width": 640,
                    "height": 360
                },
                "image_validation": {
                    "enabled": False
                }
            }

            with patch(
                "app.managers.project_manager."
                "ProjectManager.images_manifest_path",
                return_value=manifest_path
            ), patch(
                "app.modules.images.image_builder.ConfigManager",
                side_effect=AssertionError(
                    "Explicit profile must bypass ConfigManager"
                )
            ):
                builder = ImageBuilder(
                    workflow_path=workflow_path,
                    profile=profile,
                    prompt_translator=self._wide_encoder_prompt_translator(),
                )

                with patch.object(
                    ImageBuilder,
                    "_generate_image",
                    side_effect=self._fake_generate_image
                ):
                    result_path = builder.build(
                        storyboard_path=storyboard_path,
                        output_dir=output_dir
                    )

            self.assertEqual(
                manifest_path,
                result_path
            )
            manifest = json.loads(
                manifest_path.read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                640,
                manifest[0]["width"]
            )
            self.assertEqual(
                360,
                manifest[0]["height"]
            )

    def test_official_profiles_remain_valid_for_image_dimensions(self):
        builder = ImageBuilder()

        for profile_path in (
            Path(
                "config/profiles/imagen/horizontal/"
                "perfil_imagen_horizontal.json"
            ),
            Path(
                "config/profiles/imagen/vertical/"
                "perfil_imagen_vertical.json"
            ),
        ):
            with self.subTest(
                profile_path=profile_path
            ):
                profile = json.loads(
                    profile_path.read_text(
                        encoding="utf-8"
                    )
                )

                width, height = (
                    builder._get_image_dimensions(
                        profile
                    )
                )

                self.assertGreater(
                    width,
                    0
                )
                self.assertGreater(
                    height,
                    0
                )

    def _write_storyboard(
        self,
        root
    ):
        storyboard_path = root / "storyboard.json"
        storyboard_path.write_text(
            json.dumps(
                [
                    {
                        "scene": 1,
                        "text": (
                            "La luz aparece sobre el valle "
                            "y transforma la atmosfera."
                        ),
                        "visible_subject": (
                            "wide valley under first morning light"
                        ),
                        "visible_action": (
                            "light spreads across the mist"
                        ),
                        "visible_environment": (
                            "quiet mountain valley"
                        ),
                        "time_context": "dawn",
                        "key_objects": (
                            "low mist",
                            "distant ridge",
                        ),
                        "spatial_relationships": (
                            "mist sits below the ridge",
                        ),
                        "continuity_links": (),
                        "abstract_source": "transformation begins",
                        "filmable_interpretation": (
                            "A quiet dawn over a valley"
                        ),
                        "visual_constraints": (
                            "no readable text",
                        ),
                        "visual_truth_status": "structured",
                        "duration": 3.5
                    },
                    {
                        "scene": 2,
                        "text": (
                            "La luz se abre en el horizonte."
                        ),
                        "visible_subject": (
                            "bright horizon line"
                        ),
                        "visible_action": (
                            "soft light opens across the sky"
                        ),
                        "visible_environment": (
                            "open landscape horizon"
                        ),
                        "time_context": "early morning",
                        "key_objects": (
                            "horizon",
                        ),
                        "spatial_relationships": (
                            "light rises behind the landscape",
                        ),
                        "continuity_links": (
                            "same morning light",
                        ),
                        "abstract_source": "expansion",
                        "filmable_interpretation": (
                            "A soft light opening on the horizon"
                        ),
                        "visual_constraints": (
                            "no readable text",
                        ),
                        "visual_truth_status": "structured",
                        "duration": 4.0
                    }
                ]
            ),
            encoding="utf-8"
        )
        return storyboard_path

    def _write_workflow(
        self,
        root
    ):
        workflow_path = root / "workflow.json"
        workflow_path.write_text(
            json.dumps(
                {}
            ),
            encoding="utf-8"
        )
        return workflow_path

    def _fake_generate_image(
        self,
        prompt,
        scene_number,
        output_dir,
        width,
        height
    ):
        output_dir.mkdir(
            parents=True,
            exist_ok=True
        )
        image_path = output_dir / f"scene_{scene_number:03d}.png"
        from PIL import Image

        Image.new("RGB", (width, height)).save(image_path)
        return image_path

    def _wide_encoder_prompt_translator(
        self,
    ):
        return PromptTranslator(
            budget_policy=PromptBudgetPolicy(
                encoder_token_limit=10_000,
            )
        )

    @contextmanager
    def _patched_environment(
        self,
        manifest_path,
        profile
    ):
        with patch(
            "app.managers.project_manager.ProjectManager.images_manifest_path",
            return_value=manifest_path
        ), patch(
            "app.shared.config_manager.ConfigManager.get_profile_config",
            return_value=profile
        ):
            yield


if __name__ == "__main__":
    unittest.main()
