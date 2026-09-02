from types import SimpleNamespace
import unittest

from app.modules.video.ffmpeg.graphs.layer_compositor import (
    LayerCompositor
)
from app.modules.video.ffmpeg.graphs.overlay_graph_builder import (
    OverlayGraphBuilder
)
from app.modules.video.ffmpeg.graphs.visual_effect_graph_builder import (
    VisualEffectGraphBuilder
)


class FakeOverlayBuilder:

    def __init__(
        self,
        blend_mode="screen"
    ):
        self.config = SimpleNamespace(
            repeat_mode="full_video",
            min_seconds=1.0
        )
        self.blend_mode = blend_mode

    def build(
        self,
        scene_index,
        scene_count,
        scene_metadata=None
    ):
        return {
            "overlay": "overlay.mov",
            "input_position": 1,
            "blend_mode": self.blend_mode,
            "opacity": 0.5,
            "duration": 2.0
        }


class FakeVisualEffectBuilder:

    def __init__(
        self,
        blend_mode="normal"
    ):
        self.config = SimpleNamespace(
            mode="overlay",
            repeat_mode="full_video",
            min_seconds=1.0
        )
        self.blend_mode = blend_mode

    def build(
        self,
        scene_index,
        scene_count
    ):
        return {
            "effect": "effect.mov",
            "input_position": 2,
            "blend_mode": self.blend_mode,
            "opacity": 0.25,
            "duration": 2.0
        }


def graph_context(
    overlays_enabled=True,
    visual_effects_enabled=True
):
    return SimpleNamespace(
        config=SimpleNamespace(
            width=640,
            height=360,
            fps=24,
            overlays=SimpleNamespace(
                enabled=overlays_enabled
            ),
            visual_effects=SimpleNamespace(
                enabled=visual_effects_enabled
            )
        ),
        timeline=SimpleNamespace(
            audio_duration=4.0,
            image_duration=2.0
        ),
        first_overlay_input=3,
        first_visual_effect_input=5
    )


def graph(
    current_stream="[base]"
):
    return SimpleNamespace(
        context=graph_context(),
        filter_parts=[
            "[0:v]base[base]"
        ],
        current_stream=current_stream,
        video_streams=(
            "[v0]",
            "[v1]"
        ),
        overlay_streams=(),
        visual_effect_streams=()
    )


class LayerCompositorTest(
    unittest.TestCase
):

    def test_prepare_stream_matches_existing_filter(
        self
    ):
        compositor = LayerCompositor()

        self.assertEqual(
            compositor.prepare_stream(
                input_index=3,
                output_stream="[ovsrc0]",
                width=640,
                height=360,
                fps=24,
                start_time=0.0,
                duration=4.0
            ),
            "[3:v]scale=640:360:"
            "force_original_aspect_ratio=increase,"
            "crop=640:360,"
            "fps=24,"
            "format=rgba,"
            "trim=duration=4.000000,"
            "setpts=PTS-STARTPTS+0.000000/TB"
            "[ovsrc0]"
        )

    def test_normal_blend_matches_existing_overlay_filter(
        self
    ):
        compositor = LayerCompositor()

        self.assertEqual(
            compositor.compose(
                base_stream="[base]",
                layer_stream="[ovsrc0]",
                output_stream="[ov0]",
                blend_mode="normal",
                opacity=0.5,
                start_time=0.0,
                end_time=4.0
            ),
            "[ovsrc0]colorchannelmixer=aa=0.500"
            "[alpha_ov0];"
            "[base][alpha_ov0]"
            "overlay=0:0:"
            "format=auto:"
            "enable='between(t,0.000,4.000)'"
            "[ov0]"
        )

    def test_custom_blend_matches_existing_blend_filter(
        self
    ):
        compositor = LayerCompositor()

        self.assertEqual(
            compositor.compose(
                base_stream="[base]",
                layer_stream="[fxsrc0]",
                output_stream="[fx0]",
                blend_mode="add",
                opacity=0.75,
                start_time=1.0,
                end_time=3.0
            ),
            "[base][fxsrc0]"
            "blend=all_mode=addition:"
            "all_opacity=0.750:"
            "enable='between(t,1.000,3.000)'"
            "[fx0]"
        )

    def test_apply_operation_updates_current_stream_and_names(
        self
    ):
        compositor = LayerCompositor()
        parts = []

        current_stream, prepared_stream = (
            compositor.apply_operation(
                filter_parts=parts,
                current_stream="[base]",
                operation={
                    "blend_mode": "screen",
                    "opacity": 0.5,
                    "start_time": 0.0,
                    "end_time": 4.0
                },
                input_index=3,
                operation_index=0,
                source_prefix="ovsrc",
                output_prefix="ov",
                width=640,
                height=360,
                fps=24
            )
        )

        self.assertEqual(
            current_stream,
            "[ov0]"
        )
        self.assertEqual(
            prepared_stream,
            "[ovsrc0]"
        )
        self.assertEqual(
            parts,
            [
                "[3:v]scale=640:360:"
                "force_original_aspect_ratio=increase,"
                "crop=640:360,"
                "fps=24,"
                "format=rgba,"
                "trim=duration=4.000000,"
                "setpts=PTS-STARTPTS+0.000000/TB"
                "[ovsrc0]",
                "[base][ovsrc0]"
                "blend=all_mode=screen:"
                "all_opacity=0.500:"
                "enable='between(t,0.000,4.000)'"
                "[ov0]"
            ]
        )


class LayerGraphBuilderTest(
    unittest.TestCase
):

    def test_overlay_graph_builder_preserves_filter_complex(
        self
    ):
        builder = OverlayGraphBuilder(
            FakeOverlayBuilder(
                blend_mode="screen"
            )
        )

        result = builder.build(
            graph()
        )

        self.assertEqual(
            result.parts,
            [
                "[0:v]base[base]",
                "[4:v]scale=640:360:"
                "force_original_aspect_ratio=increase,"
                "crop=640:360,"
                "fps=24,"
                "format=rgba,"
                "trim=duration=4.000000,"
                "setpts=PTS-STARTPTS+0.000000/TB"
                "[ovsrc0]",
                "[base][ovsrc0]"
                "blend=all_mode=screen:"
                "all_opacity=0.500:"
                "enable='between(t,0.000,4.000)'"
                "[ov0]"
            ]
        )
        self.assertEqual(
            result.current_stream,
            "[ov0]"
        )
        self.assertEqual(
            result.overlay_streams,
            (
                "[ovsrc0]",
            )
        )
        self.assertEqual(
            result.visual_effect_streams,
            ()
        )

    def test_visual_effect_graph_builder_preserves_filter_complex(
        self
    ):
        builder = VisualEffectGraphBuilder(
            FakeVisualEffectBuilder(
                blend_mode="normal"
            )
        )

        result = builder.build(
            graph()
        )

        self.assertEqual(
            result.parts,
            [
                "[0:v]base[base]",
                "[7:v]scale=640:360:"
                "force_original_aspect_ratio=increase,"
                "crop=640:360,"
                "fps=24,"
                "format=rgba,"
                "trim=duration=4.000000,"
                "setpts=PTS-STARTPTS+0.000000/TB"
                "[fxsrc0]",
                "[fxsrc0]colorchannelmixer=aa=0.250"
                "[alpha_fx0];"
                "[base][alpha_fx0]"
                "overlay=0:0:"
                "format=auto:"
                "enable='between(t,0.000,4.000)'"
                "[fx0]"
            ]
        )
        self.assertEqual(
            result.current_stream,
            "[fx0]"
        )
        self.assertEqual(
            result.overlay_streams,
            ()
        )
        self.assertEqual(
            result.visual_effect_streams,
            (
                "[fxsrc0]",
            )
        )

    def test_current_stream_validation_is_preserved(
        self
    ):
        builder = OverlayGraphBuilder(
            FakeOverlayBuilder()
        )

        with self.assertRaisesRegex(
            ValueError,
            "No existe un stream para aplicar overlays"
        ):
            builder.build(
                graph(
                    current_stream=""
                )
            )


if __name__ == "__main__":
    unittest.main()
