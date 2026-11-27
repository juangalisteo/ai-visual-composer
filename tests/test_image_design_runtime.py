import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core import start
from app.core.execution_request import (
    ApplicationExecutionRequest,
    DesignExecutionRequest,
)
from app.managers.project_manager import ProjectManager
from app.modules.design import DesignExecutionCoordinator
from app.modules.images import ImageDesignPreparationService
from app.shared.profile_identity import (
    OperationalProfileKey,
    ProfileComponent,
)


class FakeVisualDesignInterpreter:

    def interpret(
        self,
        text
    ):
        normalized = str(
            text
        ).strip()
        return {
            "scene": 1,
            "visible_subject": "ciudad futurista",
            "visible_action": "la lluvia cae sobre la ciudad",
            "visible_environment": "avenida futurista nocturna",
            "time_context": "noche",
            "key_objects": (
                "neones",
                "lluvia",
            ),
            "spatial_relationships": (),
            "continuity_links": (),
            "abstract_source": normalized,
            "filmable_interpretation": normalized,
            "visual_constraints": (),
            "visual_truth_status": (
                "manual_design_interpreted"
            )
        }


class FakeImageBuilder:

    def __init__(self):
        self.received_scenes = None

    def build(
        self,
        storyboard_path=None,
        output_dir=None
    ):
        storyboard_path = Path(
            storyboard_path
        )
        output_dir = Path(
            output_dir
        )
        self.received_scenes = json.loads(
            storyboard_path.read_text(
                encoding="utf-8"
            )
        )
        output_dir.mkdir(
            parents=True,
            exist_ok=True
        )
        image_path = (
            output_dir
            / "scene_001.png"
        )
        image_path.write_bytes(
            b"image"
        )
        manifest_path = (
            output_dir
            / "images_manifest.json"
        )
        manifest_path.write_text(
            json.dumps(
                [
                    {
                        "scene": 1,
                        "image": str(image_path),
                        "width": 1080,
                        "height": 1920,
                        "duration": None
                    }
                ],
                indent=4
            ),
            encoding="utf-8"
        )
        return manifest_path


class ImageDesignRuntimeTest(unittest.TestCase):

    def test_start_routes_design_image_before_narrative_pipeline(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            previous_cwd = Path.cwd()
            fake_image_builder = FakeImageBuilder()

            try:
                os.chdir(
                    root
                )
                input_dir = root / "input"
                input_dir.mkdir()
                (
                    input_dir
                    / "guion_imagen.txt"
                ).write_text(
                    "Diseno visual directo desde start.",
                    encoding="utf-8"
                )

                operational_profile_key = OperationalProfileKey(
                    ProfileComponent.IMAGEN,
                    "test_format",
                    "test_profile",
                )
                request = ApplicationExecutionRequest(
                    project_name="design start",
                    overwrite_project=False,
                    operational_profile_key=operational_profile_key,
                    subtitle_profile_key=None,
                    route=DesignExecutionRequest(mode="design_image"),
                )
                with patch(
                    "app.core.start.ConfigManager"
                ) as config_manager, patch(
                    "app.modules.standard.execution_coordinator.ScriptOperation",
                    side_effect=AssertionError(
                        "ScriptOperation must not run before design route"
                    )
                ), patch(
                    "app.modules.design.execution_coordinator.ImageDesignPreparationService",
                    return_value=ImageDesignPreparationService(
                        visual_interpreter=FakeVisualDesignInterpreter()
                    )
                ), patch(
                    "app.modules.design.execution_coordinator.ImageBuilder",
                    return_value=fake_image_builder
                ), patch(
                    "app.shared.media_probe.MediaProbe.get_duration",
                    return_value=None
                ):
                    config_manager.return_value.get_profile_config.return_value = None
                    config_manager.return_value.get_ai_config.return_value = None
                    result = start.run_application(request=request)

                config_manager.assert_called_once_with(
                    operational_profile_key=operational_profile_key
                )
                self.assertEqual(
                    "images_manifest.json",
                    Path(result).name
                )
                self.assertIn(
                    "design start",
                    Path(result).parts
                )
                self.assertEqual(
                    1,
                    len(fake_image_builder.received_scenes)
                )
            finally:
                os.chdir(
                    previous_cwd
                )

    def test_design_image_uses_guion_imagen_and_generates_one_manifest_entry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            previous_cwd = Path.cwd()
            fake_image_builder = FakeImageBuilder()

            try:
                os.chdir(
                    root
                )
                input_dir = root / "input"
                input_dir.mkdir()
                (
                    input_dir
                    / "tema.txt"
                ).write_text(
                    "tema que no debe usarse",
                    encoding="utf-8"
                )
                (
                    input_dir
                    / "guion.txt"
                ).write_text(
                    "guion narrativo que no debe usarse",
                    encoding="utf-8"
                )
                (
                    input_dir
                    / "guion_imagen.txt"
                ).write_text(
                    "Diseno visual manual para una sola imagen.",
                    encoding="utf-8"
                )

                with patch(
                    "app.modules.script.operation.ScriptOperation.execute",
                    side_effect=AssertionError(
                        "ScriptOperation must not run"
                    )
                ), patch(
                    "app.modules.script.operation.ScriptPreparationService",
                    side_effect=AssertionError(
                        "ScriptPreparationService must not run"
                    )
                ), patch(
                    "app.modules.audio.voice_builder.VoiceBuilder.build",
                    side_effect=AssertionError(
                        "VoiceBuilder must not run"
                    )
                ), patch(
                    "app.modules.audio.music_selector.MusicSelector.select",
                    side_effect=AssertionError(
                        "MusicSelector must not run"
                    )
                ), patch(
                    "app.modules.audio.audio_mixer.AudioMixer.build",
                    side_effect=AssertionError(
                        "AudioMixer must not run"
                    )
                ), patch(
                    "app.modules.subtitles.io.subtitle_builder.SubtitleBuilder.build",
                    side_effect=AssertionError(
                        "SubtitleBuilder must not run"
                    )
                ), patch(
                    "app.modules.subtitles.pipeline.srt_optimizer.SrtOptimizer.optimize",
                    side_effect=AssertionError(
                        "SrtOptimizer must not run"
                    )
                ), patch(
                    "app.modules.storyboard.storyboard_builder.StoryboardBuilder.build",
                    side_effect=AssertionError(
                        "StoryboardBuilder must not run"
                    )
                ), patch(
                    "app.modules.video.video_builder.VideoBuilder.build",
                    side_effect=AssertionError(
                        "VideoBuilder must not run"
                    )
                ), patch(
                    "app.shared.media_probe.MediaProbe.get_duration",
                    return_value=None
                ):
                    result = DesignExecutionCoordinator().run_image(
                        project=ProjectManager(project_name="design image"),
                        preparation_service=ImageDesignPreparationService(
                            visual_interpreter=(
                                FakeVisualDesignInterpreter()
                            )
                        ),
                        image_builder=fake_image_builder
                    )

                manifest = json.loads(
                    Path(result).read_text(
                        encoding="utf-8"
                    )
                )
                self.assertEqual(
                    1,
                    len(manifest)
                )
                self.assertEqual(
                    "scene_001.png",
                    Path(manifest[0]["image"]).name
                )
                self.assertEqual(
                    1,
                    len(fake_image_builder.received_scenes)
                )
                self.assertEqual(
                    "Diseno visual manual para una sola imagen.",
                    fake_image_builder.received_scenes[0][
                        "filmable_interpretation"
                    ]
                )
                self.assertFalse(
                    (
                        root
                        / "output"
                        / "design image"
                        / "audio"
                    ).exists()
                )
                self.assertFalse(
                    (
                        root
                        / "output"
                        / "design image"
                        / "subtitles"
                    ).exists()
                )
                self.assertFalse(
                    (
                        root
                        / "output"
                        / "design image"
                        / "video"
                    ).exists()
                )
            finally:
                os.chdir(
                    previous_cwd
                )

    def test_design_image_rejects_more_than_one_scene(self):
        with self.assertRaises(
            ValueError
        ):
            DesignExecutionCoordinator.ensure_single_design_scene(
                [
                    {
                        "scene": 1
                    },
                    {
                        "scene": 2
                    }
                ]
            )

    def test_design_uses_target_image_profile_dimensions(self):
        cases = (
            (
                "config/profiles/imagen/vertical/"
                "perfil_imagen_vertical.json",
                1080,
                1920
            ),
            (
                "config/profiles/imagen/horizontal/"
                "perfil_imagen_horizontal.json",
                1920,
                1080
            ),
        )

        for profile_path, expected_width, expected_height in cases:
            with self.subTest(
                profile_path=profile_path
            ):
                profile = json.loads(
                    Path(profile_path).read_text(
                        encoding="utf-8"
                    )
                )

                self.assertEqual(
                    expected_width,
                    profile["video_style"]["width"]
                )
                self.assertEqual(
                    expected_height,
                    profile["video_style"]["height"]
                )


if __name__ == "__main__":
    unittest.main()
