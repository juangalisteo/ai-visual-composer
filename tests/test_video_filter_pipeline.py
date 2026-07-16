from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
import unittest

from app.modules.video.ffmpeg.filter_builder import FilterBuilder
from app.modules.video.ffmpeg.filter_pipeline import FilterPipeline
from app.modules.video.ffmpeg.graphs.graph_result import GraphResult


@dataclass(frozen=True)
class FakeFilterContext:

    first_overlay_input: int = 3
    first_visual_effect_input: int = 3
    overlay_inputs: tuple[Path, ...] = ()
    visual_effect_inputs: tuple[Path, ...] = ()


class FakeLayerBuilder:

    def __init__(
        self
    ):
        self._inputs = ()

    @property
    def inputs(
        self
    ):
        return self._inputs

    def set_inputs(
        self,
        *inputs
    ):
        self._inputs = tuple(
            Path(input_path)
            for input_path in inputs
        )


class FakeStage:

    def __init__(
        self,
        name,
        output_stream,
        video_streams=(),
        overlay_streams=(),
        visual_effect_streams=(),
        on_build=None,
        refresh_layer_inputs=False
    ):
        self.name = name
        self.output_stream = output_stream
        self.video_streams = video_streams
        self.overlay_streams = overlay_streams
        self.visual_effect_streams = (
            visual_effect_streams
        )
        self.on_build = on_build
        self.refresh_layer_inputs = (
            refresh_layer_inputs
        )
        self.seen = []

    def build(
        self,
        graph
    ):
        self.seen.append(
            {
                "current_stream": graph.current_stream,
                "video_streams": graph.video_streams,
                "overlay_streams": graph.overlay_streams,
                "visual_effect_streams": (
                    graph.visual_effect_streams
                ),
                "first_visual_effect_input": (
                    graph.context
                    .first_visual_effect_input
                )
            }
        )

        if self.on_build is not None:
            self.on_build()

        return GraphResult(
            parts=(
                graph.filter_parts
                + [
                    self.name
                ]
            ),
            current_stream=self.output_stream,
            video_streams=self.video_streams,
            overlay_streams=self.overlay_streams,
            visual_effect_streams=(
                self.visual_effect_streams
            )
        )


class FilterPipelineTest(
    unittest.TestCase
):

    def test_pipeline_runs_stages_in_order_and_updates_graph(
        self
    ):
        overlay_builder = FakeLayerBuilder()
        visual_effect_builder = FakeLayerBuilder()

        motion = FakeStage(
            name="motion",
            output_stream="[v0]",
            video_streams=(
                "[v0]",
                "[v1]"
            )
        )
        transition = FakeStage(
            name="transition",
            output_stream="[tx]"
        )
        overlay = FakeStage(
            name="overlay",
            output_stream="[ov0]",
            overlay_streams=(
                "[ovsrc0]",
            ),
            refresh_layer_inputs=True,
            on_build=lambda: overlay_builder.set_inputs(
                "overlay.mov"
            )
        )
        visual_effect = FakeStage(
            name="visual_effect",
            output_stream="[fx0]",
            visual_effect_streams=(
                "[fxsrc0]",
            ),
            refresh_layer_inputs=True,
            on_build=lambda: visual_effect_builder.set_inputs(
                "effect.mov"
            )
        )
        fade = FakeStage(
            name="fade",
            output_stream="[fadeout]"
        )
        subtitles = FakeStage(
            name="subtitles",
            output_stream="[vout]"
        )

        result = FilterPipeline(
            context=FakeFilterContext(),
            stages=(
                motion,
                transition,
                overlay,
                visual_effect,
                fade,
                subtitles
            ),
            overlay_builder=overlay_builder,
            visual_effect_builder=visual_effect_builder
        ).run()

        self.assertEqual(
            result.filter_parts,
            [
                "motion",
                "transition",
                "overlay",
                "visual_effect",
                "fade",
                "subtitles"
            ]
        )
        self.assertEqual(
            result.current_stream,
            "[vout]"
        )
        self.assertEqual(
            result.video_streams,
            (
                "[v0]",
                "[v1]"
            )
        )
        self.assertEqual(
            result.overlay_streams,
            (
                "[ovsrc0]",
            )
        )
        self.assertEqual(
            result.visual_effect_streams,
            (
                "[fxsrc0]",
            )
        )
        self.assertEqual(
            visual_effect.seen[0][
                "first_visual_effect_input"
            ],
            4
        )
        self.assertEqual(
            result.context.overlay_inputs,
            (
                Path("overlay.mov"),
            )
        )
        self.assertEqual(
            result.context.visual_effect_inputs,
            (
                Path("effect.mov"),
            )
        )

    def test_filter_builder_stage_order_is_explicit_and_unchanged(
        self
    ):
        stages = FilterBuilder()._stages(
            motion_builder=SimpleNamespace(),
            transition_builder=SimpleNamespace(),
            overlay_builder=SimpleNamespace(
                inputs=()
            ),
            visual_effect_builder=SimpleNamespace(
                inputs=()
            )
        )

        self.assertEqual(
            tuple(
                stage.__class__.__name__
                for stage in stages
            ),
            (
                "MotionGraphBuilder",
                "TransitionGraphBuilder",
                "OverlayGraphBuilder",
                "VisualEffectGraphBuilder",
                "FadeGraphBuilder",
                "SubtitleGraphBuilder"
            )
        )
        self.assertTrue(
            getattr(
                stages[2],
                "refresh_layer_inputs"
            )
        )
        self.assertTrue(
            getattr(
                stages[3],
                "refresh_layer_inputs"
            )
        )


if __name__ == "__main__":
    unittest.main()
