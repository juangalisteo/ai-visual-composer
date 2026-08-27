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

            stream_name = (
                f"v{index}"
            )

            filter_parts.append(
                self._visual_filter(
                    index=index,
                    image_count=image_count,
                    image_path=image_path,
                    media_type=self._media_type(
                        media=media,
                        index=index
                    ),
                    source_duration=self._media_duration(
                        media=media,
                        index=index
                    ),
                    duration=motion_duration,
                    width=config.width,
                    height=config.height,
                    fps=config.fps,
                    pixel_format=config.pixel_format,
                    stream_name=stream_name
                )
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

    def _visual_filter(
        self,
        index,
        image_count,
        image_path,
        media_type,
        source_duration,
        duration,
        width,
        height,
        fps,
        pixel_format,
        stream_name
    ):
        if media_type == "video":
            ProgressLogger.info(
                f"Clip escena {index + 1}: "
                f"{duration:.2f} s"
            )

            return self._video_filter(
                index=index,
                image_count=image_count,
                image_path=image_path,
                source_duration=source_duration,
                duration=duration,
                width=width,
                height=height,
                fps=fps,
                pixel_format=pixel_format,
                stream_name=stream_name
            )

        motion = self.motion_builder.build(
            image_index=index,
            image_count=image_count,
            image_path=image_path,
            duration=duration,
            width=width,
            height=height,
            fps=fps
        )

        return (
            f"[{index}:v]"
            f"{motion['filter']},"
            f"trim=duration={duration:.6f},"
            f"fps={fps},"
            f"format={pixel_format},"
            "setsar=1,"
            "settb=AVTB,"
            "setpts=PTS-STARTPTS"
            f"[{stream_name}]"
        )

    def _video_filter(
        self,
        index,
        image_count,
        image_path,
        source_duration,
        duration,
        width,
        height,
        fps,
        pixel_format,
        stream_name
    ):
        source_duration = (
            source_duration
            if source_duration is not None
            else duration
        )

        source_frame_count = max(
            2,
            round(
                float(source_duration)
                * int(fps)
            )
        )

        reverse_frame_count = max(
            0,
            source_frame_count - 2
        )

        period_frame_count = (
            source_frame_count
            + reverse_frame_count
        )

        source_stream = (
            f"v{index}_src"
        )

        pingpong_stream = (
            f"v{index}_pingpong"
        )

        parts = [
            (
                f"[{index}:v]"
                f"scale={width}:{height}:"
                "force_original_aspect_ratio=increase,"
                f"crop={width}:{height},"
                f"fps={fps},"
                f"format={pixel_format},"
                "setsar=1,"
                "settb=AVTB,"
                "setpts=PTS-STARTPTS"
                f"[{source_stream}]"
            )
        ]

        if reverse_frame_count > 0:
            forward_stream = (
                f"v{index}_forward"
            )
            reverse_stream = (
                f"v{index}_reverse"
            )

            parts.extend([
                (
                    f"[{source_stream}]"
                    f"split=2"
                    f"[{forward_stream}]"
                    f"[{reverse_stream}]"
                ),
                (
                    f"[{reverse_stream}]"
                    "reverse,"
                    "trim=start_frame=1:"
                    f"end_frame={source_frame_count - 1},"
                    "setpts=PTS-STARTPTS"
                    f"[{reverse_stream}_trimmed]"
                ),
                (
                    f"[{forward_stream}]"
                    f"[{reverse_stream}_trimmed]"
                    "concat=n=2:v=1:a=0"
                    f"[{pingpong_stream}_period]"
                ),
                (
                    f"[{pingpong_stream}_period]"
                    "loop=loop=-1:"
                    f"size={period_frame_count}:"
                    "start=0,"
                    f"trim=duration={duration:.6f},"
                    "setpts=PTS-STARTPTS"
                    f"[{pingpong_stream}]"
                )
            ])
        else:
            parts.append(
                f"[{source_stream}]"
                "loop=loop=-1:"
                f"size={period_frame_count}:"
                "start=0,"
                f"trim=duration={duration:.6f},"
                "setpts=PTS-STARTPTS"
                f"[{pingpong_stream}]"
            )

        motion = self.motion_builder.build(
            image_index=index,
            image_count=image_count,
            image_path=image_path,
            duration=duration,
            width=width,
            height=height,
            fps=fps
        )

        parts.append(
            f"[{pingpong_stream}]"
            f"{motion['filter']},"
            f"trim=duration={duration:.6f},"
            f"fps={fps},"
            f"format={pixel_format},"
            "setsar=1,"
            "settb=AVTB,"
            "setpts=PTS-STARTPTS"
            f"[{stream_name}]"
        )

        return ";".join(
            parts
        )

    def _media_type(
        self,
        media,
        index
    ):
        media_types = getattr(
            media,
            "media_types",
            ()
        )
        if not media_types:
            return "image"
        return str(
            media_types[
                index
            ]
        ).strip().lower()

    def _media_duration(
        self,
        media,
        index
    ):
        media_durations = getattr(
            media,
            "media_durations",
            ()
        )
        if not media_durations:
            return None
        return media_durations[
            index
        ]
