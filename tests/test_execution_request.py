from dataclasses import FrozenInstanceError, fields
from pathlib import Path
import inspect

import pytest

from app.core.execution_request import (
    ApplicationExecutionRequest,
    DesignExecutionRequest,
    StandardExecutionRequest,
    StudioExecutionRequest,
    adapt_legacy_run_options,
)
from app.modules.studio import (
    StudioInputMode,
    StudioIntroOutroPlan,
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
        platform="vertical",
        profile_id=f"{component.value}_vertical",
    )


def _subtitle_key(component=ProfileComponent.VIDEO):
    return SubtitleProfileKey(
        component=component,
        platform="vertical",
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
    with pytest.raises(ValueError, match="no admite"):
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


def test_adapter_converts_current_standard_controller_mapping_without_rebuilding_typed_keys():
    operational_key = _operational_key()
    subtitle_key = _subtitle_key()
    request = adapt_legacy_run_options(
        {
            "pipeline_mode": "full",
            "visual_pipeline": "video",
            "script_source": "generated",
            "operational_profile_key": operational_key,
            "subtitle_profile_key": subtitle_key,
            "voice_config": "piper_davefx",
            "music_category": "random",
            "overlays_mode": "off",
            "project_name": "Puente técnico",
            "clear_output": True,
            "display_name": "No participa",
        }
    )

    assert request.operational_profile_key is operational_key
    assert request.subtitle_profile_key is subtitle_key
    assert isinstance(request.route, StandardExecutionRequest)
    assert request.route.voice_config_id == "piper_davefx"
    assert not hasattr(request, "display_name")


def test_adapter_constructs_operational_key_only_at_the_legacy_boundary():
    request = adapt_legacy_run_options(
        {
            "pipeline_mode": "audio",
            "visual_pipeline": "image",
            "script_source": "generated",
            "profile_component": "imagen",
            "profile_platform": "vertical",
            "profile_id": "imagen_vertical",
            "voice_config": "piper_davefx",
            "music_category": None,
            "overlays_mode": "",
            "project_name": "Audio",
            "clear_output": False,
        }
    )

    assert request.operational_profile_key == _operational_key(ProfileComponent.IMAGEN)
    assert request.route.overlays_mode is None


def test_adapter_preserves_a_legacy_standard_mapping_without_operational_identity():
    request = adapt_legacy_run_options(
        {
            "pipeline_mode": "full",
            "visual_pipeline": "image",
            "script_source": "manual",
            "voice_config": "piper_davefx",
            "music_category": None,
            "project_name": "Compatibilidad",
            "clear_output": False,
        }
    )

    assert request.operational_profile_key is None
    assert request.route.pipeline_mode == "full"


def test_adapter_preserves_studio_plan_and_normalizes_legacy_paths_to_path():
    plan = StudioVideoAudioSrtPlan(
        video_path=Path("input/source.mp4"),
        audio_path=Path("input/audio.mp3"),
    )
    request = adapt_legacy_run_options(
        {
            "pipeline_mode": "studio",
            "studio_input_mode": "video_audio_srt",
            "studio_video_audio_srt_plan": plan,
            "studio_video_path": "input/source.mp4",
            "studio_subtitle_path": "input/source.srt",
            "studio_music_path": "input/music.mp3",
            "profile_component": "studio",
            "profile_platform": "vertical",
            "profile_id": "studio_vertical",
            "project_name": "Studio",
            "clear_output": False,
        }
    )

    assert isinstance(request.route, StudioExecutionRequest)
    assert request.route.plan is plan
    assert request.route.video_path == Path("input/source.mp4")
    assert request.route.subtitle_path == Path("input/source.srt")
    assert request.route.music_path == Path("input/music.mp3")


def test_adapter_ignores_design_target_and_carries_no_legacy_subtitle_fields():
    request = adapt_legacy_run_options(
        {
            "pipeline_mode": "design_image",
            "visual_pipeline": "image",
            "script_source": "manual_design",
            "design_target": "image",
            "profile_component": "imagen",
            "profile_platform": "vertical",
            "profile_id": "imagen_vertical",
            "project_name": "Diseño",
            "clear_output": False,
        }
    )

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


def test_adapter_rejects_legacy_subtitle_string_and_multiple_studio_plans():
    standard_options = {
        "pipeline_mode": "full",
        "visual_pipeline": "video",
        "script_source": "generated",
        "profile_component": "video",
        "profile_platform": "vertical",
        "profile_id": "video_vertical",
        "subtitle_profile_key": "word_by_word",
        "project_name": "Proyecto",
        "clear_output": False,
    }
    with pytest.raises(TypeError, match="SubtitleProfileKey"):
        adapt_legacy_run_options(standard_options)

    video_audio_plan = StudioVideoAudioSrtPlan(
        video_path=Path("input/source.mp4"),
        audio_path=Path("input/audio.mp3"),
    )
    with pytest.raises(ValueError, match="varios planes"):
        adapt_legacy_run_options(
            {
                "pipeline_mode": "studio",
                "studio_input_mode": "video_audio_srt",
                "studio_video_audio_srt_plan": video_audio_plan,
                "studio_intro_outro_plan": object(),
                "profile_component": "studio",
                "profile_platform": "vertical",
                "profile_id": "studio_vertical",
                "project_name": "Studio",
                "clear_output": False,
            }
        )


def test_contract_module_has_no_environment_or_presentation_dependency():
    source = inspect.getsource(__import__("app.core.execution_request", fromlist=["*"]))

    assert "os.environ" not in source
    assert "display_name" not in source
    assert "MC_PROFILE_FAMILY" not in source
    assert "MC_PROFILE_PATH" not in source
    assert "MC_SUBTITLE_CONFIG" not in source
