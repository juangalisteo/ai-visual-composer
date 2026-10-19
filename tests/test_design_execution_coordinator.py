import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app.modules.design import DesignExecutionCoordinator


class _Project:

    def __init__(
        self,
        root,
    ):
        self.root = Path(root)
        self.project_name = "design-project"
        self.setup = Mock()

    def storyboard_path(self):
        return self.root / "storyboard" / "storyboard.json"

    def images_dir(self):
        return self.root / "images"

    def images_manifest_path(self):
        return self.images_dir() / "images_manifest.json"

    def final_audio_path(self):
        return self.root / "audio" / "audio_final.mp3"

    def audio_path(self):
        return self.root / "audio" / "voz.mp3"


class _PreparationService:

    def __init__(
        self,
        prepared_design,
    ):
        self.prepared_design = prepared_design
        self.input_path = None

    def prepare(
        self,
        input_path=None,
    ):
        self.input_path = input_path
        return self.prepared_design


class _VisualTruthAdapter:

    def __init__(
        self,
        scenes,
    ):
        self.scenes = scenes
        self.prepared_design = None

    def adapt(
        self,
        prepared_design,
    ):
        self.prepared_design = prepared_design
        return self.scenes


class _ImageBuilder:

    def __init__(
        self,
        image_name="scene_001.png",
    ):
        self.image_name = image_name
        self.calls = []

    def build(
        self,
        storyboard_path=None,
        output_dir=None,
    ):
        storyboard_path = Path(storyboard_path)
        output_dir = Path(output_dir)
        self.calls.append(
            {
                "storyboard_path": storyboard_path,
                "output_dir": output_dir,
                "scenes": json.loads(
                    storyboard_path.read_text(
                        encoding="utf-8",
                    )
                ),
            }
        )
        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )
        image_path = output_dir / self.image_name
        image_path.write_bytes(b"image")
        manifest_path = output_dir / "images_manifest.json"
        manifest_path.write_text(
            json.dumps(
                [{"image": str(image_path)}],
            ),
            encoding="utf-8",
        )
        return manifest_path


class _Config:

    def __init__(self, profile, profile_key, ai_config):
        self.profile = profile
        self.profile_key = profile_key
        self.ai_config = ai_config

    def get_profile_config(self):
        return self.profile

    def get_operational_profile_key(self):
        return self.profile_key

    def get_ai_config(self):
        return self.ai_config


class _I2VBatch:

    def __init__(
        self,
        output_name="scene_001.mkv",
    ):
        self.output_name = output_name
        self.calls = []

    def __call__(
        self,
        storyboard_path=None,
        images_manifest_path=None,
        project=None,
        video_builder=None,
        profile_key=None,
    ):
        self.calls.append(
            {
                "storyboard_path": Path(storyboard_path),
                "images_manifest_path": Path(images_manifest_path),
                "project": project,
                "video_builder": video_builder,
                "profile_key": profile_key,
            }
        )
        output_dir = project.root / "video_clips"
        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )
        output_clip = output_dir / self.output_name
        output_clip.write_bytes(b"video")
        manifest_path = output_dir / "video_clips_manifest.json"
        manifest_path.write_text(
            json.dumps(
                [{
                    "scene": 1,
                    "output_clip": str(output_clip),
                }],
            ),
            encoding="utf-8",
        )
        return manifest_path


class _Telemetry:

    def __init__(
        self,
    ):
        self.measurement = None
        self.measurements = []
        self.completion = None

    def measure_stage(
        self,
        function,
        *args,
        **kwargs,
    ):
        self.measurement = (
            function,
            args,
            kwargs,
        )
        self.measurements.append(
            self.measurement
        )
        return function(
            *args,
            **kwargs,
        ), 1.25

    def complete(
        self,
        **kwargs,
    ):
        self.completion = kwargs


class DesignExecutionCoordinatorTest(unittest.TestCase):

    def _coordinator(
        self,
        telemetry,
    ):
        return DesignExecutionCoordinator(
            pipeline_telemetry=telemetry,
            summary_factory=lambda project_name: {
                "project_name": project_name,
            },
        )

    def test_run_image_prepares_visual_truth_persists_storyboard_and_measures(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = _Project(root)
            telemetry = _Telemetry()
            coordinator = self._coordinator(telemetry)
            prepared_design = object()
            preparation = _PreparationService(prepared_design)
            scenes = [{"scene": 1, "text": "Diseño manual"}]
            adapter = _VisualTruthAdapter(scenes)
            builder = _ImageBuilder()
            input_path = root / "design.txt"

            result = coordinator.run_image(
                pipeline_start=10.0,
                project=project,
                input_design_path=input_path,
                preparation_service=preparation,
                visual_truth_adapter=adapter,
                image_builder=builder,
            )

            self.assertEqual(input_path, preparation.input_path)
            self.assertIs(prepared_design, adapter.prepared_design)
            self.assertEqual(scenes, builder.calls[0]["scenes"])
            self.assertEqual(project.images_dir(), builder.calls[0]["output_dir"])
            self.assertEqual(project.images_manifest_path(), result)
            self.assertFalse(project.setup.called)
            self.assertEqual(
                {"Imágenes": 1.25},
                telemetry.completion["stage_times"],
            )
            self.assertEqual(10.0, telemetry.completion["pipeline_start"])
            artifacts = telemetry.completion["artifacts"]
            self.assertEqual(project.storyboard_path(), artifacts.storyboard_path)
            self.assertEqual(
                project.images_manifest_path(),
                artifacts.images_manifest_path,
            )

    def test_run_image_uses_the_existing_default_design_input(self):
        with tempfile.TemporaryDirectory() as directory:
            telemetry = _Telemetry()
            preparation = _PreparationService(object())
            coordinator = self._coordinator(telemetry)

            coordinator.run_image(
                project=_Project(directory),
                preparation_service=preparation,
                visual_truth_adapter=_VisualTruthAdapter([{"scene": 1}]),
                image_builder=_ImageBuilder(),
            )

        self.assertEqual(
            Path("input/guion_imagen.txt"),
            preparation.input_path,
        )

    def test_run_image_rejects_more_than_one_scene_before_builder(self):
        with tempfile.TemporaryDirectory() as directory:
            telemetry = _Telemetry()
            builder = _ImageBuilder()

            with self.assertRaisesRegex(ValueError, "exactamente una escena"):
                self._coordinator(telemetry).run_image(
                    project=_Project(directory),
                    preparation_service=_PreparationService(object()),
                    visual_truth_adapter=_VisualTruthAdapter(
                        [{"scene": 1}, {"scene": 2}],
                    ),
                    image_builder=builder,
                )

        self.assertEqual([], builder.calls)
        self.assertIsNone(telemetry.measurement)

    def test_run_image_rejects_a_manifest_without_scene_001_png(self):
        with tempfile.TemporaryDirectory() as directory:
            telemetry = _Telemetry()

            with self.assertRaisesRegex(ValueError, "scene_001.png"):
                self._coordinator(telemetry).run_image(
                    project=_Project(directory),
                    preparation_service=_PreparationService(object()),
                    visual_truth_adapter=_VisualTruthAdapter([{"scene": 1}]),
                    image_builder=_ImageBuilder("scene_002.png"),
                )

        self.assertIsNotNone(telemetry.measurement)
        self.assertIsNone(telemetry.completion)

    def test_run_image_preserves_preparation_errors(self):
        class FailingPreparation:

            def prepare(
                self,
                input_path=None,
            ):
                raise RuntimeError("preparation failure")

        with tempfile.TemporaryDirectory() as directory:
            telemetry = _Telemetry()

            with self.assertRaisesRegex(RuntimeError, "preparation failure"):
                self._coordinator(telemetry).run_image(
                    project=_Project(directory),
                    preparation_service=FailingPreparation(),
                    visual_truth_adapter=_VisualTruthAdapter([{"scene": 1}]),
                    image_builder=_ImageBuilder(),
                )

        self.assertIsNone(telemetry.measurement)
        self.assertIsNone(telemetry.completion)

    def test_run_video_prepares_one_scene_generates_one_lossless_clip_and_measures(self):
        with tempfile.TemporaryDirectory() as directory:
            project = _Project(directory)
            telemetry = _Telemetry()
            coordinator = self._coordinator(telemetry)
            prepared_design = object()
            preparation = _PreparationService(prepared_design)
            scenes = [{"scene": 1, "text": "Diseño vídeo"}]
            adapter = _VisualTruthAdapter(scenes)
            image_builder = _ImageBuilder()
            i2v_batch = _I2VBatch()
            video_builder = object()
            profile = {"technical": "profile"}
            profile_key = object()
            input_path = Path(directory) / "video-design.txt"

            result = coordinator.run_video(
                pipeline_start=20.0,
                project=project,
                input_design_path=input_path,
                preparation_service=preparation,
                visual_truth_adapter=adapter,
                image_builder=image_builder,
                video_builder=video_builder,
                profile=profile,
                profile_key=profile_key,
                generate_i2v_batch=i2v_batch,
                scene_clip_identity=lambda scene: f"scene_{int(scene):03d}",
            )

        self.assertEqual(input_path, preparation.input_path)
        self.assertIs(prepared_design, adapter.prepared_design)
        self.assertEqual(scenes, image_builder.calls[0]["scenes"])
        self.assertEqual("scene_001.mkv", result.name)
        self.assertFalse(project.setup.called)
        self.assertEqual(2, len(telemetry.measurements))
        self.assertEqual(
            {"Imágenes": 1.25, "Video I2V": 1.25},
            telemetry.completion["stage_times"],
        )
        self.assertEqual(20.0, telemetry.completion["pipeline_start"])
        self.assertEqual(1, len(i2v_batch.calls))
        i2v_call = i2v_batch.calls[0]
        self.assertEqual(project, i2v_call["project"])
        self.assertIs(video_builder, i2v_call["video_builder"])
        self.assertIs(profile_key, i2v_call["profile_key"])
        self.assertEqual(project.images_manifest_path(), i2v_call["images_manifest_path"])

    def test_run_video_uses_injected_config_for_profile_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = {"profile": "explicit"}
            profile_key = object()
            config = _Config(profile, profile_key, {"ai": "explicit"})
            i2v_batch = _I2VBatch()

            self._coordinator(_Telemetry()).run_video(
                project=_Project(directory),
                preparation_service=_PreparationService(object()),
                visual_truth_adapter=_VisualTruthAdapter([{"scene": 1}]),
                image_builder=_ImageBuilder(),
                video_builder=object(),
                config_manager=config,
                generate_i2v_batch=i2v_batch,
                scene_clip_identity=lambda scene: f"scene_{int(scene):03d}",
            )

        assert i2v_batch.calls[0]["profile_key"] is profile_key

    def test_run_video_rejects_a_scene_other_than_one_before_image_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            telemetry = _Telemetry()
            image_builder = _ImageBuilder()
            i2v_batch = _I2VBatch()

            with self.assertRaisesRegex(ValueError, "scene 1"):
                self._coordinator(telemetry).run_video(
                    project=_Project(directory),
                    preparation_service=_PreparationService(object()),
                    visual_truth_adapter=_VisualTruthAdapter([{"scene": 2}]),
                    image_builder=image_builder,
                    video_builder=object(),
                    profile={},
                    profile_key=object(),
                    generate_i2v_batch=i2v_batch,
                    scene_clip_identity=lambda scene: f"scene_{int(scene):03d}",
                )

        self.assertEqual([], image_builder.calls)
        self.assertEqual([], i2v_batch.calls)
        self.assertIsNone(telemetry.measurement)

    def test_run_video_preserves_i2v_errors(self):
        class FailingI2VBatch:

            def __call__(
                self,
                **kwargs,
            ):
                raise RuntimeError("i2v failure")

        with tempfile.TemporaryDirectory() as directory:
            telemetry = _Telemetry()

            with self.assertRaisesRegex(RuntimeError, "i2v failure"):
                self._coordinator(telemetry).run_video(
                    project=_Project(directory),
                    preparation_service=_PreparationService(object()),
                    visual_truth_adapter=_VisualTruthAdapter([{"scene": 1}]),
                    image_builder=_ImageBuilder(),
                    video_builder=object(),
                    profile={},
                    profile_key=object(),
                    generate_i2v_batch=FailingI2VBatch(),
                    scene_clip_identity=lambda scene: f"scene_{int(scene):03d}",
                )

        self.assertEqual(2, len(telemetry.measurements))
        self.assertIsNone(telemetry.completion)


if __name__ == "__main__":
    unittest.main()
