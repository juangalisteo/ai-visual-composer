import time

from app.modules.video.ffmpeg.graphs.base_graph_builder import (
    BaseGraphBuilder
)
from app.modules.video.ffmpeg.graphs.graph_result import GraphResult
from app.shared.progress_logger import ProgressLogger


class MotionGraphBuilder(
    BaseGraphBuilder
):

    def __init__(
        self,
        motion_builder
    ):
        self.motion_builder = motion_builder

    def build(
        self,
        graph
    ):
        start = time.perf_counter()

        ProgressLogger.start(
            "PREPARANDO MOVIMIENTOS"
        )

        context = graph.context
        media = context.media
        timeline = context.timeline
        config = context.config

        filter_parts = list(
            graph.filter_parts
        )

        image_count = len(
            media.image_paths
        )

        if image_count <= 0:
            raise ValueError(
                "No hay imágenes para construir "
                "los movimientos."
            )

        video_streams = []

        transitions_enabled = (
            config.transitions.enabled
            and image_count > 1
        )

        transition_duration = (
            config.transitions.duration
            if transitions_enabled
            else 0.0
        )

        for index, image_path in enumerate(
            media.image_paths
        ):
            is_last_image = (
                index
                == image_count - 1
            )

            motion_duration = (
                timeline.image_duration
            )

            if (
                transitions_enabled
                and not is_last_image
            ):
                motion_duration += (
                    transition_duration
                )

            motion = self.motion_builder.build(
                image_index=index,
                image_count=image_count,
                image_path=image_path,
                duration=motion_duration,
                width=config.width,
                height=config.height,
                fps=config.fps
            )

            stream_name = (
                f"v{index}"
            )

            filter_parts.append(
                f"[{index}:v]"
                f"{motion['filter']},"
                f"trim=duration={motion_duration:.6f},"
                f"fps={config.fps},"
                f"format={config.pixel_format},"
                f"setsar=1,"
                f"settb=AVTB,"
                f"setpts=PTS-STARTPTS"
                f"[{stream_name}]"
            )

            video_streams.append(
                f"[{stream_name}]"
            )

        ProgressLogger.finish(
            "MOVIMIENTOS PREPARADOS",
            time.perf_counter() - start
        )

        return GraphResult(
            parts=filter_parts,
            current_stream=video_streams[0],
            video_streams=tuple(
                video_streams
            )
        )