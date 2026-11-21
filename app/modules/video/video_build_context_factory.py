from dataclasses import replace
from pathlib import Path

from app.managers.project_manager import ProjectManager
from app.shared.progress_logger import ProgressLogger

from app.modules.subtitles.policies.punctuation import reconcile_timing_text
from app.modules.subtitles.policies.timing import SubtitleTimingResolver
from app.modules.video.media.audio_resolver import AudioResolver
from app.modules.video.media.media_loader import MediaLoader
from app.modules.video.media.timeline_builder import TimelineBuilder
from app.modules.video.overlays.overlay_folder_resolver import (
    OverlayFolderResolver
)
from app.modules.video.video_build_context import VideoBuildContext
from app.modules.video.video_config import VideoConfigLoader


class VideoBuildContextFactory:

    def __init__(
        self,
        subtitle_profile=None,
        warnings=None,
        config_manager=None,
        project=None,
        overlays_mode=None,
    ):
        self.subtitle_profile = subtitle_profile
        self.warnings = warnings
        self.config_manager = config_manager
        self.project = project
        self._overlays_mode = overlays_mode

    def build(
        self,
        audio_path=None,
        subtitle_path=None,
        images_manifest_path=None,
        output_path=None,
        video_clips_manifest_path=None,
        render_subtitles=True,
    ):
        project = self.project or ProjectManager()

        resolved_audio_path = (
            AudioResolver().resolve(
                project=project,
                audio_path=audio_path
            )
        )

        resolved_subtitle_path = (
            Path(
                subtitle_path
                or project.subtitle_path()
            )
            if render_subtitles
            else None
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

        config_loader = VideoConfigLoader(
            subtitle_profile=self.subtitle_profile,
            config_manager=self.config_manager,
        )
        load_options = {}
        if not render_subtitles:
            load_options["render_subtitles"] = False
        if media_manifest_type == "video_clips":
            load_options["still_images"] = False
        video_config = config_loader.load(**load_options)

        video_config = (
            self._apply_overlay_mode(
                video_config
            )
        )

        media_options = {
            "audio_path": resolved_audio_path,
            "subtitle_path": resolved_subtitle_path,
            "images_manifest_path": resolved_manifest_path,
            "output_path": resolved_output_path,
            "media_manifest_type": media_manifest_type,
            "storyboard_path": project.storyboard_path(),
        }
        if not render_subtitles:
            media_options["render_subtitles"] = False

        media = MediaLoader().load(
            **media_options,
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

        timeline_options = {
            "audio_path": media.audio_path,
            "subtitle_path": media.subtitle_path,
            "image_count": image_count,
            "subtitle_offset": (
                video_config.subtitle_offset
                if render_subtitles
                else 0.0
            ),
        }
        if not render_subtitles:
            timeline_options["render_subtitles"] = False
        scene_durations = getattr(
            media,
            "scene_durations",
            ()
        )
        if scene_durations:
            timeline_options["scene_durations"] = scene_durations

        timeline = TimelineBuilder().build(
            **timeline_options,
        )

        ProgressLogger.info(
            f"Duración del audio: "
            f"{timeline.audio_duration:.2f} segundos"
        )

        timed_scenes = getattr(
            timeline,
            "scene_durations",
            ()
        )
        ProgressLogger.info(
            f"Duración por imagen: "
            f"de {min(timed_scenes):.2f} a {max(timed_scenes):.2f} "
            "segundos (storyboard)"
            if timed_scenes
            else f"Duración por imagen: "
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

        subtitle_timing = (
            self._subtitle_timing(
                subtitle_path=media.subtitle_path,
                project=project
            )
            if render_subtitles
            else None
        )

        return VideoBuildContext(
            config=video_config,
            media=media,
            timeline=timeline,
            render_subtitles=bool(render_subtitles),
            subtitle_timing=subtitle_timing,
        )

    @staticmethod
    def _subtitle_timing(
        subtitle_path,
        project
    ):
        """Return the word times for the subtitles.

        When the project has a script, its words go on the Whisper times
        with the same alignment the SRT got (``reconcile_timing_text``), so
        the word effects see the words of the SRT lines.
        """
        timing = SubtitleTimingResolver().resolve(
            subtitle_path=subtitle_path
        )

        if timing is None:
            return None

        script_path = Path(
            project.script_path()
        )

        if not script_path.is_file():
            return timing

        return reconcile_timing_text(
            script_path.read_text(
                encoding="utf-8"
            ),
            timing,
            authoritative=True
        )

    def _apply_overlay_mode(
        self,
        video_config
    ):
        overlays_mode = (self._overlays_mode or "").strip().lower()

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

        if overlays_mode == "on":
            return replace(
                video_config,
                overlays=replace(
                    video_config.overlays,
                    enabled=True,
                ),
            )

        if overlays_mode != "smart":
            return video_config

        resolver = OverlayFolderResolver(
            warnings=self.warnings
        )

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
