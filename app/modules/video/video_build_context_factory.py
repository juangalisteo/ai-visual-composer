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

        video_config = (
            self._apply_overlay_mode(
                video_config
            )
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
        thematic_folders = tuple(
            folder
            for folder in valid_folders
            if folder != neutral_folder
        )

        if not thematic_folders:
            return self._apply_selected_overlay_folder(
                video_config=video_config,
                selected_folder=neutral_folder
            )

        resolution = (
            resolver.resolve_categories(
                topic=self._read_topic(),
                folders=thematic_folders
            )
        )

        return self._apply_overlay_category_resolution(
            video_config=video_config,
            resolution=resolution,
            neutral_folder=neutral_folder
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

    def _apply_overlay_category_resolution(
        self,
        video_config,
        resolution,
        neutral_folder
    ):
        thematic_folders = (
            resolution.thematic_folders
        )

        if not thematic_folders:
            return self._apply_selected_overlay_folder(
                video_config=video_config,
                selected_folder=neutral_folder
            )

        folders = list(
            thematic_folders
        )

        folder_weights = {}

        if resolution.primary:
            folder_weights[
                resolution.primary
            ] = 3.0

        for folder in resolution.secondary:
            folder_weights[
                folder
            ] = 2.0

        if (
            neutral_folder
            and neutral_folder not in folders
        ):
            folders.append(
                neutral_folder
            )
            folder_weights[
                neutral_folder
            ] = 1.0

        return replace(
            video_config,
            overlays=replace(
                video_config.overlays,
                enabled=True,
                folders=tuple(
                    folders
                ),
                folder_selection="random",
                folder_weights=folder_weights
            )
        )

    def _read_topic(
        self
    ):
        topic_path = Path(
            "input/tema.txt"
        )

        if not topic_path.exists():
            return ""

        return topic_path.read_text(
            encoding="utf-8"
        ).strip()
