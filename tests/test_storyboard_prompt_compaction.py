import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.core.prompt_engine import PromptEngine
from app.modules.storyboard.storyboard_builder import StoryboardBuilder
from app.modules.storyboard.storyboard_validator import StoryboardValidator
from app.providers.ollama_provider import (
    OllamaProviderResult,
    OllamaRequestPolicy,
    OllamaResponseMetadata,
)
from app.shared.config_manager import ConfigManager
from app.shared.prompt_metrics import estimate_conservative_tokens


class StoryboardPromptCompactionTest(unittest.TestCase):

    REQUIRED_FIELDS = (
        '"scene"',
        '"visible_subject"',
        '"visible_action"',
        '"visible_environment"',
        '"time_context"',
        '"key_objects"',
        '"spatial_relationships"',
        '"continuity_links"',
        '"abstract_source"',
        '"filmable_interpretation"',
        '"visual_constraints"',
        '"visual_truth_status"',
    )

    def test_uses_one_template_for_nine_scenes_and_preserves_contract(self):
        prompt = PromptEngine().build_storyboard_prompt(
            scenes=self._base_scenes(9),
            profile=self._profile(),
        )

        example = prompt.split("FORMATO EXACTO:\n\n", 1)[1]

        self.assertEqual(1, example.count('"scene"'))
        self.assertIn("Devuelve exactamente 9 objetos.", prompt)
        self.assertIn(
            'Numera los objetos consecutivamente con "scene" '
            "desde 1 hasta 9.",
            prompt,
        )
        self.assertIn(
            "La respuesta completa debe ser una única lista JSON.",
            prompt,
        )
        for field in self.REQUIRED_FIELDS:
            self.assertIn(field, example)

    def test_template_size_is_independent_of_scene_count(self):
        engine = PromptEngine()
        one_scene_prompt = engine.build_storyboard_prompt(
            scenes=self._base_scenes(1),
            profile=self._profile(),
        )
        nine_scene_prompt = engine.build_storyboard_prompt(
            scenes=self._base_scenes(9),
            profile=self._profile(),
        )

        one_scene_example = one_scene_prompt.split(
            "FORMATO EXACTO:\n\n",
            1,
        )[1]
        nine_scene_example = nine_scene_prompt.split(
            "FORMATO EXACTO:\n\n",
            1,
        )[1]

        self.assertEqual(one_scene_example, nine_scene_example)
        self.assertEqual(
            estimate_conservative_tokens(one_scene_example),
            estimate_conservative_tokens(nine_scene_example),
        )

    def test_builder_with_fake_provider_preserves_multi_scene_contract(self):
        response = json.dumps(
            [
                self._visual_scene(1),
                self._visual_scene(2),
            ]
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            script_path = root / "guion.txt"
            audio_path = root / "audio.mp3"
            output_path = root / "storyboard.json"
            script_path.write_text("Guion de prueba.", encoding="utf-8")
            audio_path.write_bytes(b"audio")
            project = SimpleNamespace(
                final_audio_path=lambda: audio_path,
                audio_path=lambda: audio_path,
            )

            with patch(
                "app.modules.storyboard.storyboard_builder.ProjectManager",
                return_value=project,
            ), patch.object(
                ConfigManager,
                "get_ai_config",
                return_value={"model": "fake-storyboard-model"},
            ), patch.object(
                ConfigManager,
                "get_profile_config",
                return_value=self._profile(),
            ), patch(
                "app.modules.storyboard.storyboard_builder.MediaProbe.get_duration",
                return_value=20.0,
            ), patch(
                "app.modules.storyboard.storyboard_builder.SceneSplitter.split",
                return_value=["Primera escena.", "Segunda escena."],
            ), patch(
                "app.modules.storyboard.storyboard_ai_builder.OllamaProvider",
            ) as provider:
                provider.return_value.generate_result.return_value = (
                    OllamaProviderResult(
                        content=response,
                        metadata=OllamaResponseMetadata(
                            requested_model="fake-storyboard-model",
                            response_model=None,
                            created_at=None,
                            policy=OllamaRequestPolicy(),
                            done=None,
                            done_reason=None,
                            prompt_length=0,
                            content_length=len(response),
                            prompt_sha256="prompt-hash",
                            content_sha256="content-hash",
                            prompt_eval_count=None,
                            eval_count=None,
                            total_duration=None,
                            load_duration=None,
                            prompt_eval_duration=None,
                            eval_duration=None,
                            thinking_length=None,
                            thinking_sha256=None,
                        ),
                    )
                )

                result = StoryboardBuilder().build(
                    script_path=script_path,
                    output_path=output_path,
                    target_scene_duration=10.0,
                )

                generated_scene_numbers = [
                    scene["scene"]
                    for scene in json.loads(
                        output_path.read_text(encoding="utf-8")
                    )
                ]

        self.assertEqual(output_path, result)
        self.assertEqual([1, 2], generated_scene_numbers)
        provider.return_value.generate_result.assert_called_once()

    def test_validator_preserves_required_count_and_consecutive_numbers(self):
        validated = StoryboardValidator().validate(
            visual_scenes=[
                self._visual_scene(1),
                self._visual_scene(2),
            ],
            expected_scene_count=2,
        )

        self.assertEqual([1, 2], [scene["scene"] for scene in validated])

        with self.assertRaisesRegex(ValueError, "numeración"):
            StoryboardValidator().validate(
                visual_scenes=[
                    self._visual_scene(1),
                    self._visual_scene(3),
                ],
                expected_scene_count=2,
            )

    def _base_scenes(self, count):
        return [
            {
                "scene": scene_number,
                "text": f"Texto base de la escena {scene_number}.",
            }
            for scene_number in range(1, count + 1)
        ]

    def _profile(self):
        return {
            "tone": "modo_conciencia",
            "format": "vertical",
            "video_style": {
                "storyboard": {
                    "seconds_per_image": 10,
                }
            },
        }

    def _visual_scene(self, number):
        return {
            "scene": number,
            "visible_subject": f"sujeto {number}",
            "visible_action": f"accion {number}",
            "visible_environment": f"entorno {number}",
            "time_context": "dia",
            "key_objects": [f"objeto {number}"],
            "spatial_relationships": ["relacion espacial"],
            "continuity_links": ["continuidad"],
            "abstract_source": "idea",
            "filmable_interpretation": f"escena filmable {number}",
            "visual_constraints": ["sin texto legible"],
            "visual_truth_status": "structured",
        }


if __name__ == "__main__":
    unittest.main()
