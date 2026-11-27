"""Reducción controlada de coordinadores de RunController (Fase 8)."""

import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.controllers.interaction.contracts import (
    StudioOperationalSelection,
    StudioProfileSelection,
    StudioSubtitleSelection,
)
from app.controllers.run_controller import RunController
from app.modules.studio import StudioInputMode, StudioVideoAudioSrtPlan
from app.shared.profile_identity import OperationalProfileKey, ProfileComponent
from app.shared.subtitle_profile_identity import SubtitleProfileKey


def _studio_selection():
    operational_key = OperationalProfileKey(
        "studio",
        "vertical",
        "studio_vertical",
    )
    subtitle_key = SubtitleProfileKey(
        "studio",
        "vertical",
        "subtitle_fixture",
        "estandar",
    )
    studio_profile = Mock()
    return StudioProfileSelection(
        operational=StudioOperationalSelection(operational_key, studio_profile),
        subtitle=StudioSubtitleSelection(subtitle_key, True),
    )


def test_profile_coordinators_compose_extracted_operational_and_subtitle_selectors():
    profile_selection = Mock()
    subtitle_selection = Mock()
    operational_key = OperationalProfileKey(
        "imagen",
        "vertical",
        "imagen_vertical",
    )
    operational = {
        "path": Path("config/profiles/imagen/vertical/perfil.json"),
        "profile_key": operational_key,
    }
    subtitle_key = SubtitleProfileKey(
        "imagen",
        "vertical",
        "subtitle_fixture",
        "estandar",
    )
    profile_selection.select_profile_identity.return_value = operational
    subtitle_selection.select_profile_subtitle_profile.return_value = subtitle_key
    controller = RunController(
        profile_selection=profile_selection,
        subtitle_selection=subtitle_selection,
    )
    writer = Mock()
    selector = Mock()
    controller._print = writer
    controller._select_from_list = selector

    result = controller.select_profile("image")

    assert result is operational
    assert result["subtitle_profile_key"] is subtitle_key
    profile_selection.select_profile_identity.assert_called_once_with(
        ProfileComponent.IMAGEN,
        writer=writer,
        selector=selector,
        label=controller._label,
        order=controller._format_order,
    )
    subtitle_selection.select_profile_subtitle_profile.assert_called_once_with(
        ProfileComponent.IMAGEN,
        "vertical",
        writer=writer,
        selector=selector,
        family_label=controller._family_label,
        presentation_families=controller._presentation_families,
    )


def test_studio_coordinator_transports_contract_to_final_options_without_state():
    selection = _studio_selection()
    controller = RunController()
    controller.select_visual_pipeline = Mock(return_value="studio")
    controller.select_studio_input_mode = Mock(
        return_value=StudioInputMode.SRT_VIDEO.value
    )
    controller._select_studio_profile_selection = Mock(return_value=selection)
    controller.select_studio_input_files = Mock(
        return_value=SimpleNamespace(
            video_path=Path("input/studio/srt_video/source.mp4"),
            subtitle_path=Path("input/studio/srt_video/source.srt"),
        )
    )
    controller.select_studio_music = Mock(return_value=None)
    controller.select_studio_intro_outro = Mock(return_value=None)
    controller.ask_project = Mock(return_value=("studio", False))

    request = controller.run()

    assert request.operational_profile_key.component is ProfileComponent.STUDIO
    assert request.operational_profile_key.format == "vertical"
    assert request.operational_profile_key.profile_id == "studio_vertical"
    assert request.subtitle_profile_key.profile_id == "subtitle_fixture"
    assert request.subtitle_profile_key is selection.subtitle.subtitle_key
    assert request.route.subtitle_original is True
    assert request.route.video_path == Path("input/studio/srt_video/source.mp4")
    assert request.route.subtitle_path == Path("input/studio/srt_video/source.srt")
    assert not hasattr(controller, "_active_studio_subtitle_key")
    assert not hasattr(controller, "_active_studio_subtitle_original")


def test_studio_request_carries_explicit_profile_keys():
    selection = _studio_selection()
    controller = RunController()
    controller.select_studio_input_mode = Mock(
        return_value=StudioInputMode.SRT_VIDEO.value
    )
    controller._select_studio_profile_selection = Mock(return_value=selection)
    controller.select_studio_input_files = Mock(
        return_value=SimpleNamespace(
            video_path=Path("input/studio/srt_video/source.mp4"),
            subtitle_path=Path("input/studio/srt_video/source.srt"),
        )
    )
    controller.select_studio_music = Mock(return_value=None)
    controller.select_studio_intro_outro = Mock(return_value=None)
    controller.ask_project = Mock(return_value=("studio", False))

    request = controller._run_studio()

    assert request.operational_profile_key is selection.operational.operational_key
    assert request.subtitle_profile_key is selection.subtitle.subtitle_key

    plan = StudioVideoAudioSrtPlan(
        video_path=Path("input/source.mp4"),
        audio_path=Path("input/audio.mp3"),
    )
    controller._print = Mock()
    controller._select_from_list = Mock(return_value=False)
    controller.select_studio_input_mode = Mock(
        return_value=StudioInputMode.VIDEO_AUDIO_SRT.value
    )
    controller._select_studio_operational_profile = Mock(
        return_value=(selection.operational.operational_key, Mock())
    )
    controller.select_studio_video_audio_srt_inputs = Mock(
        return_value=(plan.video_path, plan.audio_path)
    )
    controller.select_studio_video_audio_srt_plan = Mock(return_value=plan)
    controller.select_studio_video_audio_srt_audio_tail = Mock(return_value=plan)

    request = controller._run_studio()

    assert request.operational_profile_key is selection.operational.operational_key
    assert request.subtitle_profile_key is None


def test_removed_state_has_no_runtime_readers():
    source = inspect.getsource(RunController)

    assert "_active_studio_subtitle_key" not in source
    assert "_active_studio_subtitle_original" not in source
    assert "_active_studio_design_subtitle_key" not in source
    assert "_studio_design_subtitle_key" not in source


def test_profile_coordinator_can_skip_subtitle_selection():
    profile_selection = Mock()
    subtitle_selection = Mock()
    operational = {
        "path": Path("config/profiles/imagen/vertical/perfil.json"),
        "profile_key": OperationalProfileKey(
            "imagen",
            "vertical",
            "imagen_vertical",
        ),
    }
    profile_selection.select_profile_identity.return_value = operational
    controller = RunController(
        profile_selection=profile_selection,
        subtitle_selection=subtitle_selection,
    )

    result = controller.select_profile("image", select_subtitles=False)

    assert result is operational
    assert "subtitle_profile_key" not in result
    subtitle_selection.select_profile_subtitle_profile.assert_not_called()


def _standard_run_controller(*, visual_pipeline, pipeline_mode):
    profile_selection = Mock()
    subtitle_selection = Mock()
    operational_key = OperationalProfileKey(
        "guion" if visual_pipeline == "script" else "imagen",
        "horizontal",
        "dummy_profile",
    )
    profile_selection.select_profile_identity.return_value = {
        "path": Path("config/profiles/dummy_profile.json"),
        "profile_key": operational_key,
    }
    subtitle_selection.select_profile_subtitle_profile.return_value = (
        SubtitleProfileKey(
            operational_key.component,
            "horizontal",
            "test_family",
            "dummy_profile",
        )
    )
    controller = RunController(
        profile_selection=profile_selection,
        subtitle_selection=subtitle_selection,
    )
    controller.select_visual_pipeline = Mock(return_value=visual_pipeline)
    controller.select_script_destination = Mock(return_value="image")
    controller.select_pipeline_mode = Mock(return_value=pipeline_mode)
    controller.select_voice_config = Mock(return_value="test_voice")
    controller.select_music_category = Mock(return_value=None)
    controller.select_overlays_mode = Mock(return_value="off")
    controller.select_intro_outro = Mock(return_value=None)
    controller.ask_project = Mock(return_value=("test project", False))
    return controller, subtitle_selection


@pytest.mark.parametrize(
    ("visual_pipeline", "pipeline_mode"),
    (
        ("script", "audio"),
        ("script", "full_without_subtitles"),
        ("image", "audio"),
        ("video", "audio"),
    ),
)
def test_modes_without_subtitles_do_not_ask_subtitle_profile(
    visual_pipeline,
    pipeline_mode,
):
    controller, subtitle_selection = _standard_run_controller(
        visual_pipeline=visual_pipeline,
        pipeline_mode=pipeline_mode,
    )

    request = controller.run()

    subtitle_selection.select_profile_subtitle_profile.assert_not_called()
    assert request.route.pipeline_mode == pipeline_mode
    assert request.subtitle_profile_key is None


@pytest.mark.parametrize(
    "pipeline_mode",
    ("full", "subtitles", "storyboard"),
)
def test_modes_with_subtitles_still_ask_subtitle_profile(pipeline_mode):
    controller, subtitle_selection = _standard_run_controller(
        visual_pipeline="script",
        pipeline_mode=pipeline_mode,
    )

    request = controller.run()

    subtitle_selection.select_profile_subtitle_profile.assert_called_once()
    assert request.subtitle_profile_key is (
        subtitle_selection.select_profile_subtitle_profile.return_value
    )
