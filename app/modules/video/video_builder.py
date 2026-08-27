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


class VideoBuilder:

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

        build_context = (
            VideoBuildContextFactory().build(
                audio_path=audio_path,
                subtitle_path=subtitle_path,
                images_manifest_path=(
                    images_manifest_path
                ),
                video_clips_manifest_path=(
                    video_clips_manifest_path
                ),
                output_path=output_path
            )
        )

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

        render_service = VideoRenderService()

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

        render_service.run(
            artifacts.command
        )

        render_elapsed = (
            time.perf_counter()
            - render_start
        )

        render_service.validate(
            build_context
        )

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
