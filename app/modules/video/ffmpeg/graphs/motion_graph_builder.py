import time

from app.modules.video.ffmpeg.graphs.base_graph_builder import (
    BaseGraphBuilder
)
from app.modules.video.ffmpeg.graphs.graph_result import GraphResult
from app.modules.video.ffmpeg.i2v_normalizer import (
    I2VClipTransform,
)
from app.modules.video.media.timeline_builder import scene_spans
from app.shared.media_probe import MediaProbe
from app.shared.progress_logger import ProgressLogger


class MotionGraphBuilder(
    BaseGraphBuilder
):

    def __init__(
        self,
        motion_builder,
        i2v_transform=None,
    ):
        self.motion_builder = motion_builder
        self.i2v_transform = (
            i2v_transform
            or I2VClipTransform()
        )

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
        spans = scene_spans(
            timeline,
            image_count
        )

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

            _, motion_duration = spans[
                index
            ]

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
        return self.i2v_transform.build_filter(
            source_frame_count=(
                MediaProbe.get_video_frame_count(
                    image_path
                )
            ),
            duration=duration,
            width=width,
            height=height,
            fps=fps,
            pixel_format=pixel_format,
            input_stream=f"[{index}:v]",
            output_stream=f"[{stream_name}]",
            label_prefix=f"i2v_{index}",
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
