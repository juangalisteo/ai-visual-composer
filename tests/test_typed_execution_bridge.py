from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.core.execution_request import (
    STANDARD_PIPELINE_MODES,
    ApplicationExecutionRequest,
    DesignExecutionRequest,
    StandardExecutionRequest,
    StudioExecutionRequest,
)
from app.core import start
from app.modules.audio.tts_contracts import TtsPause
from app.modules.design import DesignExecutionCoordinator
from app.modules.standard import execution_coordinator as standard
from app.modules.studio import StudioInputMode, StudioVideoAudioSrtPlan
from app.modules.studio.execution_coordinator import StudioExecutionCoordinator
from app.shared.profile_identity import OperationalProfileKey, ProfileComponent
from app.shared.subtitle_profile_identity import SubtitleProfileKey


def _profile_key(component):
    return OperationalProfileKey(
        component=component,
        format="vertical",
        profile_id=f"{component.value}_vertical",
    )


def _subtitle_key():
    return SubtitleProfileKey(
        component=ProfileComponent.STUDIO,
        format="vertical",
        profile_id="subtitulo_studio_vertical_linea_unica",
        family="estandar",
    )


def _project():
    project = Mock()
    project.project_name = "typed bridge"
    project.script_path.return_value = Path("output/typed/guion.txt")
    project.storyboard_path.return_value = Path("output/typed/storyboard.json")
    project.images_manifest_path.return_value = Path(
        "output/typed/images_manifest.json"
    )
    project.final_audio_path.return_value = Path("output/typed/audio/final.mp3")
    project.audio_path.return_value = Path("output/typed/audio/voz.mp3")
    project.subtitle_path.return_value = Path(
        "output/typed/subtitles/subtitulos.srt"
    )
    project.video_path.return_value = Path("output/typed/video/typed.mp4")
    return project


def _telemetry():
    telemetry = Mock()

    def measure_stage(operation, *args, **kwargs):
        return operation(*args, **kwargs), 0.25

    telemetry.measure_stage.side_effect = measure_stage
    return telemetry


def _standard_request(*, pipeline_mode="audio", visual_pipeline="image", **kwargs):
    component = (
        ProfileComponent.VIDEO
        if visual_pipeline == "video"
        else ProfileComponent.IMAGEN
    )
    route = StandardExecutionRequest(
        pipeline_mode=pipeline_mode,
        visual_pipeline=visual_pipeline,
        script_source=kwargs.pop("script_source", "manual"),
        voice_config_id=kwargs.pop("voice_config_id", "piper_davefx"),
        music_category=kwargs.pop("music_category", None),
        overlays_mode=kwargs.pop("overlays_mode", "off"),
        **kwargs,
    )
    return ApplicationExecutionRequest(
        project_name="typed bridge",
        overwrite_project=False,
        operational_profile_key=_profile_key(component),
        subtitle_profile_key=None,
        route=route,
    )


def test_typed_standard_script_uses_request_source():
    project = _project()
    config = Mock()
    config.get_ai_config.return_value = object()
    config.get_profile_config.return_value = object()
    prepared_script = SimpleNamespace(text="Texto manual")
    telemetry = _telemetry()
    request = _standard_request(script_source="manual")

    with patch.object(start, "ProjectManager", return_value=project) as projects, patch.object(
        start, "ConfigManager", return_value=config
    ) as config_manager_class, patch.object(
        standard, "_required_builders", return_value={}
    ), patch.object(
        standard, "_pipeline_telemetry_artifacts", return_value=Mock()
    ), patch.object(
        start._STANDARD_EXECUTION_COORDINATOR, "_pipeline_telemetry", telemetry
    ), patch.object(
        standard.ScriptOperation, "execute", return_value=prepared_script
    ) as execute:
        result = start.run_application(request=request)

    assert result == project.script_path.return_value
    assert execute.call_args.kwargs["source_mode"] == "manual"
    projects.assert_called_once_with(project_name=request.project_name)
    assert config_manager_class.call_args.kwargs["operational_profile_key"] is (
        request.operational_profile_key
    )
    assert config_manager_class.call_args.kwargs["voice_config_id"] == (
        request.route.voice_config_id
    )
    project.setup.assert_called_once_with()


def test_typed_standard_music_category_uses_request_value():
    project = _project()
    config = Mock()
    config.get_ai_config.return_value = object()
    config.get_profile_config.return_value = object()
    telemetry = _telemetry()
    request = _standard_request(
        pipeline_mode="full",
        music_category="calm",
    )

    with patch.object(start, "ProjectManager", return_value=project), patch.object(
        start, "ConfigManager", return_value=config
    ), patch.object(standard, "_required_builders", return_value={"voice": True}), patch.object(
        standard, "_pipeline_telemetry_artifacts", return_value=Mock()
    ), patch.object(
        start._STANDARD_EXECUTION_COORDINATOR, "_pipeline_telemetry", telemetry
    ), patch.object(
        standard.ScriptOperation, "execute", return_value=SimpleNamespace(text="Texto")
    ), patch.object(standard, "VoiceBuilder") as voice_builder, patch.object(
        standard, "MusicSelector"
    ) as music_selector, patch.object(standard, "AudioMixer") as audio_mixer:
        voice_builder.return_value.build.return_value = Path("voz.mp3")
        music_selector.return_value.select.return_value = Path("calm.mp3")
        audio_mixer.return_value.build.return_value = Path("final.mp3")

        result = start.run_application(request=request)

    assert result == Path("final.mp3")
    music_selector.return_value.select.assert_called_once_with("calm")
    voice_builder.assert_called_once_with(config_manager=config)
    voice_builder.return_value.build.assert_called_once_with(
        "Texto",
        output_path=project.audio_path.return_value,
    )
    audio_mixer.return_value.build.assert_called_once_with(
        voice_path=Path("voz.mp3"),
        music_path=Path("calm.mp3"),
        output_path=project.final_audio_path.return_value,
        project=project,
    )


def test_typed_standard_injects_its_explicit_config_into_profile_consumers():
    project = _project()
    profile = object()
    config = Mock()
    config.get_ai_config.return_value = object()
    config.get_profile_config.return_value = profile
    telemetry = _telemetry()
    request = _standard_request(pipeline_mode="full")

    with patch.object(start, "ProjectManager", return_value=project), patch.object(
        start, "ConfigManager", return_value=config
    ), patch.object(
        standard,
        "_required_builders",
        return_value={"storyboard": True, "images": True, "video": True},
    ), patch.object(
        standard, "_pipeline_telemetry_artifacts", return_value=Mock()
    ), patch.object(
        start._STANDARD_EXECUTION_COORDINATOR, "_pipeline_telemetry", telemetry
    ), patch.object(
        standard.ScriptOperation, "execute", return_value=SimpleNamespace(text="Texto")
    ), patch.object(standard, "StoryboardBuilder") as storyboard_builder, patch.object(
        standard, "ImageBuilder"
    ) as image_builder, patch.object(standard, "VideoBuilder") as video_builder:
        storyboard_builder.return_value.build.return_value = Path("storyboard.json")
        image_builder.return_value.build.return_value = Path("images.json")
        video_builder.return_value.build.return_value = Path("final.mp4")

        result = start.run_application(request=request)

    assert result == Path("final.mp4")
    storyboard_builder.assert_called_once_with(
        config_manager=config,
        project=project,
    )
    image_builder.assert_called_once_with(profile=profile, project=project)
    assert video_builder.call_args.kwargs["config_manager"] is config
    assert video_builder.call_args.kwargs["project"] is project
    assert video_builder.call_args.kwargs["overlays_mode"] == "off"


def test_typed_standard_uses_the_request_project_for_subtitle_artifacts():
    project = _project()
    config = Mock()
    config.get_ai_config.return_value = object()
    config.get_profile_config.return_value = object()
    subtitle_key = _subtitle_key()
    config.get_subtitle_profile_by_key.return_value = object()
    telemetry = _telemetry()
    request = ApplicationExecutionRequest(
        project_name="typed bridge",
        overwrite_project=False,
        operational_profile_key=_profile_key(ProfileComponent.IMAGEN),
        subtitle_profile_key=subtitle_key,
        route=StandardExecutionRequest(
            pipeline_mode="full",
            visual_pipeline="image",
            script_source="manual",
            voice_config_id="piper_davefx",
        ),
    )

    with patch.object(start, "ProjectManager", return_value=project), patch.object(
        start, "ConfigManager", return_value=config
    ), patch.object(
        standard, "_required_builders", return_value={"voice": True, "subtitles": True}
    ), patch.object(
        standard, "_required_render_fps", return_value=30
    ), patch.object(
        standard, "_pipeline_telemetry_artifacts", return_value=Mock()
    ), patch.object(
        start._STANDARD_EXECUTION_COORDINATOR, "_pipeline_telemetry", telemetry
    ), patch.object(
        standard.ScriptOperation, "execute", return_value=SimpleNamespace(text="Texto")
    ), patch.object(standard, "VoiceBuilder") as voice_builder, patch.object(
        standard, "AudioMixer"
    ) as audio_mixer, patch.object(standard, "SubtitleBuilder") as subtitle_builder, patch.object(
        standard, "SrtOptimizer"
    ) as optimizer:
        voice_builder.return_value.build.return_value = project.audio_path.return_value
        voice_builder.return_value.last_pauses = (
            TtsPause(1.0, 1.5),
            TtsPause(3.25, 3.75),
        )
        audio_mixer.return_value.build.return_value = project.final_audio_path.return_value
        subtitle_builder.return_value.build.return_value = project.subtitle_path.return_value
        optimizer.return_value.optimize.return_value = project.subtitle_path.return_value

        result = start.run_application(request=request)

    assert result == project.subtitle_path.return_value
    subtitle_builder.return_value.build.assert_called_once_with(
        audio_path=project.audio_path.return_value,
        output_path=project.subtitle_path.return_value,
        voice_pauses=((1.0, 1.5), (3.25, 3.75)),
    )
    assert optimizer.call_args.kwargs["project"] is project


def _storyboard_build_options(pipeline_mode):
    project = _project()
    config = Mock()
    config.get_ai_config.return_value = object()
    config.get_profile_config.return_value = object()
    config.get_subtitle_profile_by_key.return_value = object()
    telemetry = _telemetry()
    request = ApplicationExecutionRequest(
        project_name="typed bridge",
        overwrite_project=False,
        operational_profile_key=_profile_key(ProfileComponent.IMAGEN),
        subtitle_profile_key=_subtitle_key(),
        route=StandardExecutionRequest(
            pipeline_mode=pipeline_mode,
            visual_pipeline="image",
            script_source="manual",
            voice_config_id="piper_davefx",
        ),
    )

    with patch.object(start, "ProjectManager", return_value=project), patch.object(
        start, "ConfigManager", return_value=config
    ), patch.object(
        standard,
        "_required_builders",
        return_value={"voice": True, "subtitles": True, "storyboard": True},
    ), patch.object(
        standard, "_required_render_fps", return_value=30
    ), patch.object(
        standard, "_pipeline_telemetry_artifacts", return_value=Mock()
    ), patch.object(
        start._STANDARD_EXECUTION_COORDINATOR, "_pipeline_telemetry", telemetry
    ), patch.object(
        standard.ScriptOperation, "execute", return_value=SimpleNamespace(text="Texto")
    ), patch.object(standard, "VoiceBuilder") as voice_builder, patch.object(
        standard, "AudioMixer"
    ), patch.object(standard, "SubtitleBuilder") as subtitle_builder, patch.object(
        standard, "SrtOptimizer"
    ), patch.object(standard, "StoryboardBuilder") as storyboard_builder, patch.object(
        standard, "VideoBuilder"
    ):
        voice_builder.return_value.build.return_value = project.audio_path.return_value
        voice_builder.return_value.last_pauses = (
            TtsPause(1.0, 1.5),
            TtsPause(3.25, 3.75),
        )
        subtitle_builder.return_value.build.return_value = Path(
            "output/typed/subtitles/whisper.srt"
        )

        start.run_application(request=request)

    storyboard_builder.return_value.build.assert_called_once()
    return storyboard_builder.return_value.build.call_args.kwargs


def test_typed_standard_storyboard_takes_the_whisper_times_of_this_run():
    assert _storyboard_build_options("storyboard") == {
        "subtitle_path": Path("output/typed/subtitles/whisper.srt"),
        "voice_pauses": ((1.0, 1.5), (3.25, 3.75)),
    }


def test_typed_standard_storyboard_without_subtitles_takes_the_voice_pauses():
    assert _storyboard_build_options("full_without_subtitles") == {
        "subtitle_path": None,
        "voice_pauses": ((1.0, 1.5), (3.25, 3.75)),
    }


def test_typed_standard_voice_config_id_is_injected_into_config_manager():
    project = _project()
    config = Mock()
    config.get_ai_config.return_value = object()
    config.get_profile_config.return_value = object()
    telemetry = _telemetry()
    request = _standard_request(
        pipeline_mode="audio",
        voice_config_id="test_voice_selected",
    )

    with patch.object(start, "ProjectManager", return_value=project), patch.object(
        start, "ConfigManager", return_value=config
    ) as config_manager_class, patch.object(
        standard, "_required_builders", return_value={"voice": True}
    ), patch.object(
        standard, "_pipeline_telemetry_artifacts", return_value=Mock()
    ), patch.object(
        start._STANDARD_EXECUTION_COORDINATOR, "_pipeline_telemetry", telemetry
    ), patch.object(
        standard.ScriptOperation, "execute", return_value=SimpleNamespace(text="Texto")
    ), patch.object(standard, "VoiceBuilder") as voice_builder, patch.object(
        standard, "AudioMixer"
    ) as audio_mixer:
        voice_builder.return_value.build.return_value = project.audio_path.return_value
        audio_mixer.return_value.build.return_value = project.final_audio_path.return_value

        result = start.run_application(request=request)

    assert result == project.final_audio_path.return_value
    config_manager_class.assert_called_once_with(
        operational_profile_key=request.operational_profile_key,
        voice_config_id="test_voice_selected",
    )
    voice_builder.assert_called_once_with(config_manager=config)
    voice_builder.return_value.build.assert_called_once_with(
        "Texto",
        output_path=project.audio_path.return_value,
    )


def test_typed_standard_summary_shows_storyboard_metrics_only_with_storyboard():
    cases = (
        ("audio", {"voice": False, "storyboard": True}, False, False),
        ("audio", {"voice": True, "storyboard": True}, False, True),
        ("subtitles", {"voice": True, "storyboard": True}, False, True),
        ("storyboard", {"voice": True, "storyboard": False}, False, True),
        ("storyboard", {"voice": True, "storyboard": True}, True, True),
    )
    for pipeline_mode, builders, expected, expected_duration in cases:
        project = _project()
        config = Mock()
        config.get_ai_config.return_value = object()
        config.get_profile_config.return_value = object()
        telemetry = _telemetry()

        with patch.object(start, "ProjectManager", return_value=project), patch.object(
            start, "ConfigManager", return_value=config
        ), patch.object(
            standard, "_required_builders", return_value=builders
        ), patch.object(
            standard, "_pipeline_telemetry_artifacts", return_value=Mock()
        ), patch.object(
            start._STANDARD_EXECUTION_COORDINATOR, "_pipeline_telemetry", telemetry
        ), patch.object(
            standard.ScriptOperation, "execute", return_value=SimpleNamespace(text="Texto")
        ), patch.object(standard, "VoiceBuilder"), patch.object(
            standard, "AudioMixer"
        ), patch.object(standard, "StoryboardBuilder"):
            start.run_application(
                request=_standard_request(pipeline_mode=pipeline_mode)
            )

        summary = telemetry.complete.call_args.kwargs["summary"]
        assert summary.include_visual_metrics is expected, pipeline_mode
        assert summary.include_media_duration is expected_duration, pipeline_mode


def test_standard_stage_table_ends_every_standard_mode():
    assert set(standard._LAST_STAGE_BY_PIPELINE_MODE) == set(
        STANDARD_PIPELINE_MODES
    )


def test_typed_standard_voice_requires_voice_config_id():
    project = _project()
    config = Mock()
    config.get_ai_config.return_value = object()
    config.get_profile_config.return_value = object()
    telemetry = _telemetry()
    request = ApplicationExecutionRequest(
        project_name="typed bridge",
        overwrite_project=False,
        operational_profile_key=_profile_key(ProfileComponent.IMAGEN),
        subtitle_profile_key=None,
        route=StandardExecutionRequest(
            pipeline_mode="audio",
            visual_pipeline="image",
            script_source="manual",
        ),
    )

    with patch.object(start, "ProjectManager", return_value=project), patch.object(
        start, "ConfigManager", return_value=config
    ), patch.object(standard, "_required_builders", return_value={"voice": True}), patch.object(
        standard, "_pipeline_telemetry_artifacts", return_value=Mock()
    ), patch.object(
        start._STANDARD_EXECUTION_COORDINATOR, "_pipeline_telemetry", telemetry
    ), patch.object(
        standard.ScriptOperation, "execute", return_value=SimpleNamespace(text="Texto")
    ), patch.object(standard, "VoiceBuilder") as voice_builder:
        try:
            start.run_application(request=request)
        except ValueError as error:
            assert str(error) == (
                "Generar la voz requiere voice_config_id."
            )
        else:
            raise AssertionError("La ruta estándar aceptó una voz sin voice_config_id.")

    voice_builder.assert_not_called()


def test_typed_video_uses_request_visual_pipeline_and_operational_key():
    project = _project()
    config = Mock()
    config.get_ai_config.return_value = object()
    config.get_profile_config.return_value = object()
    telemetry = _telemetry()
    request = _standard_request(
        pipeline_mode="full",
        visual_pipeline="video",
    )
    manifest = Path("output/typed/video_clips_manifest.json")
    final_video = Path("output/typed/video/final.mp4")

    with patch.object(start, "ProjectManager", return_value=project), patch.object(
        start, "ConfigManager", return_value=config
    ) as config_manager_class, patch.object(
        standard, "_required_builders", return_value={}
    ), patch.object(
        standard, "_pipeline_telemetry_artifacts", return_value=Mock()
    ), patch.object(
        start._STANDARD_EXECUTION_COORDINATOR, "_pipeline_telemetry", telemetry
    ), patch.object(
        standard.ScriptOperation, "execute", return_value=SimpleNamespace(text="Texto")
    ), patch.object(
        standard, "generate_video_clips", return_value=manifest
    ) as generate_i2v, patch.object(
        standard, "build_public_video", return_value=final_video
    ), patch.object(standard, "VideoBuilder") as video_builder:
        result = start.run_application(request=request)

    assert result == final_video
    assert generate_i2v.call_args.kwargs["profile_key"] is request.operational_profile_key
    assert config_manager_class.call_args.kwargs["operational_profile_key"] is (
        request.operational_profile_key
    )
    config.get_operational_profile_key.assert_not_called()
    assert video_builder.call_args.kwargs["overlays_mode"] == "off"


def test_typed_design_image_dispatches_only_to_design_image():
    project = _project()
    request = ApplicationExecutionRequest(
        project_name="typed bridge",
        overwrite_project=False,
        operational_profile_key=_profile_key(ProfileComponent.IMAGEN),
        subtitle_profile_key=None,
        route=DesignExecutionRequest(mode="design_image"),
    )

    with patch.object(start, "ProjectManager", return_value=project) as projects, patch.object(
        DesignExecutionCoordinator, "run_image", return_value=Path("images.json")
    ) as run_image, patch.object(DesignExecutionCoordinator, "run_video") as run_video:
        result = start.run_application(request=request)

    assert result == Path("images.json")
    assert run_image.call_args.kwargs["project"] is project
    projects.assert_called_once_with(project_name=request.project_name)
    project.setup.assert_not_called()
    run_video.assert_not_called()


def test_typed_design_video_transports_the_existing_operational_key():
    project = _project()
    operational_profile_key = _profile_key(ProfileComponent.VIDEO)
    request = ApplicationExecutionRequest(
        project_name="typed bridge",
        overwrite_project=False,
        operational_profile_key=operational_profile_key,
        subtitle_profile_key=None,
        route=DesignExecutionRequest(mode="design_video"),
    )

    with patch.object(start, "ProjectManager", return_value=project) as projects, patch.object(
        DesignExecutionCoordinator, "run_video", return_value=Path("scene_001.mkv")
    ) as run_video:
        result = start.run_application(request=request)

    assert result == Path("scene_001.mkv")
    assert run_video.call_args.kwargs["profile_key"] is operational_profile_key
    assert (
        run_video.call_args.kwargs["config_manager"]
        .get_operational_profile_key()
        is operational_profile_key
    )
    projects.assert_called_once_with(project_name=request.project_name)
    project.setup.assert_not_called()


def test_typed_studio_standard_preserves_paths_and_subtitle_key():
    subtitle_profile_key = _subtitle_key()
    request = ApplicationExecutionRequest(
        project_name="typed studio",
        overwrite_project=False,
        operational_profile_key=_profile_key(ProfileComponent.STUDIO),
        subtitle_profile_key=subtitle_profile_key,
        route=StudioExecutionRequest(
            input_mode=StudioInputMode.SRT_VIDEO,
            video_path=Path("input/source.mp4"),
            subtitle_path=Path("input/source.srt"),
        ),
    )

    project = _project()
    with patch.object(start, "ProjectManager", return_value=project) as projects, patch.object(
        StudioExecutionCoordinator, "run_standard", return_value="studio-result"
    ) as execute:
        result = start.run_application(request=request)

    assert result == "studio-result"
    assert execute.call_args.kwargs["music_path"] is None
    assert execute.call_args.kwargs["input_mode"] == "srt_video"
    assert execute.call_args.kwargs["subtitle_profile_key"] is subtitle_profile_key
    assert execute.call_args.kwargs["video_path"] == Path("input/source.mp4")
    assert execute.call_args.kwargs["subtitle_path"] == Path("input/source.srt")
    assert (
        execute.call_args.kwargs["config_manager"]
        .get_operational_profile_key()
        is request.operational_profile_key
    )
    projects.assert_called_once_with(project_name=request.project_name)
    project.setup.assert_called_once_with()
    assert execute.call_args.kwargs["project"] is project


def test_typed_studio_plan_is_delegated_without_reconstruction():
    plan = StudioVideoAudioSrtPlan(
        video_path=Path("input/source.mp4"),
        audio_path=Path("input/source.mp3"),
    )
    subtitle_profile_key = _subtitle_key()
    request = ApplicationExecutionRequest(
        project_name="typed studio",
        overwrite_project=False,
        operational_profile_key=_profile_key(ProfileComponent.STUDIO),
        subtitle_profile_key=subtitle_profile_key,
        route=StudioExecutionRequest(
            input_mode=StudioInputMode.VIDEO_AUDIO_SRT,
            plan=plan,
        ),
    )

    project = _project()
    with patch.object(start, "ProjectManager", return_value=project) as projects, patch.object(
        StudioExecutionCoordinator, "run_video_audio_srt", return_value="video-audio"
    ) as execute:
        result = start.run_application(request=request)

    assert result == "video-audio"
    assert execute.call_args.args == (plan,)
    assert execute.call_args.kwargs["subtitle_profile_key"] is subtitle_profile_key
    assert execute.call_args.kwargs["project"] is project
    projects.assert_called_once_with(project_name=request.project_name)
    assert (
        execute.call_args.kwargs["config_manager"]
        .get_operational_profile_key()
        is request.operational_profile_key
    )
