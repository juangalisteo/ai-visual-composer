import time

from app.modules.video.ffmpeg.graphs.base_graph_builder import (
    BaseGraphBuilder
)
from app.modules.video.ffmpeg.graphs.graph_result import GraphResult
from app.shared.progress_logger import ProgressLogger


class FadeGraphBuilder(
    BaseGraphBuilder
):

    def __init__(
        self,
        output_stream="[fadeout]",
    ):
        self.output_stream = output_stream

    def build(
        self,
        graph
    ):
        start = time.perf_counter()

        context = graph.context
        timeline = context.timeline
        fade_config = context.config.fade

        filter_parts = list(
            graph.filter_parts
        )

        current_stream = (
            graph.current_stream
        )

        if not current_stream:
            raise ValueError(
                "No existe un stream para aplicar "
                "el fade."
            )

        total_duration = (
            timeline.audio_duration
        )

        filters = [
            f"trim=duration={total_duration:.6f}"
        ]

        fade_duration = min(
            fade_config.duration,
            total_duration / 2
        )

        if (
            fade_config.enabled
            and fade_duration > 0
        ):
            if fade_config.fade_in:
                filters.append(
                    "fade=t=in:"
                    "st=0:"
                    f"d={fade_duration:.3f}"
                )

                ProgressLogger.info(
                    f"Fade inicial: "
                    f"{fade_duration:.2f} segundos"
                )

            else:
                ProgressLogger.info(
                    "Fade inicial: desactivado"
                )

            if fade_config.fade_out:
                fade_out_start = max(
                    0.0,
                    total_duration
                    - fade_duration
                )

                filters.append(
                    "fade=t=out:"
                    f"st={fade_out_start:.3f}:"
                    f"d={fade_duration:.3f}"
                )

                ProgressLogger.info(
                    f"Fade final: "
                    f"{fade_duration:.2f} segundos"
                )

            else:
                ProgressLogger.info(
                    "Fade final: desactivado"
                )

        else:
            ProgressLogger.info(
                "Fade: desactivado"
            )

        filters.append(
            "setpts=PTS-STARTPTS"
        )

        output_stream = self.output_stream

        filter_parts.append(
            f"{current_stream}"
            + ",".join(
                filters
            )
            + output_stream
        )

        ProgressLogger.info(
            f"Grafo de fade preparado "
            f"({time.perf_counter() - start:.4f} s)"
        )

        return GraphResult(
            parts=filter_parts,
            current_stream=output_stream,
            video_streams=graph.video_streams
        )
