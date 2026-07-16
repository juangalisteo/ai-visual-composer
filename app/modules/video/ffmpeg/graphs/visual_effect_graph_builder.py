from app.modules.video.ffmpeg.graphs.base_graph_builder import (
    BaseGraphBuilder
)
from app.modules.video.ffmpeg.graphs.graph_result import (
    GraphResult
)
from app.modules.video.ffmpeg.graphs.layer_compositor import (
    LayerCompositor
)
from app.shared.progress_logger import (
    ProgressLogger
)


class VisualEffectGraphBuilder(
    BaseGraphBuilder
):

    def __init__(
        self,
        visual_effect_builder
    ):
        self.visual_effect_builder = (
            visual_effect_builder
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
                "efectos visuales."
            )

        if (
            not config.visual_effects.enabled
        ):
            ProgressLogger.info(
                "Efectos visuales: desactivados"
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
            "PREPARANDO EFECTOS VISUALES"
        )

        operations = self._build_operations(
            scene_count=scene_count,
            total_duration=(
                timeline.audio_duration
            ),
            scene_duration=(
                timeline.image_duration
            )
        )

        visual_effect_streams = list(
            graph.visual_effect_streams
        )

        for index, operation in enumerate(
            operations
        ):
            input_index = (
                context.first_visual_effect_input
                + operation["input_position"]
            )

            current_stream, prepared_stream = (
                self.compositor.apply_operation(
                    filter_parts=filter_parts,
                    current_stream=current_stream,
                    operation=operation,
                    input_index=input_index,
                    operation_index=index,
                    source_prefix="fxsrc",
                    output_prefix="fx",
                    width=config.width,
                    height=config.height,
                    fps=config.fps
                )
            )

            visual_effect_streams.append(
                prepared_stream
            )

            ProgressLogger.info(
                f"Efecto visual: {operation['name']} | "
                f"{operation['start_time']:.2f}-"
                f"{operation['end_time']:.2f} s"
            )

        ProgressLogger.info(
            "Efectos visuales aplicados: "
            f"{len(operations)}"
        )

        return GraphResult(
            parts=filter_parts,
            current_stream=current_stream,
            video_streams=graph.video_streams,
            overlay_streams=graph.overlay_streams,
            visual_effect_streams=tuple(
                visual_effect_streams
            )
        )

    def _build_operations(
        self,
        scene_count,
        total_duration,
        scene_duration
    ):
        mode = (
            self.visual_effect_builder.config.mode
        )

        operations = []

        if mode in {
            "overlay",
            "both"
        }:
            operations.extend(
                self._build_repeat_operations(
                    scene_count=scene_count,
                    total_duration=total_duration,
                    scene_duration=scene_duration
                )
            )

        if mode in {
            "transition",
            "both"
        }:
            operations.extend(
                self._build_transition_operations(
                    scene_count=scene_count,
                    total_duration=total_duration,
                    scene_duration=scene_duration
                )
            )

        return sorted(
            operations,
            key=lambda operation: (
                operation["start_time"]
            )
        )

    def _build_repeat_operations(
        self,
        scene_count,
        total_duration,
        scene_duration
    ):
        repeat_mode = (
            self.visual_effect_builder.config.repeat_mode
        )

        if repeat_mode == "full_video":
            effect = self.visual_effect_builder.build(
                scene_index=0,
                scene_count=scene_count
            )

            if effect["effect"] is None:
                return []

            return [
                self._operation(
                    item=effect,
                    start_time=0.0,
                    end_time=total_duration
                )
            ]

        if repeat_mode == "scene":
            operations = []

            for scene_index in range(
                scene_count
            ):
                start_time = (
                    scene_index
                    * scene_duration
                )

                end_time = min(
                    total_duration,
                    start_time
                    + scene_duration
                )

                effect = self.visual_effect_builder.build(
                    scene_index=scene_index,
                    scene_count=scene_count
                )

                if effect["effect"] is None:
                    continue

                operations.append(
                    self._operation(
                        item=effect,
                        start_time=start_time,
                        end_time=end_time
                    )
                )

            return operations

        operations = []
        current_time = 0.0
        interval_index = 0

        while current_time < total_duration:
            effect = self.visual_effect_builder.build(
                scene_index=interval_index,
                scene_count=scene_count
            )

            duration = float(
                effect.get(
                    "duration",
                    self.visual_effect_builder
                    .config
                    .min_seconds
                )
            )

            end_time = min(
                total_duration,
                current_time
                + duration
            )

            if effect["effect"] is not None:
                operations.append(
                    self._operation(
                        item=effect,
                        start_time=current_time,
                        end_time=end_time
                    )
                )

            current_time = end_time
            interval_index += 1

        return operations

    def _build_transition_operations(
        self,
        scene_count,
        total_duration,
        scene_duration
    ):
        operations = []

        for scene_index in range(
            1,
            scene_count
        ):
            effect = self.visual_effect_builder.build(
                scene_index=scene_index,
                scene_count=scene_count
            )

            if effect["effect"] is None:
                continue

            duration = float(
                effect["duration"]
            )

            boundary = (
                scene_index
                * scene_duration
            )

            start_time = max(
                0.0,
                boundary
                - duration / 2
            )

            end_time = min(
                total_duration,
                start_time
                + duration
            )

            operations.append(
                self._operation(
                    item=effect,
                    start_time=start_time,
                    end_time=end_time
                )
            )

        return operations

    def _operation(
        self,
        item,
        start_time,
        end_time
    ):
        return {
            "name": item["effect"],
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
        effect_stream,
        output_stream,
        blend_mode,
        opacity,
        start_time,
        end_time
    ):
        return (
            self.compositor.compose(
                base_stream=base_stream,
                layer_stream=effect_stream,
                output_stream=output_stream,
                blend_mode=blend_mode,
                opacity=opacity,
                start_time=start_time,
                end_time=end_time
            )
        )
