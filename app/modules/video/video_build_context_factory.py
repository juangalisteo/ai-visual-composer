from pathlib import Path

from app.managers.project_manager import ProjectManager
from app.shared.progress_logger import ProgressLogger

from app.modules.video.media.audio_resolver import AudioResolver
from app.modules.video.media.media_loader import MediaLoader
from app.modules.video.media.timeline_builder import TimelineBuilder
from app.modules.video.video_build_context import VideoBuildContext
from app.modules.video.video_config import VideoConfigLoader


class VideoBuildContextFactory:

    def build(
        self,
        audio_path=None,
        subtitle_path=None,
        images_manifest_path=None,
        output_path=None
    ):
        project = ProjectManager()

        resolved_audio_path = (
            AudioResolver().resolve(
                project=project,
                audio_path=audio_path
            )
        )

        resolved_subtitle_path = Path(
            subtitle_path
            or project.subtitle_path()
        )

        resolved_manifest_path = Path(
            images_manifest_path
            or project.images_manifest_path()
        )

        resolved_output_path = Path(
            output_path
            or project.video_path()
        )

        video_config = (
            VideoConfigLoader().load()
        )

        media = MediaLoader().load(
            audio_path=resolved_audio_path,
            subtitle_path=resolved_subtitle_path,
            images_manifest_path=resolved_manifest_path,
            output_path=resolved_output_path
        )

        image_count = len(
            media.image_paths
        )

        ProgressLogger.info(
            f"Audio: {media.audio_path.name}"
        )

        ProgressLogger.info(
            f"Imágenes: {image_count}"
        )

        timeline = TimelineBuilder().build(
            audio_path=media.audio_path,
            subtitle_path=media.subtitle_path,
            image_count=image_count,
            subtitle_offset=(
                video_config.subtitle_offset
            )
        )

        ProgressLogger.info(
            f"Duración del audio: "
            f"{timeline.audio_duration:.2f} segundos"
        )

        ProgressLogger.info(
            f"Duración por imagen: "
            f"{timeline.image_duration:.2f} segundos"
        )

        ProgressLogger.info(
            f"Duración de transición: "
            f"{video_config.transitions.duration:.2f} segundos"
        )

        ProgressLogger.info(
            f"Resolución: "
            f"{video_config.width}x{video_config.height}"
        )

        ProgressLogger.info(
            f"Fotogramas por segundo: "
            f"{video_config.fps}"
        )

        return VideoBuildContext(
            config=video_config,
            media=media,
            timeline=timeline
        )
