from pathlib import Path
from unittest.mock import Mock

from app.controllers.run_controller import RunController


def test_run_controller_delegates_all_phase_five_studio_routes():
    export_selection = Mock()
    video_audio_selection = Mock()
    montage_selection = Mock()
    intro_outro_route_selection = Mock()
    input_selection = Mock()
    export_plan = Mock()
    combined_plan = Mock()
    montage_plan = Mock()
    intro_outro_plan = Mock()
    prepared_input = Mock()
    video_path = Path("input/studio/video_audio_srt/video.mp4")
    audio_path = Path("input/studio/video_audio_srt/audio.mp3")
    subtitle_path = Path("input/studio/video_audio_srt/subtitle.srt")
    candidates = Mock()
    profile_key = Mock()
    profile = Mock()
    input_mode = "video"
    export_mode = Mock()
    export_selection.select_plan.return_value = export_plan
    video_audio_selection.select_inputs.return_value = (video_path, audio_path)
    video_audio_selection.select_subtitle.return_value = subtitle_path
    video_audio_selection.select_plan.return_value = combined_plan
    video_audio_selection.select_audio_tail.return_value = combined_plan
    montage_selection.select_plan.return_value = montage_plan
    montage_selection.select_order.return_value = (Mock(),)
    intro_outro_route_selection.select_plan.return_value = intro_outro_plan
    input_selection.select_files.return_value = prepared_input
    controller = RunController(
        studio_export_selection=export_selection,
        studio_video_audio_srt_selection=video_audio_selection,
        studio_montage_selection=montage_selection,
        studio_intro_outro_route_selection=intro_outro_route_selection,
        studio_input_selection=input_selection,
    )
    writer = Mock()
    selector = Mock()
    controller._print = writer
    controller._select_from_list = selector

    assert controller.select_studio_subtitle_export_plan(export_mode) is export_plan
    assert controller.select_studio_video_audio_srt_inputs() == (
        video_path,
        audio_path,
    )
    assert controller.select_studio_video_audio_srt_subtitle() == subtitle_path
    assert controller.select_studio_video_audio_srt_audio_tail(combined_plan) is (
        combined_plan
    )
    assert controller._select_studio_montage_order(candidates) == (
        montage_selection.select_order.return_value
    )

    select_inputs = Mock(return_value=(video_path, audio_path))
    select_subtitle = Mock(return_value=subtitle_path)
    select_order = Mock(return_value=(Mock(),))
    select_transitions = Mock(return_value=True)
    require_assets = Mock(return_value=(Path("intro.mp4"),))
    select_asset = Mock(return_value=Path("intro.mp4"))
    controller.select_studio_video_audio_srt_inputs = select_inputs
    controller.select_studio_video_audio_srt_subtitle = select_subtitle
    controller._select_studio_montage_order = select_order
    controller.select_studio_montage_transitions = select_transitions
    controller._require_intro_outro_assets = require_assets
    controller._select_intro_outro_asset = select_asset

    assert controller.select_studio_video_audio_srt_plan(
        True,
        video_path=video_path,
        audio_path=audio_path,
        subtitle_path=subtitle_path,
    ) is combined_plan
    assert controller.select_studio_montage_plan(profile_key, profile) is montage_plan
    assert controller.select_studio_intro_outro_plan(profile_key) is intro_outro_plan
    assert controller.select_studio_input_files(profile, input_mode) is prepared_input

    common = {"writer": writer, "selector": selector}
    export_selection.select_plan.assert_called_once_with(export_mode, **common)
    video_audio_selection.select_inputs.assert_called_once_with(**common)
    video_audio_selection.select_subtitle.assert_called_once_with(**common)
    video_audio_selection.select_plan.assert_called_once_with(
        True,
        video_path=video_path,
        audio_path=audio_path,
        subtitle_path=subtitle_path,
        select_inputs=select_inputs,
        select_subtitle=select_subtitle,
    )
    video_audio_selection.select_audio_tail.assert_called_once_with(
        combined_plan,
        **common,
    )
    montage_selection.select_plan.assert_called_once_with(
        profile_key,
        profile,
        select_order=select_order,
        select_transitions=select_transitions,
        writer=writer,
    )
    intro_outro_route_selection.select_plan.assert_called_once_with(
        profile_key,
        require_assets=require_assets,
        select_asset=select_asset,
        **common,
    )
    input_selection.select_files.assert_called_once_with(
        profile,
        input_mode,
        **common,
    )
