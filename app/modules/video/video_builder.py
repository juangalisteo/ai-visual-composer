import time

from app.shared.progress_logger import ProgressLogger

from app.modules.video.video_build_context_factory import (
    VideoBuildContextFactory
)
from app.modules.video.video_component_factory import (
    VideoComponentFactory
)
from app.modules.video.video_filter_context_factory import (
    VideoFilterContextFactory
)
from app.modules.video.video_render_service import (
    VideoRenderService
)
from app.modules.video.ffmpeg.diagnostics import (
    FFmpegDiagnostics
)
from app.shared.operational_error import OperationalError, create_operational_error


class VideoBuilder:

    def __init__(
        self,
        subtitle_profile=None,
        intro_outro_selection=None,
        render_subtitles=True,
        warnings=None,
        config_manager=None,
        project=None,
        overlays_mode=None,
    ):
        self.subtitle_profile = subtitle_profile
        self.intro_outro_selection = (
            intro_outro_selection
        )
        self.render_subtitles = bool(render_subtitles)
        self.warnings = warnings
        self.config_manager = config_manager
        self.project = project
        self._overlays_mode = overlays_mode

    def build(
        self,
        audio_path=None,
        subtitle_path=None,
        images_manifest_path=None,
        video_clips_manifest_path=None,
        output_path=None
    ):
        total_start = time.perf_counter()

        ProgressLogger.start(
            "GENERANDO VÍDEO FINAL"
        )

        context_options = {
            "audio_path": audio_path,
            "subtitle_path": subtitle_path,
            "images_manifest_path": images_manifest_path,
            "video_clips_manifest_path": video_clips_manifest_path,
            "output_path": output_path,
        }
        if not self.render_subtitles:
            context_options["render_subtitles"] = False

        context_factory_options = {
            "subtitle_profile": self.subtitle_profile,
            "warnings": self.warnings,
            "config_manager": self.config_manager,
            "project": self.project,
        }
        if self._overlays_mode is not None:
            context_factory_options["overlays_mode"] = self._overlays_mode

        build_context = VideoBuildContextFactory(
            **context_factory_options,
        ).build(**context_options)

        if self.intro_outro_selection is None:
            render_service = VideoRenderService()
        else:
            render_service = VideoRenderService(
                intro_outro_selection=(
                    self.intro_outro_selection
                )
            )
        diagnostics = FFmpegDiagnostics(
            output_path=build_context.media.output_path,
            scene_count=len(
                build_context.media.image_paths
            ),
            config_manager=self.config_manager,
        )

        filter_context = None
        try:
            components = (
                VideoComponentFactory().create(
                    build_context.config
                )
            )

            filter_context = (
                VideoFilterContextFactory().build(
                    build_context=build_context,
                    components=components
                )
            )

            ProgressLogger.start(
                "PREPARANDO FFMPEG"
            )

            prepare_start = time.perf_counter()

            artifacts = render_service.build_artifacts(
                build_context=build_context,
                filter_context=filter_context,
                components=components
            )

            ProgressLogger.finish(
                "FFMPEG PREPARADO",
                time.perf_counter() - prepare_start
            )

            ProgressLogger.start(
                "RENDERIZANDO VÍDEO"
            )

            render_start = time.perf_counter()

            render_service.render_final(
                build_context=build_context,
                artifacts=artifacts,
                diagnostics=diagnostics,
            )

            render_elapsed = (
                time.perf_counter()
                - render_start
            )

            diagnostics.finish("SUCCESS")
        except Exception as error:
            diagnostics.finish(
                "FAILED",
                error=str(error),
            )
            if isinstance(error, OperationalError):
                raise
            if isinstance(error, (ValueError, RuntimeError)):
                raise create_operational_error(
                    family="VIDEO",
                    user_message="No se pudo preparar el render del video final.",
                    recommended_action="Revisa el diagnostico de FFmpeg y los recursos de entrada.",
                    operation="Preparar render de video",
                    resource=str(build_context.media.output_path),
                    diagnostic_reference=str(diagnostics.path),
                    technical_metadata={"phase": "video_build"},
                ) from error
            raise
        finally:
            if filter_context is not None:
                filter_context.cleanup_temporary_subtitle()

        total_elapsed = (
            time.perf_counter()
            - total_start
        )

        ProgressLogger.finish(
            "RENDER COMPLETADO",
            render_elapsed
        )

        ProgressLogger.info(
            f"Ruta: {build_context.media.output_path}"
        )

        ProgressLogger.finish(
            "VÍDEO FINALIZADO",
            total_elapsed
        )

        return build_context.media.output_path
