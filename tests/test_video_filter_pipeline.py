from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.modules.video.ffmpeg.filter_builder import FilterBuilder
from app.modules.video.ffmpeg.filter_pipeline import FilterPipeline
from app.modules.video.ffmpeg.graphs.graph_result import GraphResult
from app.modules.video.ffmpeg.graphs.motion_graph_builder import (
    MotionGraphBuilder
)


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

    def test_filter_builder_omits_only_subtitle_stage_when_disabled(self):
        stages = FilterBuilder()._stages(
            motion_builder=SimpleNamespace(),
            transition_builder=SimpleNamespace(),
            overlay_builder=SimpleNamespace(inputs=()),
            visual_effect_builder=SimpleNamespace(inputs=()),
            render_subtitles=False,
        )

        self.assertEqual(
            tuple(stage.__class__.__name__ for stage in stages),
            (
                "MotionGraphBuilder",
                "TransitionGraphBuilder",
                "OverlayGraphBuilder",
                "VisualEffectGraphBuilder",
                "FadeGraphBuilder",
            ),
        )
        self.assertEqual("[vout]", stages[-1].output_stream)

    def test_motion_graph_applies_i2v_transform_to_raw_video_clips(
        self
    ):
        class MotionBuilderSpy:

            def __init__(
                self
            ):
                self.calls = []

            def build(
                self,
                **kwargs
            ):
                self.calls.append(
                    kwargs
                )
                return {
                    "type": "zoom_in",
                    "filter": (
                        "scale=672:378:"
                        "force_original_aspect_ratio=increase,"
                        "crop=672:378,"
                        "format=yuv444p,"
                        "zoompan=z='1':x='0':y='0':"
                        "d=1:s=672x378:fps=24,"
                        "scale=640:360:flags=lanczos"
                    ),
                    "duration": kwargs[
                        "duration"
                    ],
                    "frame_count": 96
                }

        context = SimpleNamespace(
            media=SimpleNamespace(
                image_paths=(
                    Path("scene_001.mp4"),
                ),
                media_types=(
                    "video",
                ),
                media_durations=(
                    2.0,
                )
            ),
            timeline=SimpleNamespace(
                image_duration=4.0
            ),
            config=SimpleNamespace(
                transitions=SimpleNamespace(
                    enabled=False,
                    duration=0.4
                ),
                width=640,
                height=360,
                fps=24,
                pixel_format="yuv420p"
            )
        )
        graph = SimpleNamespace(
            context=context,
            filter_parts=[]
        )

        motion_builder = MotionBuilderSpy()

        with patch(
            "app.modules.video.ffmpeg.graphs.motion_graph_builder"
            ".MediaProbe.get_video_frame_count",
            return_value=48,
        ):
            result = MotionGraphBuilder(
                motion_builder
            ).build(
                graph
            )

        self.assertEqual(
            result.video_streams,
            (
                "[v0]",
            )
        )
        self.assertIn("trim=duration=4.000000", result.parts[0])
        self.assertIn(
            "fps=24,format=yuv420p",
            result.parts[0]
        )
        self.assertIn("reverse", result.parts[0])
        self.assertIn("loop=loop=-1:size=94:start=0", result.parts[0])
        self.assertNotIn(
            "zoompan",
            result.parts[0]
        )
        self.assertEqual(
            motion_builder.calls,
            []
        )

    def test_motion_graph_keeps_motion_for_static_images(self):
        class MotionBuilderSpy:

            def __init__(self):
                self.calls = []

            def build(self, **kwargs):
                self.calls.append(kwargs)
                return {
                    "filter": "zoompan=z='1':d=1:s=640x360:fps=24",
                }

        context = SimpleNamespace(
            media=SimpleNamespace(
                image_paths=(Path("scene_001.png"),),
                media_types=("image",),
                media_durations=(None,),
            ),
            timeline=SimpleNamespace(image_duration=4.0),
            config=SimpleNamespace(
                transitions=SimpleNamespace(
                    enabled=False,
                    duration=0.4,
                ),
                width=640,
                height=360,
                fps=24,
                pixel_format="yuv420p",
            ),
        )
        result = MotionGraphBuilder(
            MotionBuilderSpy()
        ).build(
            SimpleNamespace(
                context=context,
                filter_parts=[],
            )
        )

        self.assertIn("zoompan", result.parts[0])


if __name__ == "__main__":
    unittest.main()
