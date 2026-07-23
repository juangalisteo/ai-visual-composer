import inspect
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.cinematic_direction import create_cinematic_direction_set
from app.domain import StoryboardScene
from app.modules.images.image_builder import ImageBuilder
from app.photography_direction import PhotographyDirection
from app.prompt_translation import BackendPrompt, BackendPromptTrace
from app.visual_direction import EffectiveVisualBrief


class FailingCinematicRuntime:

    def resolve(
        self,
        effective_visual_brief
    ):
        raise AssertionError(
            "cinematic runtime should be disabled"
        )

    def translate(
        self,
        *args,
        **kwargs
    ):
        raise AssertionError(
            "prompt translator should be disabled"
        )


class RecordingCinematicOrchestrator:

    def __init__(
        self
    ):
        self.effective_visual_briefs = []
        self.direction_set = create_cinematic_direction_set(
            photography=PhotographyDirection(
                dominant_photographic_language="observational intimacy",
                fingerprint="photography-fingerprint"
            )
        )

    def resolve(
        self,
        effective_visual_brief
    ):
        self.effective_visual_briefs.append(
            effective_visual_brief
        )
        return self.direction_set


class RecordingPromptTranslator:

    def __init__(
        self
    ):
        self.calls = []

    def translate(
        self,
        effective_visual_brief,
        cinematic_direction_set=None,
        cinematic_enabled=False
    ):
        self.calls.append(
            (
                effective_visual_brief,
                cinematic_direction_set,
                cinematic_enabled
            )
        )
        return BackendPrompt(
            instructions=(),
            trace=BackendPromptTrace(
                source_visual_brief_fingerprint=(
                    effective_visual_brief.fingerprint
                )
            ),
            source_id=effective_visual_brief.source_id,
            source_version=effective_visual_brief.source_version,
            fingerprint="backend-prompt-fingerprint"
        )


class ImageBuilderCinematicRuntimeTest(unittest.TestCase):

    def test_legacy_build_does_not_invoke_cinematic_runtime_by_default(self):
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
                manifest_path=manifest_path
            ):
                builder = ImageBuilder(
                    workflow_path=workflow_path,
                    cinematic_orchestrator=FailingCinematicRuntime(),
                    prompt_translator=FailingCinematicRuntime()
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
                    manifest[0]
                )
            )
            self.assertIn(
                "A quiet dawn over a valley",
                manifest[0]["prompt"]
            )

    def test_cinematic_flag_invokes_orchestrator_and_prompt_translator(self):
        orchestrator = RecordingCinematicOrchestrator()
        translator = RecordingPromptTranslator()

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
                manifest_path=manifest_path
            ):
                builder = ImageBuilder(
                    workflow_path=workflow_path,
                    cinematic_orchestrator=orchestrator,
                    prompt_translator=translator
                )

                with patch.object(
                    ImageBuilder,
                    "_generate_image",
                    side_effect=self._fake_generate_image
                ):
                    builder.build(
                        storyboard_path=storyboard_path,
                        output_dir=output_dir,
                        cinematic_enabled=True
                    )

        self.assertEqual(
            1,
            len(
                orchestrator.effective_visual_briefs
            )
        )
        self.assertEqual(
            1,
            len(
                translator.calls
            )
        )

        effective_visual_brief, direction_set, enabled = (
            translator.calls[0]
        )

        self.assertIsInstance(
            effective_visual_brief,
            EffectiveVisualBrief
        )
        self.assertIs(
            direction_set,
            orchestrator.direction_set
        )
        self.assertTrue(
            enabled
        )
        self.assertEqual(
            "A quiet dawn over a valley",
            effective_visual_brief.visual_brief.visible_content
        )
        self.assertEqual(
            "backend-prompt-fingerprint",
            builder._build_cinematic_runtime_metadata(
                storyboard_scene=StoryboardScene(
                    scene_number=1,
                    text="La escena conserva su texto."
                ),
                visual_idea="A quiet dawn over a valley",
                cinematic_enabled=True
            )["backend_prompt_fingerprint"]
        )

    def test_runtime_effective_visual_brief_fingerprint_is_deterministic(self):
        builder = ImageBuilder()
        storyboard_scene = StoryboardScene(
            scene_number=1,
            text="La escena conserva su texto."
        )

        first = builder._build_runtime_effective_visual_brief(
            storyboard_scene=storyboard_scene,
            visual_idea="A quiet dawn over a valley"
        )
        second = builder._build_runtime_effective_visual_brief(
            storyboard_scene=storyboard_scene,
            visual_idea="A quiet dawn over a valley"
        )

        self.assertEqual(
            first,
            second
        )
        self.assertEqual(
            first.fingerprint,
            second.fingerprint
        )
        self.assertTrue(
            first.fingerprint
        )

    def test_runtime_knows_only_cinematic_orchestrator_not_individual_directions(self):
        source = inspect.getsource(
            ImageBuilder
        )

        self.assertIn(
            "CinematicDirectionOrchestrator",
            source
        )

        for forbidden in (
            "PhotographyDirector",
            "LightingDirector",
            "CompositionDirector",
            "ColorDirector",
            "MovementDirector",
            "ContinuityDirector",
        ):
            with self.subTest(
                forbidden=forbidden
            ):
                self.assertNotIn(
                    forbidden,
                    source
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
                        "text": "La escena conserva su texto.",
                        "visual_idea": "A quiet dawn over a valley",
                        "duration": 3
                    }
                ],
                ensure_ascii=False
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
            "{}",
            encoding="utf-8"
        )
        return workflow_path

    def _patched_environment(
        self,
        manifest_path
    ):
        project = SimpleNamespace(
            images_manifest_path=lambda: manifest_path
        )
        config = SimpleNamespace(
            get_profile_config=lambda: {
                "format": "horizontal",
                "video_style": {
                    "width": 640,
                    "height": 360
                },
                "visual_director": {
                    "enabled": False
                }
            }
        )

        return patch.multiple(
            "app.modules.images.image_builder",
            ProjectManager=lambda: project,
            ConfigManager=lambda: config
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
        image_path.write_text(
            f"{width}x{height}\n{prompt}",
            encoding="utf-8"
        )
        return image_path


if __name__ == "__main__":
    unittest.main()
