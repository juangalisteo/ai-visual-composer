import time

from app.modules.video.ffmpeg.graphs.base_graph_builder import (
    BaseGraphBuilder
)
from app.modules.video.ffmpeg.graphs.graph_result import GraphResult

from app.modules.video.transitions.transition_selector import (
    TransitionSelector
)

from app.shared.progress_logger import ProgressLogger


class TransitionGraphBuilder(
    BaseGraphBuilder
):

    def __init__(
        self,
        transition_builder
    ):
        self.transition_builder = (
            transition_builder
        )

    def build(
        self,
        graph
    ):
        context = graph.context
        config = context.config
        timeline = context.timeline

        filter_parts = list(
            graph.filter_parts
        )

        video_streams = tuple(
            graph.video_streams
        )

        image_count = len(
            video_streams
        )

        if image_count <= 0:
            raise ValueError(
                "No existen streams de vídeo para "
                "construir las transiciones."
            )

        if image_count == 1:
            ProgressLogger.info(
                "Transiciones: ninguna"
            )

            return GraphResult(
                parts=filter_parts,
                current_stream=video_streams[0],
                video_streams=video_streams
            )

        if not config.transitions.enabled:
            output_stream = (
                "[tx_concat]"
            )

            filter_parts.append(
                "".join(
                    video_streams
                )
                + f"concat=n={image_count}:"
                + "v=1:a=0"
                + output_stream
            )

            ProgressLogger.info(
                "Transiciones: desactivadas"
            )

            return GraphResult(
                parts=filter_parts,
                current_stream=output_stream,
                video_streams=video_streams
            )

        start = time.perf_counter()

        ProgressLogger.start(
            "PREPARANDO TRANSICIONES"
        )

        transition_selector = (
            TransitionSelector(
                config.transitions
            )
        )

        current_stream = (
            video_streams[0]
        )

        for scene_index in range(
            1,
            image_count
        ):
            transition_type = (
                transition_selector.select(
                    scene_index=scene_index,
                    scene_count=image_count
                )
            )

            next_stream = (
                video_streams[
                    scene_index
                ]
            )

            output_stream = (
                f"[tx{scene_index}]"
            )

            transition_offset = (
                timeline.image_duration
                * scene_index
            )

            transition = (
                self.transition_builder.build(
                    previous_stream=current_stream,
                    current_stream=next_stream,
                    transition_type=transition_type,
                    duration=(
                        config.transitions.duration
                    ),
                    offset=transition_offset,
                    output_stream=output_stream,
                    from_scene=scene_index,
                    to_scene=scene_index + 1
                )
            )

            filter_parts.append(
                transition["filter"]
            )

            current_stream = (
                output_stream
            )

        ProgressLogger.finish(
            "TRANSICIONES PREPARADAS",
            time.perf_counter() - start
        )

        return GraphResult(
            parts=filter_parts,
            current_stream=current_stream,
            video_streams=video_streams
        )