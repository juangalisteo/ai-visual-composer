import time

from app.modules.video.ffmpeg.filter_pipeline import (
    FilterPipeline
)
from app.modules.video.ffmpeg.graphs.fade_graph_builder import (
    FadeGraphBuilder
)
from app.modules.video.ffmpeg.graphs.motion_graph_builder import (
    MotionGraphBuilder
)
from app.modules.video.ffmpeg.graphs.overlay_graph_builder import (
    OverlayGraphBuilder
)
from app.modules.video.ffmpeg.graphs.subtitle_graph_builder import (
    SubtitleGraphBuilder
)
from app.modules.video.ffmpeg.graphs.transition_graph_builder import (
    TransitionGraphBuilder
)
from app.modules.video.ffmpeg.graphs.visual_effect_graph_builder import (
    VisualEffectGraphBuilder
)
from app.shared.progress_logger import ProgressLogger


class FilterBuilder:

    def build(
        self,
        context,
        motion_builder,
        transition_builder,
        overlay_builder,
        visual_effect_builder
    ):
        total_start = time.perf_counter()

        if not context.media.image_paths:
            raise ValueError(
                "No hay imágenes para construir "
                "el vídeo."
            )

        graph = FilterPipeline(
            context=context,
            stages=self._stages(
                motion_builder=motion_builder,
                transition_builder=transition_builder,
                overlay_builder=overlay_builder,
                visual_effect_builder=visual_effect_builder,
                render_subtitles=context.render_subtitles,
            ),
            overlay_builder=overlay_builder,
            visual_effect_builder=visual_effect_builder
        ).run()

        ProgressLogger.info(
            f"Duración esperada del montaje: "
            f"{graph.context.timeline.audio_duration:.2f} segundos"
        )

        ProgressLogger.finish(
            "FILTRO FFMPEG CONSTRUIDO",
            time.perf_counter() - total_start
        )

        return ";".join(
            graph.filter_parts
        )

    def _stages(
        self,
        motion_builder,
        transition_builder,
        overlay_builder,
        visual_effect_builder,
        render_subtitles=True,
    ):
        overlay_stage = OverlayGraphBuilder(
            overlay_builder
        )

        visual_effect_stage = VisualEffectGraphBuilder(
            visual_effect_builder
        )

        overlay_stage.refresh_layer_inputs = True
        visual_effect_stage.refresh_layer_inputs = True

        stages = (
            MotionGraphBuilder(
                motion_builder
            ),
            TransitionGraphBuilder(
                transition_builder
            ),
            overlay_stage,
            visual_effect_stage,
            FadeGraphBuilder(
                output_stream=(
                    "[fadeout]"
                    if render_subtitles
                    else "[vout]"
                )
            ),
        )

        if render_subtitles:
            return (*stages, SubtitleGraphBuilder())

        return stages
