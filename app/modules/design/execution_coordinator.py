"""Coordination for manual DESIGN execution."""

import json
import time
from pathlib import Path

from app.core.pipeline_telemetry import (
    PipelineTelemetry,
    PipelineTelemetryArtifacts,
)
from app.managers.pipeline_summary import PipelineSummary
from app.managers.project_manager import ProjectManager
from app.modules.images import (
    ImageDesignPreparationService,
    ImageDesignVisualTruthAdapter,
)
from app.modules.images.image_builder import ImageBuilder
from app.modules.video_component import (
    VideoComponentBuilder,
    VideoDesignPreparationService,
    VideoDesignVisualTruthAdapter,
)
from app.shared.config_manager import ConfigManager


class DesignExecutionCoordinator:
    """Coordinate DESIGN routes through existing capabilities."""

    def __init__(
        self,
        pipeline_telemetry=None,
        summary_factory=None,
        project_factory=None,
    ):
        self._pipeline_telemetry = (
            pipeline_telemetry
            or PipelineTelemetry()
        )
        self._summary_factory = (
            summary_factory
            or PipelineSummary
        )
        self._project_factory = (
            project_factory
            or ProjectManager
        )

    def run_image(
        self,
        pipeline_start=None,
        project=None,
        input_design_path=None,
        preparation_service=None,
        visual_truth_adapter=None,
        image_builder=None,
    ):
        if pipeline_start is None:
            pipeline_start = time.perf_counter()

        project = (
            project
            or self._project_factory()
        )
        summary = self._summary_factory(
            project.project_name
        )

        preparation_service = (
            preparation_service
            or ImageDesignPreparationService()
        )
        visual_truth_adapter = (
            visual_truth_adapter
            or ImageDesignVisualTruthAdapter()
        )
        image_builder = (
            image_builder
            or ImageBuilder()
        )

        prepared_design = preparation_service.prepare(
            input_path=(
                input_design_path
                or Path("input/guion_imagen.txt")
            )
        )
        scenes = visual_truth_adapter.adapt(
            prepared_design
        )

        self.ensure_single_design_scene(
            scenes
        )
        storyboard_path = self.persist_storyboard(
            project=project,
            scenes=scenes,
        )

        images_manifest_path, images_elapsed = (
            self._pipeline_telemetry.measure_stage(
                image_builder.build,
                storyboard_path=storyboard_path,
                output_dir=project.images_dir(),
            )
        )

        self.ensure_single_design_image(
            images_manifest_path
        )

        self._pipeline_telemetry.complete(
            summary=summary,
            stage_times={
                "Imágenes": images_elapsed,
            },
            pipeline_start=pipeline_start,
            artifacts=self._telemetry_artifacts(
                project
            ),
        )

        return images_manifest_path

    def run_video(
        self,
        pipeline_start=None,
        project=None,
        input_design_path=None,
        preparation_service=None,
        visual_truth_adapter=None,
        image_builder=None,
        video_builder=None,
        profile=None,
        profile_key=None,
        generate_i2v_batch=None,
        scene_clip_identity=None,
    ):
        if pipeline_start is None:
            pipeline_start = time.perf_counter()

        project = (
            project
            or self._project_factory()
        )
        summary = self._summary_factory(
            project.project_name
        )

        preparation_service = (
            preparation_service
            or VideoDesignPreparationService()
        )
        visual_truth_adapter = (
            visual_truth_adapter
            or VideoDesignVisualTruthAdapter()
        )
        image_builder = (
            image_builder
            or ImageBuilder()
        )
        video_builder = (
            video_builder
            or VideoComponentBuilder()
        )
        if profile is None:
            config = ConfigManager()
            profile = config.get_profile_config()
            if profile_key is None:
                profile_key = config.get_operational_profile_key()

        prepared_design = preparation_service.prepare(
            input_path=(
                input_design_path
                or Path("input/guion_video.txt")
            )
        )
        scenes = visual_truth_adapter.adapt(
            prepared_design
        )

        self.ensure_single_video_design_scene(
            scenes
        )
        storyboard_path = self.persist_storyboard(
            project=project,
            scenes=scenes,
        )

        images_manifest_path, images_elapsed = (
            self._pipeline_telemetry.measure_stage(
                image_builder.build,
                storyboard_path=storyboard_path,
                output_dir=project.images_dir(),
            )
        )

        self.ensure_single_design_image(
            images_manifest_path
        )

        video_clips_manifest_path, video_elapsed = (
            self._pipeline_telemetry.measure_stage(
                generate_i2v_batch,
                storyboard_path=storyboard_path,
                images_manifest_path=images_manifest_path,
                project=project,
                video_builder=video_builder,
                profile_key=profile_key,
            )
        )

        output_clip = self.ensure_single_video_design_clip(
            video_clips_manifest_path,
            scene_clip_identity=scene_clip_identity,
        )

        self._pipeline_telemetry.complete(
            summary=summary,
            stage_times={
                "Imágenes": images_elapsed,
                "Video I2V": video_elapsed,
            },
            pipeline_start=pipeline_start,
            artifacts=self._telemetry_artifacts(
                project
            ),
        )

        return output_clip

    @staticmethod
    def persist_storyboard(
        project,
        scenes,
    ):
        storyboard_path = project.storyboard_path()
        storyboard_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        storyboard_path.write_text(
            json.dumps(
                scenes,
                ensure_ascii=False,
                indent=4,
            ),
            encoding="utf-8",
        )
        return storyboard_path

    @staticmethod
    def ensure_single_design_scene(
        scenes,
    ):
        if not isinstance(
            scenes,
            list,
        ):
            raise ValueError(
                "El diseño visual debe producir una lista "
                "de escenas."
            )

        if len(
            scenes,
        ) != 1:
            raise ValueError(
                "El diseño visual debe producir exactamente "
                "una escena."
            )

    @staticmethod
    def ensure_single_design_image(
        images_manifest_path,
    ):
        manifest_path = Path(
            images_manifest_path
        )
        manifest = json.loads(
            manifest_path.read_text(
                encoding="utf-8",
            )
        )

        if not isinstance(
            manifest,
            list,
        ):
            raise ValueError(
                "El manifiesto de diseño debe contener "
                "una lista de imágenes."
            )

        if len(
            manifest,
        ) != 1:
            raise ValueError(
                "El diseño visual debe generar exactamente "
                "una imagen."
            )

        image_name = Path(
            str(
                manifest[0].get(
                    "image",
                    "",
                )
            )
        ).name

        if image_name != "scene_001.png":
            raise ValueError(
                "La imagen de diseño debe corresponder a "
                "scene_001.png."
            )

    @classmethod
    def ensure_single_video_design_scene(
        cls,
        scenes,
    ):
        cls.ensure_single_design_scene(
            scenes
        )

        scene = scenes[0]
        if not isinstance(
            scene,
            dict,
        ):
            raise ValueError(
                "El diseño de vídeo debe producir una escena válida."
            )

        if int(
            scene.get(
                "scene",
                0,
            )
        ) != 1:
            raise ValueError(
                "El diseño de vídeo debe producir scene 1."
            )

    @staticmethod
    def ensure_single_video_design_clip(
        video_clips_manifest_path,
        scene_clip_identity,
    ):
        manifest_path = Path(
            video_clips_manifest_path
        )
        manifest = json.loads(
            manifest_path.read_text(
                encoding="utf-8",
            )
        )

        if not isinstance(
            manifest,
            list,
        ):
            raise ValueError(
                "El manifiesto de diseño de vídeo debe "
                "contener una lista de clips."
            )

        if len(
            manifest,
        ) != 1:
            raise ValueError(
                "El diseño de vídeo debe generar exactamente "
                "un clip."
            )

        try:
            scene_number = int(
                manifest[0][
                    "scene"
                ]
            )
        except (
            KeyError,
            TypeError,
            ValueError,
        ) as error:
            raise ValueError(
                "El clip de diseño de vídeo debe declarar scene 1."
            ) from error

        if scene_number != 1:
            raise ValueError(
                "El clip de diseño de vídeo debe corresponder "
                "a scene 1."
            )

        output_clip = Path(
            str(
                manifest[0].get(
                    "output_clip",
                    "",
                )
            )
        )

        expected_identity = scene_clip_identity(
            scene_number
        )
        if output_clip.stem != expected_identity:
            raise ValueError(
                "El clip de diseño de vídeo debe corresponder "
                f"a {expected_identity}."
            )

        if not output_clip.exists():
            raise FileNotFoundError(
                "No existe el clip de diseño de vídeo: "
                f"{output_clip}"
            )

        return output_clip

    @staticmethod
    def _telemetry_artifacts(
        project,
    ):
        return PipelineTelemetryArtifacts(
            storyboard_path=project.storyboard_path(),
            images_manifest_path=project.images_manifest_path(),
            final_audio_path=project.final_audio_path(),
            audio_path=project.audio_path(),
        )
