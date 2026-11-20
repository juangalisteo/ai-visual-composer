"""Each image of the final video lasts what its storyboard scene lasts."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.modules.video.ffmpeg.graphs.motion_graph_builder import (
    MotionGraphBuilder,
)
from app.modules.video.ffmpeg.graphs.overlay_graph_builder import (
    OverlayGraphBuilder,
)
from app.modules.video.ffmpeg.graphs.transition_graph_builder import (
    TransitionGraphBuilder,
)
from app.modules.video.ffmpeg.graphs.visual_effect_graph_builder import (
    VisualEffectGraphBuilder,
)
from app.modules.video.media.media_loader import MediaLoader
from app.modules.video.media.timeline_builder import (
    TimelineBuilder,
    VideoTimeline,
    scene_spans,
)
from app.modules.video.transitions.transition_builder import TransitionBuilder


DURATIONS = (6.6, 7.4, 5.5)


def _timeline(scene_durations=DURATIONS):
    return VideoTimeline(
        audio_duration=sum(DURATIONS),
        image_duration=sum(DURATIONS) / 3,
        subtitle_path=None,
        scene_durations=scene_durations,
    )


def _rounded(spans):
    return [
        (round(start, 6), round(duration, 6))
        for start, duration in spans
    ]


def _build_timeline(audio_duration, scene_durations):
    with patch(
        "app.modules.video.media.timeline_builder.MediaProbe.get_duration",
        return_value=audio_duration,
    ):
        return TimelineBuilder().build(
            audio_path="audio.mp3",
            subtitle_path=None,
            image_count=len(scene_durations),
            subtitle_offset=0.0,
            render_subtitles=False,
            scene_durations=scene_durations,
        )


def test_timeline_takes_the_storyboard_duration_of_each_image():
    timeline = _build_timeline(19.5, (6.6, 7.4, 5.5))

    assert timeline.scene_durations == pytest.approx((6.6, 7.4, 5.5))
    assert timeline.image_duration == pytest.approx(6.5)


def test_last_image_absorbs_the_milliseconds_rounded_in_the_storyboard():
    timeline = _build_timeline(19.512, (6.6, 7.4, 5.5))

    assert timeline.scene_durations == pytest.approx((6.6, 7.4, 5.512))
    assert sum(timeline.scene_durations) == pytest.approx(19.512)


@pytest.mark.parametrize(
    "scene_durations",
    (
        (6.6, None, 5.5),
        (6.6, 7.4),
        (6.6, 7.4, 3.0),
        (),
    ),
)
def test_without_a_duration_for_every_image_the_audio_is_shared_equally(
    scene_durations,
):
    with patch(
        "app.modules.video.media.timeline_builder.MediaProbe.get_duration",
        return_value=19.5,
    ):
        timeline = TimelineBuilder().build(
            audio_path="audio.mp3",
            subtitle_path=None,
            image_count=3,
            subtitle_offset=0.0,
            render_subtitles=False,
            scene_durations=scene_durations,
        )

    assert timeline.scene_durations == ()
    assert _rounded(scene_spans(timeline, 3)) == [
        (0.0, 6.5),
        (6.5, 6.5),
        (13.0, 6.5),
    ]


def test_scene_spans_follow_one_another_from_zero():
    assert _rounded(scene_spans(_timeline(), 3)) == [
        (0.0, 6.6),
        (6.6, 7.4),
        (14.0, 5.5),
    ]
    assert scene_spans(SimpleNamespace(image_duration=2.0), 2) == (
        (0.0, 2.0),
        (2.0, 2.0),
    )


def test_media_loader_reads_the_storyboard_duration_of_each_clip(tmp_path):
    clips = []
    for number in (1, 2, 3):
        clip = tmp_path / f"scene_{number:03d}.mp4"
        clip.write_bytes(b"clip")
        clips.append({"scene": number, "output_clip": str(clip)})
    manifest = tmp_path / "clips.json"
    manifest.write_text(json.dumps(clips), encoding="utf-8")
    storyboard = tmp_path / "storyboard.json"
    storyboard.write_text(
        json.dumps([
            {"scene": 1, "duration": 6.6, "visible_subject": "uno"},
            {"scene": 2, "duration": 0, "visible_subject": "dos"},
            {"scene": 3, "duration": True},
        ]),
        encoding="utf-8",
    )
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"audio")

    media = MediaLoader().load(
        audio_path=audio,
        subtitle_path=None,
        images_manifest_path=manifest,
        output_path=tmp_path / "out.mp4",
        media_manifest_type="video_clips",
        storyboard_path=storyboard,
        render_subtitles=False,
    )

    assert media.scene_durations == (6.6, None, None)
    assert media.scene_metadata == (
        {"visible_subject": "uno"},
        {"visible_subject": "dos"},
        {},
    )


def test_media_loader_reads_the_storyboard_duration_of_each_image(tmp_path):
    images = []
    for number in (2, 1):
        image = tmp_path / f"scene_{number:03d}.png"
        image.write_bytes(b"png")
        images.append({"scene": number, "image": str(image)})
    manifest = tmp_path / "images.json"
    manifest.write_text(json.dumps(images), encoding="utf-8")
    storyboard = tmp_path / "storyboard.json"
    storyboard.write_text(
        json.dumps([
            {"scene": 1, "duration": 6.6},
            {"scene": 2, "duration": 7.4},
        ]),
        encoding="utf-8",
    )
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"audio")

    media = MediaLoader().load(
        audio_path=audio,
        subtitle_path=None,
        images_manifest_path=manifest,
        output_path=tmp_path / "out.mp4",
        storyboard_path=storyboard,
        render_subtitles=False,
    )

    assert media.scene_durations == (7.4, 6.6)


class _MotionBuilder:

    def build(self, **kwargs):
        return {"filter": "zoompan=z='1'"}


def _transitions(enabled):
    return SimpleNamespace(
        enabled=enabled,
        duration=0.4,
        selection="random",
        avoid_repeats=False,
        types=("fade",),
        weights={"fade": 1},
    )


def test_motion_graph_gives_each_image_its_scene_duration():
    graph = SimpleNamespace(
        context=SimpleNamespace(
            media=SimpleNamespace(
                image_paths=tuple(
                    Path(f"scene_{number}.png") for number in (1, 2, 3)
                ),
                media_types=("image",) * 3,
                media_durations=(None,) * 3,
            ),
            timeline=_timeline(),
            config=SimpleNamespace(
                transitions=_transitions(True),
                width=640,
                height=360,
                fps=24,
                pixel_format="yuv420p",
            ),
        ),
        filter_parts=[],
    )

    result = MotionGraphBuilder(_MotionBuilder()).build(graph)

    assert [
        part.split("trim=duration=")[1].split(",")[0]
        for part in result.parts
    ] == ["7.000000", "7.800000", "5.500000"]


def test_transitions_start_where_each_scene_starts():
    graph = SimpleNamespace(
        context=SimpleNamespace(
            timeline=_timeline(),
            config=SimpleNamespace(transitions=_transitions(True)),
        ),
        filter_parts=[],
        video_streams=("[v0]", "[v1]", "[v2]"),
    )

    result = TransitionGraphBuilder(TransitionBuilder()).build(graph)

    assert [
        part.split("offset=")[1].split("[")[0]
        for part in result.parts
    ] == ["6.600", "14.000"]


class _LayerBuilder:

    def __init__(self, config):
        self.config = config

    def build(self, scene_index, scene_count, scene_metadata=None):
        return {
            "overlay": f"layer_{scene_index}.mov",
            "effect": f"layer_{scene_index}.mov",
            "input_position": scene_index,
            "blend_mode": "screen",
            "opacity": 0.5,
            "duration": 1.0,
        }


def _layer_graph():
    return SimpleNamespace(
        context=SimpleNamespace(
            config=SimpleNamespace(
                width=640,
                height=360,
                fps=24,
                overlays=SimpleNamespace(enabled=True),
                visual_effects=SimpleNamespace(enabled=True),
            ),
            media=SimpleNamespace(scene_metadata=()),
            timeline=_timeline(),
            first_overlay_input=3,
            first_visual_effect_input=3,
        ),
        filter_parts=["[0:v]base[base]"],
        current_stream="[base]",
        video_streams=("[v0]", "[v1]", "[v2]"),
        overlay_streams=(),
        visual_effect_streams=(),
    )


def _enabled_windows(parts):
    return [
        part.split("enable='between(t,")[1].split(")")[0]
        for part in parts
        if "enable='between" in part
    ]


def test_overlays_per_scene_follow_the_scene_durations():
    builder = _LayerBuilder(SimpleNamespace(repeat_mode="scene"))

    result = OverlayGraphBuilder(builder).build(_layer_graph())

    assert _enabled_windows(result.parts) == [
        "0.000,6.600",
        "6.600,14.000",
        "14.000,19.500",
    ]


def test_visual_effects_per_scene_and_between_scenes_follow_the_scene_durations():
    scene_effects = VisualEffectGraphBuilder(
        _LayerBuilder(SimpleNamespace(mode="overlay", repeat_mode="scene"))
    ).build(_layer_graph())
    transition_effects = VisualEffectGraphBuilder(
        _LayerBuilder(SimpleNamespace(mode="transition", repeat_mode="scene"))
    ).build(_layer_graph())

    assert _enabled_windows(scene_effects.parts) == [
        "0.000,6.600",
        "6.600,14.000",
        "14.000,19.500",
    ]
    assert _enabled_windows(transition_effects.parts) == [
        "6.100,7.100",
        "13.500,14.500",
    ]
