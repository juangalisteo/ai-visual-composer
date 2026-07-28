import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from app.core.prompt_engine import PromptEngine
from app.modules.images.image_builder import ImageBuilder
from app.modules.storyboard.storyboard_composer import StoryboardComposer
from app.modules.storyboard.storyboard_validator import StoryboardValidator


class StoryboardVisualTruthSourceTest(unittest.TestCase):

    def test_storyboard_prompt_requests_visual_truth_2_contract(self):
        prompt = PromptEngine().build_storyboard_prompt(
            scenes=[
                {
                    "scene": 1,
                    "text": "Una persona entrega una llave antigua.",
                }
            ],
            profile={
                "tone": "modo_conciencia",
                "platform": "instagram",
                "format": "vertical",
            },
        )

        self.assertIn(
            "Visual Truth 2.0",
            prompt,
        )
        self.assertIn(
            '"visible_subject"',
            prompt,
        )
        self.assertIn(
            '"filmable_interpretation"',
            prompt,
        )
        self.assertIn(
            '"visual_idea"',
            prompt,
        )
        self.assertIn(
            "compatibilidad temporal",
            prompt,
        )

    def test_validator_accepts_visual_truth_and_derives_legacy_visual_idea(self):
        validated = StoryboardValidator().validate(
            visual_scenes=[
                {
                    "scene": "1",
                    "visible_subject": "persona adulta con abrigo oscuro",
                    "visible_action": "entrega una llave antigua",
                    "visible_environment": "habitacion silenciosa",
                    "time_context": "noche",
                    "key_objects": [
                        "llave antigua",
                        "",
                        None,
                    ],
                    "spatial_relationships": (
                        "la llave queda entre ambas manos",
                    ),
                    "continuity_links": [
                        "misma llave de la escena anterior",
                    ],
                    "abstract_source": "confianza transferida",
                    "filmable_interpretation": (
                        "una llave antigua cambia de manos en silencio"
                    ),
                    "visual_constraints": "sin texto legible",
                    "visual_truth_status": " structured ",
                }
            ],
            expected_scene_count=1,
        )

        self.assertEqual(
            "una llave antigua cambia de manos en silencio",
            validated[0]["visual_idea"],
        )
        self.assertEqual(
            (
                "llave antigua",
            ),
            validated[0]["key_objects"],
        )
        self.assertEqual(
            (
                "sin texto legible",
            ),
            validated[0]["visual_constraints"],
        )
        self.assertEqual(
            "structured",
            validated[0]["visual_truth_status"],
        )

    def test_validator_rejects_scenes_without_visual_truth(self):
        with self.assertRaisesRegex(
            ValueError,
            "visible_subject",
        ):
            StoryboardValidator().validate(
                visual_scenes=[
                    {
                        "scene": 1,
                        "visual_idea": "legacy only idea",
                    }
                ],
                expected_scene_count=1,
            )

    def test_composer_preserves_visual_truth_and_keeps_compatibility_field(self):
        scenes = StoryboardComposer().compose(
            base_scenes=[
                {
                    "scene": 1,
                    "text": "Una persona entrega una llave.",
                }
            ],
            visual_scenes=[
                {
                    "scene": 1,
                    "visible_subject": "persona adulta",
                    "visible_action": "entrega una llave antigua",
                    "visible_environment": "biblioteca privada",
                    "time_context": "amanecer",
                    "key_objects": (
                        "llave antigua",
                    ),
                    "spatial_relationships": (
                        "las manos se encuentran sobre la mesa",
                    ),
                    "continuity_links": (
                        "misma persona",
                    ),
                    "abstract_source": "umbral de responsabilidad",
                    "filmable_interpretation": (
                        "una llave antigua se entrega con solemnidad"
                    ),
                    "visual_constraints": (
                        "sin texto legible",
                    ),
                    "visual_truth_status": "structured",
                    "visual_idea": (
                        "una llave antigua se entrega con solemnidad"
                    ),
                }
            ],
            scene_duration=3.25,
        )

        self.assertEqual(
            "persona adulta",
            scenes[0]["visible_subject"],
        )
        self.assertEqual(
            "biblioteca privada",
            scenes[0]["visible_environment"],
        )
        self.assertEqual(
            (
                "llave antigua",
            ),
            scenes[0]["key_objects"],
        )
        self.assertEqual(
            "una llave antigua se entrega con solemnidad",
            scenes[0]["visual_idea"],
        )

    def test_image_builder_accepts_visual_truth_without_legacy_visual_idea(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            storyboard_path = root / "storyboard.json"
            manifest_path = root / "images_manifest.json"
            output_dir = root / "images"
            workflow_path = root / "workflow.json"

            storyboard_path.write_text(
                json.dumps(
                    [
                        {
                            "scene": 1,
                            "text": "Una persona entrega una llave.",
                            "duration": 3.0,
                            "visible_subject": "persona adulta",
                            "visible_action": "entrega una llave antigua",
                            "visible_environment": "biblioteca privada",
                            "time_context": "noche",
                            "key_objects": [
                                "llave antigua",
                            ],
                            "spatial_relationships": [
                                "la llave queda entre ambas manos",
                            ],
                            "continuity_links": [
                                "misma llave",
                            ],
                            "abstract_source": "confianza transferida",
                            "filmable_interpretation": (
                                "una llave antigua cambia de manos en silencio"
                            ),
                            "visual_constraints": [
                                "sin texto legible",
                            ],
                            "visual_truth_status": "structured",
                        }
                    ]
                ),
                encoding="utf-8"
            )
            workflow_path.write_text(
                json.dumps(
                    {}
                ),
                encoding="utf-8"
            )

            with self._patched_environment(
                manifest_path=manifest_path,
                profile={
                    "format": "horizontal",
                    "video_style": {
                        "width": 640,
                        "height": 360,
                    },
                },
            ):
                builder = ImageBuilder(
                    workflow_path=workflow_path
                )

                with patch.object(
                    ImageBuilder,
                    "_generate_image",
                    side_effect=self._fake_generate_image,
                ):
                    builder.build(
                        storyboard_path=storyboard_path,
                        output_dir=output_dir,
                    )

            manifest = json.loads(
                manifest_path.read_text(
                    encoding="utf-8"
                )
            )

        self.assertIn(
            "una llave antigua cambia de manos en silencio",
            manifest[0]["prompt"],
        )
        self.assertIn(
            "biblioteca privada",
            manifest[0]["prompt"],
        )

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
        image_path.write_bytes(
            b"fake image"
        )
        return image_path

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
