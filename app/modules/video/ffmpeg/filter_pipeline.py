from dataclasses import replace

from app.modules.video.ffmpeg.graphs.graph_context import (
    GraphContext
)


class FilterPipeline:

    def __init__(
        self,
        context,
        stages,
        overlay_builder,
        visual_effect_builder
    ):
        self.context = context
        self.stages = tuple(
            stages
        )
        self.overlay_builder = overlay_builder
        self.visual_effect_builder = (
            visual_effect_builder
        )

    def run(
        self
    ):
        graph = GraphContext(
            context=self.context,
            filter_parts=[]
        )

        context = self.context

        for stage in self.stages:
            result = stage.build(
                graph
            )

            context = self._context_after_stage(
                context=context,
                stage=stage
            )

            graph = self._to_graph(
                context=context,
                result=result,
                previous_graph=graph
            )

        self.context = context

        return graph

    def _context_after_stage(
        self,
        context,
        stage
    ):
        if not getattr(
            stage,
            "refresh_layer_inputs",
            False
        ):
            return context

        return self._refresh_layer_inputs(
            context
        )

    def _refresh_layer_inputs(
        self,
        context
    ):
        overlay_inputs = (
            self.overlay_builder.inputs
        )

        first_visual_effect_input = (
            context.first_overlay_input
            + len(
                overlay_inputs
            )
        )

        return replace(
            context,
            overlay_inputs=overlay_inputs,
            visual_effect_inputs=(
                self.visual_effect_builder.inputs
            ),
            first_visual_effect_input=(
                first_visual_effect_input
            )
        )

    def _to_graph(
        self,
        context,
        result,
        previous_graph
    ):
        return GraphContext(
            context=context,
            filter_parts=result.parts,
            current_stream=(
                result.current_stream
            ),
            video_streams=(
                result.video_streams
                or previous_graph.video_streams
            ),
            overlay_streams=(
                result.overlay_streams
                or previous_graph.overlay_streams
            ),
            visual_effect_streams=(
                result.visual_effect_streams
                or previous_graph.visual_effect_streams
            )
        )
