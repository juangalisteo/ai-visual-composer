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
from app.modules.video.ffmpeg.i2v_normalizer import (
    I2VClipNormalizer
)


class VideoBuilder:

    def __init__(
        self,
        subtitle_profile=None
    ):
        self.subtitle_profile = subtitle_profile

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
            VideoBuildContextFactory(
                subtitle_profile=self.subtitle_profile
            ).build(
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

        render_service = VideoRenderService()
        diagnostics = FFmpegDiagnostics(
            output_path=build_context.media.output_path,
            scene_count=len(
                build_context.media.image_paths
            ),
        )

        try:
            build_context = I2VClipNormalizer().normalize(
                build_context=build_context,
                diagnostics=diagnostics,
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
            raise

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
