"""Zoom and pan (``video_style.motion``) are only read for still images.

The motion builder only acts on still images; a WAN clip gets no added
motion. A montage of video clips neither needs nor reads the block, so the
VIDEO profile (which only montages clips) does not declare it (I5b, N2).
"""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.modules.video.config.loaders.motion_loader import MotionConfigLoader
from app.modules.video.ffmpeg.graphs.motion_graph_builder import (
    MotionGraphBuilder,
)
from app.modules.video.motion.motion_builder import MotionBuilder
from app.modules.video.video_build_context_factory import (
    VideoBuildContextFactory,
)
from app.modules.video.video_component_factory import VideoComponentFactory
from app.modules.video.video_config import VideoConfigLoader
from app.shared.profile_identity import OperationalProfileKey, ProfileComponent
from app.shared.profile_resolver import ProfileResolver


FORMATS = ("vertical", "horizontal")
STILL_IMAGE_COMPONENTS = (ProfileComponent.GUION, ProfileComponent.IMAGEN)


def _profile(component, profile_format):
    return ProfileResolver().load_operational(
        OperationalProfileKey(
            component,
            profile_format,
            f"{component.value}_{profile_format}",
        )
    )


def _load(profile, **options):
    return VideoConfigLoader(
        subtitle_profile=None,
        config_manager=SimpleNamespace(
            get_profile_config=lambda: deepcopy(profile),
        ),
    ).load(render_subtitles=False, **options)


@pytest.mark.parametrize("profile_format", FORMATS)
def test_the_video_profile_loads_for_its_clip_montage(profile_format):
    profile = _profile(ProfileComponent.VIDEO, profile_format)

    config = _load(profile, still_images=False)

    assert "motion" not in profile["video_style"]
    assert config.motion is None
    assert config.width == profile["video_style"]["width"]
    assert config.transitions.duration > 0


@pytest.mark.parametrize("profile_format", FORMATS)
def test_a_still_image_montage_requires_motion(profile_format):
    profile = _profile(ProfileComponent.VIDEO, profile_format)

    with pytest.raises(ValueError, match="video_style.motion"):
        _load(profile)


@pytest.mark.parametrize("profile_format", FORMATS)
@pytest.mark.parametrize("component", STILL_IMAGE_COMPONENTS)
def test_still_image_profiles_keep_their_motion(component, profile_format):
    profile = _profile(component, profile_format)

    config = _load(profile)

    assert config.motion == MotionConfigLoader().load(profile)
    assert config.motion.enabled is True


@pytest.mark.parametrize("component", STILL_IMAGE_COMPONENTS)
def test_a_clip_montage_does_not_read_the_motion_block(component):
    # GUION also goes to Video: there its motion block has no effect.
    profile = _profile(component, "vertical")
    profile["video_style"]["motion"]["types"] = ["test_unknown_motion"]

    assert _load(profile, still_images=False).motion is None
    with pytest.raises(ValueError, match="test_unknown_motion"):
        _load(profile)


def _build_context(**build_options):
    project = SimpleNamespace(
        subtitle_path=lambda: Path("test_project.srt"),
        storyboard_path=lambda: Path("test_storyboard.json"),
        images_manifest_path=lambda: Path("test_images.json"),
        video_path=lambda: Path("test_video.mp4"),
    )
    config = SimpleNamespace(
        subtitle_offset=0.0,
        transitions=SimpleNamespace(duration=0.4),
        width=640,
        height=360,
        fps=24,
    )
    media = SimpleNamespace(
        audio_path=Path("test_audio.mp3"),
        subtitle_path=None,
        image_paths=(Path("test_clip.mp4"),),
    )
    module = "app.modules.video.video_build_context_factory"
    with patch(f"{module}.ProjectManager", return_value=project), patch(
        f"{module}.AudioResolver",
    ) as audio_resolver, patch(
        f"{module}.VideoConfigLoader",
    ) as config_loader, patch(
        f"{module}.MediaLoader",
    ) as media_loader, patch(
        f"{module}.TimelineBuilder",
    ) as timeline_builder:
        audio_resolver.return_value.resolve.return_value = Path("test_audio.mp3")
        config_loader.return_value.load.return_value = config
        media_loader.return_value.load.return_value = media
        timeline_builder.return_value.build.return_value = SimpleNamespace(
            audio_duration=4.0,
            image_duration=4.0,
        )
        VideoBuildContextFactory().build(
            audio_path="test_audio.mp3",
            output_path="test_out.mp4",
            render_subtitles=False,
            **build_options,
        )
    return config_loader.return_value.load, media_loader.return_value.load


def test_a_clip_manifest_loads_the_config_without_still_images():
    load, media_load = _build_context(
        video_clips_manifest_path="test_clips.json",
    )

    load.assert_called_once_with(render_subtitles=False, still_images=False)
    assert media_load.call_args.kwargs["media_manifest_type"] == "video_clips"


def test_an_image_manifest_loads_the_config_with_still_images():
    load, media_load = _build_context(images_manifest_path="test_images.json")

    load.assert_called_once_with(render_subtitles=False)
    assert media_load.call_args.kwargs["media_manifest_type"] == "images"


def test_without_motion_settings_there_is_no_motion_builder():
    components = VideoComponentFactory().create(
        SimpleNamespace(
            motion=None,
            overlays=SimpleNamespace(),
            visual_effects=SimpleNamespace(),
        )
    )

    assert components.motion_builder is None


def test_with_motion_settings_the_motion_builder_uses_them():
    motion = MotionConfigLoader().load(
        _profile(ProfileComponent.IMAGEN, "vertical")
    )

    components = VideoComponentFactory().create(
        SimpleNamespace(
            motion=motion,
            overlays=SimpleNamespace(),
            visual_effects=SimpleNamespace(),
        )
    )

    assert isinstance(components.motion_builder, MotionBuilder)
    assert components.motion_builder.config is motion


def test_a_clip_graph_needs_no_motion_builder():
    context = SimpleNamespace(
        media=SimpleNamespace(
            image_paths=(Path("test_scene_001.mp4"),),
            media_types=("video",),
            media_durations=(2.0,),
        ),
        timeline=SimpleNamespace(image_duration=4.0),
        config=SimpleNamespace(
            transitions=SimpleNamespace(enabled=False, duration=0.4),
            width=640,
            height=360,
            fps=24,
            pixel_format="yuv420p",
        ),
    )

    with patch(
        "app.modules.video.ffmpeg.graphs.motion_graph_builder"
        ".MediaProbe.get_video_frame_count",
        return_value=48,
    ):
        result = MotionGraphBuilder(None).build(
            SimpleNamespace(context=context, filter_parts=[])
        )

    assert result.video_streams == ("[v0]",)
    assert "zoompan" not in result.parts[0]
