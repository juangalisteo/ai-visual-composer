import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core import start
from app.modules.design import DesignExecutionCoordinator
from app.modules.video_component import (
    VideoClipGenerationResult,
    VideoDesignPreparationService,
    VideoDesignVisualTruthAdapter,
)
from app.modules.visual_design import VisualDesignInterpreter
from app.shared.operational_error import OperationalError
from app.shared.profile_identity import (
    OperationalProfileKey,
    ProfileComponent,
)
from app.shared.profile_resolver import ProfileResolver


class FakeImageBuilder:

    def __init__(
        self
    ):
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


class FakeVideoComponentBuilder:

    def __init__(
        self
    ):
        self.calls = []

    def generate_clip(
        self,
        source_path,
        output_dir,
        output_name=None,
        storyboard_scene=None,
        **overrides
    ):
        output_dir = Path(
            output_dir
        )
        output_dir.mkdir(
            parents=True,
            exist_ok=True
        )
        output_clip = (
            output_dir
            / (
                output_name
                or "scene_001.mp4"
            )
        )
        output_clip.write_bytes(
            b"video"
        )
        call = {
            "source_path": Path(
                source_path
            ),
            "output_dir": output_dir,
            "output_name": output_name,
            "storyboard_scene": storyboard_scene,
            "overrides": overrides,
        }
        self.calls.append(
            call
        )
        return VideoClipGenerationResult(
            source_image=source_path,
            output_clip=output_clip,
            manifest_path=None,
            prompt_id="fake-prompt",
            backend="FakeVideo",
            model="fake-model",
            workflow="fake-workflow",
            seed=overrides.get(
                "seed",
                123
            ),
            frames=overrides.get(
                "frames",
                17
            ),
            fps=overrides.get(
                "fps",
                8.0
            ),
            generation_width=overrides.get(
                "generation_width",
                320
            ),
            generation_height=overrides.get(
                "generation_height",
                320
            ),
            steps=overrides.get(
                "steps",
                4
            ),
            cfg=overrides.get(
                "cfg",
                5.0
            ),
            sampler=overrides.get(
                "sampler",
                "uni_pc"
            ),
            scheduler=overrides.get(
                "scheduler",
                "simple"
            ),
            profile_name=overrides.get(
                "profile_name",
                "vertical"
            ),
            duration_seconds=2.0,
            fingerprint="fake-fingerprint"
        )


class FakeVideoDesignInterpreter:

    def interpret(
        self,
        text
    ):
        normalized = str(
            text
        ).strip()
        if "Tesla" in normalized:
            return {
                "scene": 1,
                "visible_subject": "Nikola Tesla sentado",
                "visible_action": (
                    "permanece sentado junto a una bombilla "
                    "que se ilumina suavemente"
                ),
                "visible_environment": "despacho de laboratorio",
                "time_context": "",
                "key_objects": (
                    "bombilla iluminandose",
                ),
                "spatial_relationships": (
                    "Tesla sentado junto a la bombilla",
                ),
                "continuity_links": (),
                "abstract_source": normalized,
                "filmable_interpretation": (
                    "Nikola Tesla sentado en su despacho, "
                    "iluminado por una bombilla que cobra "
                    "intensidad de forma sutil."
                ),
                "visual_constraints": (
                    "preserve seated posture",
                ),
                "visual_truth_status": (
                    "manual_video_design_interpreted"
                )
            }
        return {
            "scene": 1,
            "visible_subject": (
                "joven mago observando un antiguo libro cerrado"
            ),
            "visible_action": (
                "investiga un misterio en silencio"
            ),
            "visible_environment": (
                "biblioteca oscura de un castillo"
            ),
            "time_context": "noche",
            "key_objects": (
                "libro antiguo",
                "varita",
                "lampara tenue",
            ),
            "spatial_relationships": (
                "el sujeto esta sentado frente al libro",
            ),
            "continuity_links": (),
            "abstract_source": normalized,
            "filmable_interpretation": (
                "Un joven mago permanece en una biblioteca "
                "oscura, observando un libro antiguo mientras "
                "una luz tenue sugiere un misterio oculto."
            ),
            "visual_constraints": (
                "avoid readable text",
                "single filmable scene",
            ),
            "visual_truth_status": (
                "manual_video_design_interpreted"
            )
        }


class VideoDesignRuntimeTest(unittest.TestCase):

    def test_design_clip_identity_accepts_non_mp4_extension(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clip = root / "scene_001.mkv"
            clip.write_bytes(b"video")
            manifest_path = root / "video_clips_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    [{"scene": 1, "output_clip": str(clip)}]
                ),
                encoding="utf-8",
            )

            result = DesignExecutionCoordinator.ensure_single_video_design_clip(
                manifest_path,
                scene_clip_identity=start._scene_clip_identity,
            )

        self.assertEqual(clip, result)

    def test_design_clip_identity_rejects_wrong_scene_stem(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clip = root / "scene_002.mkv"
            clip.write_bytes(b"video")
            manifest_path = root / "video_clips_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    [{"scene": 1, "output_clip": str(clip)}]
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "scene_001"):
                DesignExecutionCoordinator.ensure_single_video_design_clip(
                    manifest_path,
                    scene_clip_identity=start._scene_clip_identity,
                )

    def test_video_design_preparation_reads_only_guion_video(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            input_dir = (
                root
                / "input"
            )
            input_dir.mkdir()
            (
                input_dir
                / "tema.txt"
            ).write_text(
                "Tema que no debe usarse.",
                encoding="utf-8"
            )
            (
                input_dir
                / "guion.txt"
            ).write_text(
                "Guion narrativo que no debe usarse.",
                encoding="utf-8"
            )
            (
                input_dir
                / "guion_imagen.txt"
            ).write_text(
                "Diseno de imagen que no debe usarse.",
                encoding="utf-8"
            )
            expected_text = (
                "Nikola Tesla sentado en su despacho "
                "con una bombilla iluminandose."
            )
            (
                input_dir
                / "guion_video.txt"
            ).write_text(
                expected_text,
                encoding="utf-8"
            )

            prepared = VideoDesignPreparationService(
                visual_interpreter=FakeVideoDesignInterpreter()
            ).prepare(
                input_path=(
                    input_dir
                    / "guion_video.txt"
                )
            )

            self.assertEqual(
                expected_text,
                prepared.text
            )
            self.assertEqual(
                input_dir / "guion_video.txt",
                prepared.source_path
            )
            self.assertEqual(
                "manual_design",
                prepared.source
            )
            self.assertEqual(
                "video",
                prepared.target
            )
            self.assertEqual(
                1,
                prepared.expected_clips
            )
            self.assertEqual(
                "Nikola Tesla sentado",
                prepared.visual_truth["visible_subject"]
            )
            self.assertEqual(
                "despacho de laboratorio",
                prepared.visual_truth["visible_environment"]
            )

    def test_video_design_requires_guion_video_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_path = (
                Path(temp_dir)
                / "input"
                / "guion_video.txt"
            )

            with self.assertRaisesRegex(
                FileNotFoundError,
                "guion_video.txt"
            ):
                VideoDesignPreparationService().prepare(
                    input_path=missing_path
                )

    def test_video_design_adapter_generates_single_visual_truth_scene(self):
        prepared = VideoDesignPreparationService(
            visual_interpreter=FakeVideoDesignInterpreter()
        ).prepare(
            input_path=_temporary_video_design_file(
                (
                    "Nikola Tesla sentado en su despacho "
                    "con una bombilla iluminandose."
                )
            )
        )

        scenes = VideoDesignVisualTruthAdapter().adapt(
            prepared
        )

        self.assertEqual(
            1,
            len(scenes)
        )
        self.assertEqual(
            1,
            scenes[0]["scene"]
        )
        self.assertIn(
            "Nikola Tesla",
            scenes[0]["visible_subject"]
        )
        self.assertIn(
            "sentado",
            scenes[0]["visible_action"]
        )
        self.assertIn(
            "despacho",
            scenes[0]["visible_environment"]
        )
        self.assertIn(
            "bombilla",
            " ".join(
                scenes[0]["key_objects"]
            )
        )
        self.assertEqual(
            "manual_video_design_interpreted",
            scenes[0]["visual_truth_status"]
        )

    def test_conceptual_video_design_is_interpreted_as_filmable_scene(self):
        source_text = "Harry Potter y el misterio del principe"
        prepared = VideoDesignPreparationService(
            visual_interpreter=FakeVideoDesignInterpreter()
        ).prepare(
            input_path=_temporary_video_design_file(
                source_text
            )
        )

        scene = VideoDesignVisualTruthAdapter().adapt(
            prepared
        )[0]

        self.assertEqual(
            source_text,
            scene["abstract_source"]
        )
        self.assertNotEqual(
            source_text,
            scene["visible_subject"]
        )
        self.assertNotEqual(
            source_text,
            scene["visible_action"]
        )
        self.assertNotEqual(
            source_text,
            scene["visible_environment"]
        )
        self.assertNotEqual(
            source_text,
            scene["filmable_interpretation"]
        )
        self.assertIn(
            "biblioteca",
            scene["visible_environment"]
        )
        self.assertIn(
            "misterio",
            scene["visible_action"]
        )
        self.assertTrue(
            scene["key_objects"]
        )

    def test_rejects_degenerate_interpretation_copying_source_everywhere(self):
        class DegenerateAIBuilder:

            def __init__(
                self,
                ai_config
            ):
                self.ai_config = ai_config

            def build(
                self,
                prompt
            ):
                text = "Harry Potter y el misterio del principe"
                return json.dumps(
                    [
                        {
                            "scene": 1,
                            "visible_subject": text,
                            "visible_action": text,
                            "visible_environment": text,
                            "filmable_interpretation": text,
                            "abstract_source": text,
                        }
                    ]
                )

        interpreter = VisualDesignInterpreter(
            ai_config={
                "model": "fake"
            },
            profile={
                "tone": "modo_conciencia",
                "platform": "vertical",
                "format": "vertical",
            },
            ai_builder_factory=DegenerateAIBuilder
        )

        with self.assertRaises(OperationalError) as context:
            interpreter.interpret(
                "Harry Potter y el misterio del principe"
            )

        self.assertEqual("EXTERNAL_SERVICE", context.exception.context.family)

    def test_design_video_generates_one_image_and_one_i2v_clip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            previous_cwd = Path.cwd()
            fake_image_builder = FakeImageBuilder()
            fake_video_builder = FakeVideoComponentBuilder()
            video_design_text = (
                "Nikola Tesla sentado en su despacho "
                "con una bombilla iluminandose."
            )
            profile_resolver = ProfileResolver(
                Path.cwd()
                / "config"
                / "profiles"
            )
            profile_key = OperationalProfileKey(
                ProfileComponent.VIDEO,
                "vertical",
                "video_vertical",
            )
            profile = profile_resolver.load_operational(
                profile_key
            )

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
                    "Tema que no debe usarse.",
                    encoding="utf-8"
                )
                (
                    input_dir
                    / "guion.txt"
                ).write_text(
                    "Guion narrativo que no debe usarse.",
                    encoding="utf-8"
                )
                (
                    input_dir
                    / "guion_imagen.txt"
                ).write_text(
                    "Diseno de imagen que no debe usarse.",
                    encoding="utf-8"
                )
                (
                    input_dir
                    / "guion_video.txt"
                ).write_text(
                    video_design_text,
                    encoding="utf-8"
                )

                with patch(
                    "app.core.start.ScriptOperation",
                    side_effect=AssertionError(
                        "ScriptOperation must not run"
                    )
                ), patch(
                    "app.core.start.ScriptPreparationService",
                    side_effect=AssertionError(
                        "ScriptPreparationService must not run"
                    )
                ), patch(
                    "app.core.start.VoiceBuilder",
                    side_effect=AssertionError(
                        "VoiceBuilder must not run"
                    )
                ), patch(
                    "app.core.start.MusicSelector",
                    side_effect=AssertionError(
                        "MusicSelector must not run"
                    )
                ), patch(
                    "app.core.start.AudioMixer",
                    side_effect=AssertionError(
                        "AudioMixer must not run"
                    )
                ), patch(
                    "app.core.start.SubtitleBuilder",
                    side_effect=AssertionError(
                        "SubtitleBuilder must not run"
                    )
                ), patch(
                    "app.core.start.SrtOptimizer",
                    side_effect=AssertionError(
                        "SrtOptimizer must not run"
                    )
                ), patch(
                    "app.core.start.StoryboardBuilder",
                    side_effect=AssertionError(
                        "StoryboardBuilder must not run"
                    )
                ), patch(
                    "app.core.start.VideoBuilder",
                    side_effect=AssertionError(
                        "VideoBuilder must not run"
                    )
                ), patch(
                    "app.core.start.MediaProbe.get_duration",
                    return_value=None
                ), patch(
                    "app.modules.design.execution_coordinator.ConfigManager"
                ) as config_manager_mock, patch(
                    "app.modules.video_component.profile_parameters.ProfileResolver",
                    return_value=profile_resolver
                ):
                    config_manager_mock.return_value.get_profile_config.return_value = (
                        profile
                    )
                    config_manager_mock.return_value.get_operational_profile_key.return_value = (
                        profile_key
                    )
                    result = start.ejecutar_diseno_video(
                        preparation_service=VideoDesignPreparationService(
                            visual_interpreter=(
                                FakeVideoDesignInterpreter()
                            )
                        ),
                        image_builder=fake_image_builder,
                        video_builder=fake_video_builder
                    )

                config_manager_mock.return_value.get_profile_config.assert_called_once_with()
                config_manager_mock.return_value.get_operational_profile_key.assert_called_once_with()

                self.assertEqual(
                    "scene_001.mp4",
                    Path(result).name
                )
                self.assertEqual(
                    1,
                    len(fake_image_builder.received_scenes)
                )
                self.assertEqual(
                    (
                        "Nikola Tesla sentado en su despacho, "
                        "iluminado por una bombilla que cobra "
                        "intensidad de forma sutil."
                    ),
                    fake_image_builder.received_scenes[0][
                        "filmable_interpretation"
                    ]
                )
                self.assertEqual(
                    1,
                    len(fake_video_builder.calls)
                )
                call = fake_video_builder.calls[0]
                self.assertEqual(
                    "scene_001.png",
                    call["source_path"].name
                )
                self.assertEqual(
                    "scene_001.mp4",
                    call["output_name"]
                )
                self.assertEqual(
                    "Nikola Tesla sentado",
                    call["storyboard_scene"].visible_subject
                )
                self.assertIn(
                    "bombilla",
                    call["storyboard_scene"].filmable_interpretation
                )
                self.assertEqual(
                    448,
                    call["overrides"]["generation_width"]
                )
                self.assertEqual(
                    800,
                    call["overrides"]["generation_height"]
                )
                self.assertEqual(
                    49,
                    call["overrides"]["frames"]
                )
                self.assertEqual(
                    20,
                    call["overrides"]["steps"]
                )
                manifest_path = (
                    root
                    / "output"
                    / "default_project"
                    / "video_clips"
                    / "video_clips_manifest.json"
                )
                manifest = json.loads(
                    manifest_path.read_text(
                        encoding="utf-8"
                    )
                )
                self.assertEqual(
                    1,
                    len(manifest)
                )
                self.assertEqual(
                    "scene_001.mp4",
                    Path(manifest[0]["output_clip"]).name
                )
                self.assertFalse(
                    (
                        root
                        / "output"
                        / "default_project"
                        / "audio"
                    ).exists()
                )
                self.assertFalse(
                    (
                        root
                        / "output"
                        / "default_project"
                        / "subtitles"
                    ).exists()
                )
                self.assertFalse(
                    (
                        root
                        / "output"
                        / "default_project"
                        / "video"
                    ).exists()
                )
            finally:
                os.chdir(
                    previous_cwd
                )


if __name__ == "__main__":
    unittest.main()


def _temporary_video_design_file(
    text
):
    temp_dir = tempfile.TemporaryDirectory()
    path = (
        Path(
            temp_dir.name
        )
        / "guion_video.txt"
    )
    path.write_text(
        text,
        encoding="utf-8"
    )
    _TEMPORARY_VIDEO_DESIGN_DIRS.append(
        temp_dir
    )
    return path


_TEMPORARY_VIDEO_DESIGN_DIRS = []
