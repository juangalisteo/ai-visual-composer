from app.modules.video.ffmpeg.graphs.base_graph_builder import (
    BaseGraphBuilder
)
from app.modules.video.ffmpeg.graphs.graph_result import GraphResult
from app.modules.video.ffmpeg.graphs.layer_compositor import (
    LayerCompositor
)
from app.modules.video.media.timeline_builder import scene_spans
from app.shared.progress_logger import ProgressLogger


class OverlayGraphBuilder(
    BaseGraphBuilder
):

    def __init__(
        self,
        overlay_builder
    ):
        self.overlay_builder = (
            overlay_builder
        )
        self.compositor = LayerCompositor()

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

        current_stream = (
            graph.current_stream
        )

        if not current_stream:
            raise ValueError(
                "No existe un stream para aplicar "
                "overlays."
            )

        if not config.overlays.enabled:
            ProgressLogger.info(
                "Overlays: desactivados"
            )

            return GraphResult(
                parts=filter_parts,
                current_stream=current_stream,
                video_streams=graph.video_streams,
                overlay_streams=graph.overlay_streams,
                visual_effect_streams=(
                    graph.visual_effect_streams
                )
            )

        scene_count = len(
            graph.video_streams
        )

        if scene_count <= 0:
            return GraphResult(
                parts=filter_parts,
                current_stream=current_stream,
                video_streams=graph.video_streams,
                overlay_streams=graph.overlay_streams,
                visual_effect_streams=(
                    graph.visual_effect_streams
                )
            )

        ProgressLogger.start(
            "PREPARANDO OVERLAYS"
        )

        operations = self._build_operations(
            scene_count=scene_count,
            total_duration=(
                timeline.audio_duration
            ),
            spans=scene_spans(
                timeline,
                scene_count
            )
        )

        overlay_streams = list(
            graph.overlay_streams
        )

        for index, operation in enumerate(
            operations
        ):
            input_index = (
                context.first_overlay_input
                + operation["input_position"]
            )

            current_stream, prepared_stream = (
                self.compositor.apply_operation(
                    filter_parts=filter_parts,
                    current_stream=current_stream,
                    operation=operation,
                    input_index=input_index,
                    operation_index=index,
                    source_prefix="ovsrc",
                    output_prefix="ov",
                    width=config.width,
                    height=config.height,
                    fps=config.fps,
                    layer_blend=config.layer_blend,
                    output_pixel_format=config.pixel_format
                )
            )

            overlay_streams.append(
                prepared_stream
            )

            ProgressLogger.info(
                f"Overlay: {operation['name']} | "
                f"{operation['start_time']:.2f}-"
                f"{operation['end_time']:.2f} s"
            )

        ProgressLogger.info(
            f"Overlays aplicados: {len(operations)}"
        )

        return GraphResult(
            parts=filter_parts,
            current_stream=current_stream,
            video_streams=graph.video_streams,
            overlay_streams=tuple(
                overlay_streams
            ),
            visual_effect_streams=(
                graph.visual_effect_streams
            )
        )

    def _build_operations(
        self,
        scene_count,
        total_duration,
        spans
    ):
        repeat_mode = (
            self.overlay_builder.config.repeat_mode
        )

        if repeat_mode == "full_video":
            overlay = self.overlay_builder.build(
                scene_index=0,
                scene_count=scene_count
            )

            if overlay["overlay"] is None:
                return []

            return [
                self._operation(
                    item=overlay,
                    start_time=0.0,
                    end_time=total_duration
                )
            ]

        if repeat_mode == "scene":
            operations = []

            for scene_index in range(
                scene_count
            ):
                start_time, scene_duration = spans[
                    scene_index
                ]

                end_time = min(
                    total_duration,
                    start_time
                    + scene_duration
                )

                overlay = self.overlay_builder.build(
                    scene_index=scene_index,
                    scene_count=scene_count
                )

                if overlay["overlay"] is None:
                    continue

                operations.append(
                    self._operation(
                        item=overlay,
                        start_time=start_time,
                        end_time=end_time
                    )
                )

            return operations

        operations = []
        current_time = 0.0
        interval_index = 0

        while current_time < total_duration:
            overlay = self.overlay_builder.build(
                scene_index=interval_index,
                scene_count=scene_count
            )

            duration = float(
                overlay.get(
                    "duration",
                    self.overlay_builder.config.min_seconds
                )
            )

            end_time = min(
                total_duration,
                current_time
                + duration
            )

            if overlay["overlay"] is not None:
                operations.append(
                    self._operation(
                        item=overlay,
                        start_time=current_time,
                        end_time=end_time
                    )
                )

            current_time = end_time
            interval_index += 1

        return operations

    def _operation(
        self,
        item,
        start_time,
        end_time
    ):
        return {
            "name": item["overlay"],
            "input_position": item["input_position"],
            "blend_mode": item["blend_mode"],
            "opacity": item["opacity"],
            "start_time": start_time,
            "end_time": end_time
        }

    def _prepare_stream(
        self,
        input_index,
        output_stream,
        width,
        height,
        fps,
        start_time,
        duration
    ):
        return (
            self.compositor.prepare_stream(
                input_index=input_index,
                output_stream=output_stream,
                width=width,
                height=height,
                fps=fps,
                start_time=start_time,
                duration=duration
            )
        )

    def _compose(
        self,
        base_stream,
        overlay_stream,
        output_stream,
        blend_mode,
        opacity,
        start_time,
        end_time
    ):
        return (
            self.compositor.compose(
                base_stream=base_stream,
                layer_stream=overlay_stream,
                output_stream=output_stream,
                blend_mode=blend_mode,
                opacity=opacity,
                start_time=start_time,
                end_time=end_time
            )
        )
