from dataclasses import FrozenInstanceError, fields
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import inspect

import pytest

from app.controllers.interaction.contracts import (
    StudioOperationalSelection,
    StudioProfileSelection,
    StudioSubtitleSelection,
)
from app.controllers.interaction.navigation import Navigation
from app.controllers.run_controller import RunController
from app.core.execution_request import (
    STANDARD_PIPELINE_MODES,
    ApplicationExecutionRequest,
    DesignExecutionRequest,
    StandardExecutionRequest,
    StudioExecutionRequest,
)
from app.modules.studio import (
    StudioInputMode,
    StudioVideoAudioSrtPlan,
)
from app.shared.profile_identity import (
    OperationalProfileKey,
    ProfileComponent,
)
from app.shared.subtitle_profile_identity import SubtitleProfileKey


def _operational_key(component=ProfileComponent.VIDEO):
    return OperationalProfileKey(
        component=component,
        format="vertical",
        profile_id=f"{component.value}_vertical",
    )


def _subtitle_key(component=ProfileComponent.VIDEO):
    return SubtitleProfileKey(
        component=component,
        format="vertical",
        profile_id=f"subtitulo_{component.value}_vertical_linea_unica",
        family="estandar",
    )


def _standard_route():
    return StandardExecutionRequest(
        pipeline_mode="full",
        visual_pipeline="video",
        script_source="generated",
        voice_config_id="piper_davefx",
        music_category="random",
        overlays_mode="off",
    )


def test_standard_execution_request_is_immutable_and_preserves_technical_values():
    request = _standard_route()

    assert request.pipeline_mode == "full"
    assert request.visual_pipeline == "video"
    assert request.script_source == "generated"
    assert request.voice_config_id == "piper_davefx"
    assert request.music_category == "random"
    assert request.overlays_mode == "off"
    with pytest.raises(FrozenInstanceError):
        request.pipeline_mode = "audio"


def test_standard_execution_request_rejects_display_name_as_voice_identity():
    with pytest.raises(ValueError, match="identidad técnica"):
        StandardExecutionRequest(
            pipeline_mode="full",
            visual_pipeline="video",
            script_source="generated",
            voice_config_id="Masculina - Davefx",
        )


@pytest.mark.parametrize("pipeline_mode", ("script", "dummy_mode"))
def test_standard_execution_request_rejects_a_mode_the_menu_does_not_offer(
    pipeline_mode,
):
    with pytest.raises(ValueError, match=f"no admite el modo {pipeline_mode}"):
        StandardExecutionRequest(
            pipeline_mode=pipeline_mode,
            visual_pipeline="image",
            script_source="manual",
        )


def test_standard_execution_request_accepts_exactly_the_modes_the_menu_offers():
    offered = []

    def capture(modes):
        offered.extend(mode["mode"] for mode in modes)
        return modes[0]

    Navigation(None, None).select_pipeline_mode(
        include_full_without_subtitles=True,
        writer=lambda _message: None,
        selector=capture,
    )

    assert tuple(offered) == STANDARD_PIPELINE_MODES
    for pipeline_mode in offered:
        request = StandardExecutionRequest(
            pipeline_mode=pipeline_mode,
            visual_pipeline="image",
            script_source="manual",
        )
        assert request.pipeline_mode == pipeline_mode


def test_studio_execution_request_transports_existing_typed_plan_and_paths():
    plan = StudioVideoAudioSrtPlan(
        video_path=Path("input/source.mp4"),
        audio_path=Path("input/audio.mp3"),
        subtitle_path=Path("input/source.srt"),
    )
    request = StudioExecutionRequest(
        input_mode=StudioInputMode.VIDEO_AUDIO_SRT,
        plan=plan,
        video_path=Path("input/source.mp4"),
        subtitle_path=Path("input/source.srt"),
        music_path=Path("input/music.mp3"),
    )

    assert request.plan is plan
    assert request.input_mode is StudioInputMode.VIDEO_AUDIO_SRT
    assert request.video_path == Path("input/source.mp4")


def test_studio_execution_request_rejects_plan_for_another_input_mode():
    plan = StudioVideoAudioSrtPlan(
        video_path=Path("input/source.mp4"),
        audio_path=Path("input/audio.mp3"),
    )

    with pytest.raises(ValueError, match="no corresponde"):
        StudioExecutionRequest(
            input_mode=StudioInputMode.INTRO_OUTRO,
            plan=plan,
        )


def test_studio_execution_request_rejects_untyped_plan():
    with pytest.raises(TypeError, match="plan"):
        StudioExecutionRequest(
            input_mode=StudioInputMode.SRT_VIDEO,
            plan=object(),
        )


def test_design_execution_request_accepts_only_the_two_design_routes():
    assert DesignExecutionRequest(mode="design_image").mode == "design_image"
    assert DesignExecutionRequest(mode="design_video").mode == "design_video"

    with pytest.raises(ValueError, match="design_image"):
        DesignExecutionRequest(mode="design_target")


def test_application_request_preserves_complete_operational_and_subtitle_keys():
    operational_key = _operational_key()
    subtitle_key = _subtitle_key()
    request = ApplicationExecutionRequest(
        project_name="Proyecto técnico",
        clear_output=False,
        operational_profile_key=operational_key,
        subtitle_profile_key=subtitle_key,
        route=_standard_route(),
    )

    assert request.operational_profile_key is operational_key
    assert request.subtitle_profile_key is subtitle_key
    assert request.route == _standard_route()


def test_application_request_rejects_incoherent_design_identity():
    with pytest.raises(ValueError, match="no corresponde"):
        ApplicationExecutionRequest(
            project_name="Diseño",
            clear_output=False,
            operational_profile_key=_operational_key(ProfileComponent.VIDEO),
            subtitle_profile_key=None,
            route=DesignExecutionRequest(mode="design_image"),
        )


def test_application_request_rejects_a_special_route_in_standard_payload():
    with pytest.raises(ValueError, match="no admite el modo design_video"):
        ApplicationExecutionRequest(
            project_name="Incoherente",
            clear_output=False,
            operational_profile_key=_operational_key(),
            subtitle_profile_key=None,
            route=StandardExecutionRequest(
                pipeline_mode="design_video",
                visual_pipeline="video",
                script_source="manual_design",
            ),
        )


def _menu_controller(
    *,
    profile,
    visual_pipeline="video",
    pipeline_mode="full",
    music_category="random",
    project_name="Proyecto",
    clear_output=False,
):
    controller = RunController()
    controller.select_visual_pipeline = Mock(return_value=visual_pipeline)
    controller.select_pipeline_mode = Mock(return_value=pipeline_mode)
    controller.select_profile = Mock(return_value=profile)
    controller.select_voice_config = Mock(return_value="piper_davefx")
    controller.select_music_category = Mock(return_value=music_category)
    controller.select_overlays_mode = Mock(return_value="off")
    controller.select_intro_outro = Mock(return_value=None)
    controller.ask_project_name = Mock(return_value=project_name)
    controller.ask_clear_output = Mock(return_value=clear_output)
    return controller


def test_run_builds_the_standard_request_without_rebuilding_typed_keys():
    operational_key = _operational_key()
    subtitle_key = _subtitle_key()
    controller = _menu_controller(
        profile={
            "profile_key": operational_key,
            "subtitle_profile_key": subtitle_key,
            "display_name": "No participa",
        },
        project_name="Puente técnico",
        clear_output=True,
    )

    request = controller.run()

    assert request.operational_profile_key is operational_key
    assert request.subtitle_profile_key is subtitle_key
    assert isinstance(request.route, StandardExecutionRequest)
    assert request.route.voice_config_id == "piper_davefx"
    assert not hasattr(request, "display_name")


def test_run_transports_the_selected_operational_key_without_texts():
    operational_key = _operational_key(ProfileComponent.IMAGEN)
    controller = _menu_controller(
        profile={"profile_key": operational_key},
        visual_pipeline="image",
        pipeline_mode="audio",
        music_category=None,
        project_name="Audio",
    )

    request = controller.run()

    assert request.operational_profile_key is operational_key
    assert request.operational_profile_key == _operational_key(ProfileComponent.IMAGEN)
    assert request.route.overlays_mode == "off"
    with pytest.raises(ValueError, match="overlays_mode debe ser texto no vacío"):
        StandardExecutionRequest(
            pipeline_mode="audio",
            visual_pipeline="image",
            script_source="generated",
            overlays_mode="",
        )


def test_request_keeps_a_standard_route_without_operational_identity():
    request = ApplicationExecutionRequest(
        project_name="Compatibilidad",
        clear_output=False,
        operational_profile_key=None,
        subtitle_profile_key=None,
        route=StandardExecutionRequest(
            pipeline_mode="full",
            visual_pipeline="image",
            script_source="manual",
            voice_config_id="piper_davefx",
        ),
    )

    assert request.operational_profile_key is None
    assert request.route.pipeline_mode == "full"


def test_run_studio_keeps_the_typed_plan_and_transports_paths_as_path():
    operational_key = _operational_key(ProfileComponent.STUDIO)
    plan = StudioVideoAudioSrtPlan(
        video_path=Path("input/source.mp4"),
        audio_path=Path("input/audio.mp3"),
    )
    controller = RunController()
    controller._print = Mock()
    controller._select_from_list = Mock(return_value=False)
    controller.select_studio_input_mode = Mock(
        return_value=StudioInputMode.VIDEO_AUDIO_SRT.value
    )
    controller._select_studio_operational_profile = Mock(
        return_value=(operational_key, Mock())
    )
    controller.select_studio_video_audio_srt_inputs = Mock(
        return_value=(plan.video_path, plan.audio_path)
    )
    controller.select_studio_video_audio_srt_plan = Mock(return_value=plan)
    controller.select_studio_video_audio_srt_audio_tail = Mock(return_value=plan)
    controller.ask_project_name = Mock(return_value="Studio")
    controller.ask_clear_output = Mock(return_value=False)

    request = controller._run_studio()

    assert isinstance(request.route, StudioExecutionRequest)
    assert request.route.plan is plan

    controller.select_studio_input_mode = Mock(
        return_value=StudioInputMode.SRT_VIDEO.value
    )
    controller._select_studio_profile_selection = Mock(
        return_value=StudioProfileSelection(
            operational=StudioOperationalSelection(operational_key, Mock()),
            subtitle=StudioSubtitleSelection(
                _subtitle_key(ProfileComponent.STUDIO),
                True,
            ),
        )
    )
    controller.select_studio_input_files = Mock(
        return_value=SimpleNamespace(
            video_path=Path("input/source.mp4"),
            subtitle_path=Path("input/source.srt"),
        )
    )
    controller.select_studio_music = Mock(return_value=Path("input/music.mp3"))
    controller.select_studio_intro_outro = Mock(return_value=None)

    request = controller._run_studio()

    assert request.route.video_path == Path("input/source.mp4")
    assert request.route.subtitle_path == Path("input/source.srt")
    assert request.route.music_path == Path("input/music.mp3")


def test_run_builds_the_design_route_and_carries_no_legacy_subtitle_fields():
    controller = _menu_controller(
        profile={"profile_key": _operational_key(ProfileComponent.IMAGEN)},
        visual_pipeline="script",
        project_name="Diseño",
    )
    controller.select_script_destination = Mock(return_value="design")
    controller.select_design_target = Mock(return_value="image")

    request = controller.run()

    assert isinstance(request.route, DesignExecutionRequest)
    field_names = {
        field.name
        for contract in (
            ApplicationExecutionRequest,
            StandardExecutionRequest,
            StudioExecutionRequest,
            DesignExecutionRequest,
        )
        for field in fields(contract)
    }
    assert "design_target" not in field_names
    assert "subtitle_config" not in field_names
    assert "profile_family" not in field_names
    assert "profile_path" not in field_names


def test_request_rejects_subtitle_string_and_carries_a_single_studio_plan():
    with pytest.raises(TypeError, match="SubtitleProfileKey"):
        ApplicationExecutionRequest(
            project_name="Proyecto",
            clear_output=False,
            operational_profile_key=_operational_key(),
            subtitle_profile_key="word_by_word",
            route=_standard_route(),
        )

    studio_fields = {field.name for field in fields(StudioExecutionRequest)}
    assert "plan" in studio_fields
    assert studio_fields.isdisjoint(
        {
            "studio_video_audio_srt_plan",
            "studio_intro_outro_plan",
            "studio_montage_plan",
            "studio_subtitle_export_plan",
        }
    )


def test_contract_module_has_no_environment_or_presentation_dependency():
    source = inspect.getsource(__import__("app.core.execution_request", fromlist=["*"]))

    assert "os.environ" not in source
    assert "display_name" not in source
    assert "MC_PROFILE_FAMILY" not in source
    assert "MC_PROFILE_PATH" not in source
    assert "MC_SUBTITLE_CONFIG" not in source
