from dataclasses import replace
import os
from pathlib import Path

from app.managers.project_manager import ProjectManager
from app.shared.progress_logger import ProgressLogger

from app.modules.video.media.audio_resolver import AudioResolver
from app.modules.video.media.media_loader import MediaLoader
from app.modules.video.media.timeline_builder import TimelineBuilder
from app.modules.video.overlays.overlay_folder_resolver import (
    OverlayFolderResolver
)
from app.modules.video.video_build_context import VideoBuildContext
from app.modules.video.video_config import VideoConfigLoader


class VideoBuildContextFactory:

    def build(
        self,
        audio_path=None,
        subtitle_path=None,
        images_manifest_path=None,
        output_path=None,
        video_clips_manifest_path=None
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

        media_manifest_type = "images"

        if video_clips_manifest_path is not None:
            resolved_manifest_path = Path(
                video_clips_manifest_path
            )
            media_manifest_type = "video_clips"
        else:
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

        video_config = (
            self._apply_overlay_mode(
                video_config
            )
        )

        media = MediaLoader().load(
            audio_path=resolved_audio_path,
            subtitle_path=resolved_subtitle_path,
            images_manifest_path=resolved_manifest_path,
            output_path=resolved_output_path,
            media_manifest_type=media_manifest_type,
            storyboard_path=project.storyboard_path()
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

    def _apply_overlay_mode(
        self,
        video_config
    ):
        overlays_mode = (
            os.environ.get(
                "MC_OVERLAYS_MODE",
                ""
            )
            .strip()
            .lower()
        )

        if not overlays_mode:
            return video_config

        if overlays_mode == "off":
            return replace(
                video_config,
                overlays=replace(
                    video_config.overlays,
                    enabled=False
                )
            )

        if overlays_mode != "smart":
            return video_config

        resolver = OverlayFolderResolver()

        valid_folders = (
            resolver.discover_valid_folders(
                directory=(
                    video_config.overlays.directory
                ),
                extensions=(
                    video_config.overlays.extensions
                ),
                types=(
                    video_config.overlays.types
                )
            )
        )

        if not valid_folders:
            return replace(
                video_config,
                overlays=replace(
                    video_config.overlays,
                    enabled=False,
                    folders=()
                )
            )

        neutral_folder = self._neutral_overlay_folder(
            valid_folders
        )
        if neutral_folder is None:
            return self._apply_selected_overlay_folder(
                video_config=video_config,
                selected_folder=None
            )

        return replace(
            video_config,
            overlays=replace(
                video_config.overlays,
                enabled=True,
                folders=valid_folders,
                repeat_mode="scene",
                folder_selection="random",
                folder_weights={}
            )
        )

    def _neutral_overlay_folder(
        self,
        folders
    ):
        for folder in folders:
            if folder == "Light Leaks":
                return folder

        return None

    def _apply_selected_overlay_folder(
        self,
        video_config,
        selected_folder
    ):
        enabled = selected_folder is not None

        if selected_folder:
            folders = (
                selected_folder,
            )
        else:
            folders = ()

        return replace(
            video_config,
            overlays=replace(
                video_config.overlays,
                enabled=enabled,
                folders=folders
            )
        )
