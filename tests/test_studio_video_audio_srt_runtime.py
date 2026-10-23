import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

import pytest
import main

from app.core.start import ejecutar_studio_video_audio_srt
from app.controllers.run_controller import RunController
from app.modules.studio import (
    StudioInputMode,
    StudioProfileLoader,
    StudioVideoAudioSrtInputError,
    StudioVideoAudioSrtInputService,
    StudioVideoAudioSrtPlan,
    StudioVideoAudioSrtService,
)
from app.shared.error_context import ErrorContext, ErrorSeverity, ExitKind
from app.shared.media_probe import MediaInfo
from app.shared.operational_error import OperationalError
from app.shared.profile_identity import OperationalProfileKey
from app.shared.profile_resolver import ProfileResolver
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


class RecordingRunner:

    def __init__(self):
        self.command = None

    def run(self, command):
        self.command = tuple(command)
        Path(command[-1]).write_bytes(b"rendered")


class DurationValidator:

    def __init__(self):
        self.profile = None

    def validate(self, output_path, expected_duration, profile):
        assert Path(output_path).is_file()
        assert profile.max_duration_difference > 0
        self.profile = profile
        return expected_duration


def _media_info(duration):
    return MediaInfo(
        duration=duration,
        width=1920,
        height=1080,
        fps=30.0,
        pixel_format="yuv420p",
        video_codec="h264",
        audio_codec="aac",
        audio_sample_rate=48000,
        audio_channels=2,
    )


STUDIO_YOUTUBE_SUBTITLE_PROFILE_IDS = {
    "single_line": "subtitulo_studio_youtube_linea_unica",
    "word_by_word": "subtitulo_studio_youtube_palabra_por_palabra",
}


def _standard_subtitle_key(style):
    return SubtitleProfileKey(
        "studio",
        "youtube",
        STUDIO_YOUTUBE_SUBTITLE_PROFILE_IDS[style],
        "estandar",
    )


def _profile_and_subtitles():
    operational_key = OperationalProfileKey("studio", "youtube", "studio_youtube")
    profile = StudioProfileLoader().load(
        ProfileResolver().load_operational(operational_key),
        operational_key,
    )
    return operational_key, profile, SubtitleProfileResolver()


def _write_sources(root, with_subtitle=False):
    video = root / "source.mp4"
    audio = root / "new-audio.wav"
    video.write_bytes(b"video-original")
    audio.write_bytes(b"audio-new")
    subtitle = None
    if with_subtitle:
        subtitle = root / "human.srt"
        subtitle.write_text(
            "1\n00:00:00,000 --> 00:00:01,500\nTexto humano intacto.\n",
            encoding="utf-8",
        )
    return video, audio, subtitle


def test_studio_export_menu_label_changes_without_changing_its_mode_id():
    controller = RunController()
    messages = []
    controller._print = messages.append
    controller._select_from_list = Mock(return_value=StudioInputMode.EXPORTAR_SRT.value)

    assert controller.select_studio_input_mode() == StudioInputMode.EXPORTAR_SRT.value
    assert "6. EXPORTAR SRT ➜  VIDEO" in messages


@pytest.mark.parametrize("subtitles", (False, True))
def test_video_audio_srt_menu_uses_operational_platform_and_never_asks_for_music(
    subtitles,
):
    profile_key, _, _ = _profile_and_subtitles()
    planner = Mock()
    controller = RunController(studio_video_audio_srt_input_service=planner)
    controller.select_studio_input_mode = Mock(return_value="video_audio_srt")
    controller._select_studio_operational_profile = Mock(
        return_value=(profile_key, Mock())
    )
    controller._select_from_list = Mock(return_value=subtitles)
    subtitle_key = _standard_subtitle_key("word_by_word")
    controller._select_studio_video_audio_srt_subtitle_profile = Mock(
        return_value=subtitle_key
    )
    video_path = Path("input/studio/video_audio_srt/source.mp4")
    audio_path = Path("input/studio/video_audio_srt/new-audio.wav")
    plan = StudioVideoAudioSrtPlan(video_path, audio_path)
    controller.select_studio_video_audio_srt_inputs = Mock(
        return_value=(video_path, audio_path)
    )
    controller.select_studio_video_audio_srt_subtitle = Mock(
        return_value=Path("input/studio/video_audio_srt/human.srt")
    )
    controller.select_studio_video_audio_srt_plan = Mock(return_value=plan)
    controller.select_studio_video_audio_srt_audio_tail = Mock(return_value=plan)
    controller.select_studio_music = Mock()
    controller.ask_project_name = Mock(return_value="project")
    controller.ask_clear_output = Mock(return_value=False)

    options = controller._run_studio()

    controller.select_studio_video_audio_srt_plan.assert_called_once_with(
        subtitles,
        video_path=video_path,
        audio_path=audio_path,
        subtitle_path=(
            Path("input/studio/video_audio_srt/human.srt")
            if subtitles
            else None
        ),
    )
    assert controller._select_from_list.call_args_list[0].args == ((True, False),)
    controller.select_studio_music.assert_not_called()
    assert "studio_music_path" not in options
    assert "subtitle_config" not in options
    assert ("subtitle_profile_key" in options) is subtitles
    assert "studio_subtitle_original" not in options
    if subtitles:
        controller.select_studio_video_audio_srt_subtitle.assert_called_once_with()
        controller._select_studio_video_audio_srt_subtitle_profile.assert_called_once_with(
            profile_key
        )
    else:
        controller.select_studio_video_audio_srt_subtitle.assert_not_called()
        controller._select_studio_video_audio_srt_subtitle_profile.assert_not_called()


def test_input_requires_required_files_and_ignores_srt_when_disabled():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        service = StudioVideoAudioSrtInputService(root)

        with pytest.raises(StudioVideoAudioSrtInputError, match="MP4"):
            service.create_plan(False)

        video = root / "source.mp4"
        video.write_bytes(b"video")
        with pytest.raises(StudioVideoAudioSrtInputError, match="audio"):
            service.create_plan(False)

        audio = root / "new-audio.wav"
        audio.write_bytes(b"audio")
        (root / "ignored-one.srt").write_text(
            "1\n00:00:00,000 --> 00:00:01,000\nUno\n",
            encoding="utf-8",
        )
        (root / "ignored-two.srt").write_text(
            "1\n00:00:00,000 --> 00:00:01,000\nDos\n",
            encoding="utf-8",
        )
        assert service.create_plan(False) == StudioVideoAudioSrtPlan(video, audio)

        subtitle = root / "ignored-one.srt"
        (root / "ignored-two.srt").unlink()
        assert service.create_plan(True).subtitle_path == subtitle

        subtitle.unlink()
        with pytest.raises(StudioVideoAudioSrtInputError, match="ningun archivo SRT"):
            service.create_plan(True)

        (root / "first.srt").write_text(
            "1\n00:00:00,000 --> 00:00:01,000\nUno\n",
            encoding="utf-8",
        )
        (root / "second.srt").write_text(
            "1\n00:00:00,000 --> 00:00:01,000\nDos\n",
            encoding="utf-8",
        )
        with pytest.raises(StudioVideoAudioSrtInputError, match="seleccionar un archivo SRT"):
            service.create_plan(True)


@pytest.mark.parametrize("srt_count", (0, 1, 3))
def test_disabled_subtitles_ignore_all_srt_cardinalities(srt_count):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        video, audio, _ = _write_sources(root)
        for index in range(srt_count):
            (root / f"ignored-{index}.srt").write_text(
                "SRT deliberadamente invalido para esta rama",
                encoding="utf-8",
            )
        service = StudioVideoAudioSrtInputService(root)
        candidates = Mock(wraps=service._candidates)
        service._candidates = candidates
        service._valid_subtitle_candidates = Mock(
            side_effect=AssertionError("SUBTÍTULOS = No no debe validar SRT")
        )

        plan = service.create_plan(False)

    assert plan == StudioVideoAudioSrtPlan(video, audio)
    assert plan.subtitle_path is None
    service._valid_subtitle_candidates.assert_not_called()
    assert candidates.call_args_list == [
        call((".mp4",)),
        call(service.audio_extensions),
    ]


def test_input_candidates_are_ordered_and_selected_individually():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "zeta.mp4").write_bytes(b"video")
        selected_video = root / "alpha.mp4"
        selected_video.write_bytes(b"video")
        selected_audio = root / "audio-a.flac"
        selected_audio.write_bytes(b"audio")
        (root / "audio-z.mp3").write_bytes(b"audio")
        selected_subtitle = root / "a.srt"
        selected_subtitle.write_text(
            "1\n00:00:00,000 --> 00:00:01,000\nUno\n",
            encoding="utf-8",
        )
        (root / "z.srt").write_text(
            "1\n00:00:00,000 --> 00:00:01,000\nDos\n",
            encoding="utf-8",
        )
        service = StudioVideoAudioSrtInputService(root)
        candidates = service.discover(True)

        assert tuple(path.name for path in candidates.videos) == (
            "alpha.mp4", "zeta.mp4",
        )
        assert tuple(path.name for path in candidates.audios) == (
            "audio-a.flac", "audio-z.mp3",
        )
        assert tuple(path.name for path in candidates.subtitles) == ("a.srt", "z.srt")
        assert service.create_plan(
            True,
            video_path=selected_video,
            audio_path=selected_audio,
            subtitle_path=selected_subtitle,
        ) == StudioVideoAudioSrtPlan(
            selected_video,
            selected_audio,
            selected_subtitle,
        )


def test_video_audio_srt_input_menus_only_appear_for_multiple_candidates():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        video_one = root / "one.mp4"
        video_two = root / "two.mp4"
        audio_one = root / "one.mp3"
        audio_two = root / "two.wav"
        subtitle_one = root / "one.srt"
        subtitle_two = root / "two.srt"
        for path in (video_one, video_two, audio_one, audio_two):
            path.write_bytes(b"media")
        for path in (subtitle_one, subtitle_two):
            path.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\nTexto\n",
                encoding="utf-8",
            )
        controller = RunController(
            studio_video_audio_srt_input_service=StudioVideoAudioSrtInputService(root)
        )
        controller._select_from_list = Mock(
            side_effect=(video_two, audio_one, subtitle_two)
        )

        plan = controller.select_studio_video_audio_srt_plan(True)

        assert plan == StudioVideoAudioSrtPlan(video_two, audio_one, subtitle_two)
        assert controller._select_from_list.call_args_list == [
            call((video_one, video_two)),
            call((audio_one, audio_two)),
            call((subtitle_one, subtitle_two)),
        ]


def test_video_audio_srt_single_candidates_are_selected_without_a_menu():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        video, audio, subtitle = _write_sources(root, with_subtitle=True)
        controller = RunController(
            studio_video_audio_srt_input_service=StudioVideoAudioSrtInputService(root)
        )
        controller._select_from_list = Mock()

        assert controller.select_studio_video_audio_srt_inputs() == (video, audio)
        assert controller.select_studio_video_audio_srt_subtitle() == subtitle
        controller._select_from_list.assert_not_called()


def test_video_audio_srt_without_subtitles_never_discovers_srt():
    planner = Mock()
    planner.discover.return_value = SimpleNamespace(
        videos=(Path("video.mp4"),),
        audios=(Path("audio.mp3"),),
    )
    controller = RunController(studio_video_audio_srt_input_service=planner)

    assert controller.select_studio_video_audio_srt_inputs() == (
        Path("video.mp4"),
        Path("audio.mp3"),
    )

    planner.discover.assert_called_once_with(False)


@pytest.mark.parametrize(
    ("audio_duration", "choice", "expected_mode"),
    ((10.0, None, "silence"), (3.0, "silence", "silence"), (3.0, "music", "music")),
)
def test_audio_tail_selection_only_prompts_when_audio_is_shorter(
    audio_duration,
    choice,
    expected_mode,
):
    video = Path("video.mp4")
    audio = Path("audio.mp3")
    music_selector = Mock()
    music_selector.select.return_value = Path("assets/music/tail.mp3")
    probe = Mock()
    probe.inspect.return_value = _media_info(8.0)
    probe.get_duration.return_value = audio_duration
    controller = RunController(
        studio_music_selector=music_selector,
        media_probe=probe,
    )
    messages = []
    controller._print = messages.append
    controller._select_from_list = Mock(return_value=choice)

    selected = controller.select_studio_video_audio_srt_audio_tail(
        StudioVideoAudioSrtPlan(video, audio)
    )

    assert selected.video_duration == 8.0
    assert selected.audio_duration == audio_duration
    assert selected.audio_tail_mode == expected_mode
    if expected_mode == "music":
        assert selected.music_path == Path("assets/music/tail.mp3")
        music_selector.select.assert_called_once_with("random")
    else:
        assert selected.music_path is None
        music_selector.select.assert_not_called()
    if choice is None:
        controller._select_from_list.assert_not_called()
    else:
        assert "1. SIN MÚSICA" in messages
        assert "2. CON MÚSICA" in messages
        assert "DEJAR SILENCIO" not in "\n".join(messages)
        assert "COMPLETAR CON MÚSICA" not in "\n".join(messages)


def test_video_audio_srt_subtitle_selection_uses_real_profiles_without_original():
    profile_key, _, _ = _profile_and_subtitles()
    controller = RunController()
    family = controller.subtitle_profile_resolver.discover_families(
        profile_key.component,
        profile_key.platform,
    )[0]
    descriptors = controller.subtitle_profile_resolver.discover_profiles_for_family(
        profile_key.component,
        profile_key.platform,
        family,
    )
    messages = []
    controller._print = messages.append
    controller._select_from_list = Mock(side_effect=(family, descriptors[-1]))

    selected = controller._select_studio_video_audio_srt_subtitle_profile(
        profile_key
    )

    assert selected == descriptors[-1].key
    assert "ORIGINAL" not in "\n".join(messages)


@pytest.mark.parametrize(
    ("video_duration", "audio_duration", "tail_mode", "expected_audio_filter"),
    (
        (10.0, 10.0, "silence", "atrim=duration=10.000000"),
        (10.0, 15.0, "silence", "atrim=duration=10.000000"),
        (10.0, 3.0, "silence", "apad,atrim=duration=10.000000"),
    ),
)
def test_video_is_temporal_authority_and_new_audio_never_loops(
    video_duration,
    audio_duration,
    tail_mode,
    expected_audio_filter,
):
    _, profile, _ = _profile_and_subtitles()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        video, audio, _ = _write_sources(root)
        runner = RecordingRunner()
        probe = Mock()
        probe.inspect.return_value = _media_info(video_duration)
        probe.get_duration.return_value = audio_duration
        output = root / "out.mp4"

        validator = DurationValidator()
        rendered, duration, command = StudioVideoAudioSrtService(
            probe=probe,
            runner=runner,
            validator=validator,
        ).render(
            StudioVideoAudioSrtPlan(
                video,
                audio,
                audio_tail_mode=tail_mode,
            ),
            output,
            profile,
        )

        graph = command[command.index("-filter_complex") + 1]
        assert rendered == output
        assert duration == video_duration
        assert output.read_bytes() == b"rendered"
        assert "-stream_loop" not in command
        assert f"trim=duration={video_duration:.6f}" in graph
        assert expected_audio_filter in graph
        assert f"[1:a:0]aresample={profile.audio_sample_rate}" in graph
        assert "[0:a:0]" not in graph
        assert "amix=" not in graph
        assert "subtitles=" not in graph
        assert validator.profile is profile
        assert video.read_bytes() == b"video-original"
        assert audio.read_bytes() == b"audio-new"


def test_short_audio_can_be_completed_with_music_only_in_the_final_gap():
    _, profile, _ = _profile_and_subtitles()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        video, audio, _ = _write_sources(root)
        music = root / "tail.mp3"
        music.write_bytes(b"music")
        runner = RecordingRunner()
        probe = Mock()
        probe.inspect.return_value = _media_info(10.0)
        probe.get_duration.return_value = 3.0
        output = root / "out.mp4"

        _, duration, command = StudioVideoAudioSrtService(
            probe=probe,
            runner=runner,
            validator=DurationValidator(),
        ).render(
            StudioVideoAudioSrtPlan(
                video,
                audio,
                audio_tail_mode="music",
                music_path=music,
            ),
            output,
            profile,
        )

        graph = command[command.index("-filter_complex") + 1]
        assert duration == 10.0
        assert command.count("-stream_loop") == 1
        assert "[0:a:0]" not in graph
        assert "amix=" not in graph
        assert "atrim=duration=3.000000" in graph
        assert "atrim=duration=7.000000" in graph
        assert "[new_audio][tail_music]concat=n=2:v=0:a=1[aout]" in graph
        assert f"[2:a:0]volume={profile.music.volume:.6f}," in graph
        assert (
            f"alimiter=limit={profile.music.limiter_limit:.6f}:"
            "level=false:latency=true[tail_music]"
        ) in graph
        assert "(ow-iw)/2:(oh-ih)/2," in graph


@pytest.mark.parametrize("style", ("single_line", "word_by_word"))
def test_render_uses_the_common_studio_style_for_human_srt(style):
    profile_key, profile, resolver = _profile_and_subtitles()
    subtitle_profile = resolver.load(
        _standard_subtitle_key(style)
    )
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        video, audio, subtitle = _write_sources(root, with_subtitle=True)
        runner = RecordingRunner()
        probe = Mock()
        probe.inspect.return_value = _media_info(2.0)
        probe.get_duration.return_value = 2.0
        service = StudioVideoAudioSrtService(
            probe=probe,
            runner=runner,
            validator=DurationValidator(),
        )
        service.FONTS_DIRECTORY = root

        _, _, command = service.render(
            StudioVideoAudioSrtPlan(video, audio, subtitle),
            root / "out.mp4",
            profile,
            subtitle_profile=subtitle_profile,
        )

        graph = command[command.index("-filter_complex") + 1]
        assert "subtitles=" in graph
        assert "human.srt" in graph
        assert "force_style=" in graph
        assert "amix=" not in graph


@pytest.mark.parametrize("style", ("single_line", "word_by_word"))
def test_human_srt_is_preserved_without_whisper_or_transformers(style):
    profile_key, profile, resolver = _profile_and_subtitles()
    subtitle_profile = resolver.load(
        _standard_subtitle_key(style)
    )
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        video, audio, subtitle = _write_sources(root, with_subtitle=True)
        output = root / "output" / "video" / "final.mp4"
        config = Mock()
        config.get_operational_profile_key.return_value = OperationalProfileKey(
            profile_key.component,
            profile_key.platform,
            profile_key.profile_id,
        )
        config.get_profile_config.return_value = {}
        config.get_subtitle_profile_by_key.return_value = subtitle_profile
        project = Mock()
        resolver_output = Mock()
        resolver_output.resolve.return_value = output
        renderer = Mock()
        renderer.render.return_value = (output, 2.0, ("ffmpeg",))

        options = dict(
            subtitle_profile_key=subtitle_profile.key,
            project=project,
            config_manager=config,
            profile_loader=Mock(load=Mock(return_value=profile)),
            output_path_resolver=resolver_output,
            service=renderer,
        )
        with patch("app.core.start.ExternalMediaSubtitlePreparationService") as whisper, patch(
            "app.modules.studio.execution_coordinator.SubtitleCueTransformer"
        ) as transformer:
                result = ejecutar_studio_video_audio_srt(
                    StudioVideoAudioSrtPlan(video, audio, subtitle),
                    **options,
                )

        whisper.assert_not_called()
        transformer.assert_not_called()
        assert subtitle.read_text(encoding="utf-8") == (
            "1\n00:00:00,000 --> 00:00:01,500\nTexto humano intacto.\n"
        )
        assert result.base_subtitle_path.is_file()
        assert result.generated_subtitle_path.is_file()
        assert result.generated_subtitle_path == result.base_subtitle_path
        assert result.base_subtitle_path.read_text(encoding="utf-8") == (
            "1\n00:00:00,000 --> 00:00:01,500\nTexto humano intacto.\n"
        )
        render_plan = renderer.render.call_args.args[0]
        assert render_plan.subtitle_path == result.generated_subtitle_path
        assert renderer.render.call_args.kwargs["subtitle_profile"] == subtitle_profile


def test_human_srt_allows_only_a_visual_uppercase_derivative():
    profile_key, profile, resolver = _profile_and_subtitles()
    subtitle_profile = resolver.load(
        _standard_subtitle_key("single_line")
    )
    subtitle_profile = type("UppercaseProfile", (), {
        "key": subtitle_profile.key,
        "cue_policy": {**subtitle_profile.cue_policy, "text_case": "uppercase"},
        "render_style": subtitle_profile.render_style,
    })()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        video, audio, subtitle = _write_sources(root, with_subtitle=True)
        output = root / "output" / "video" / "final.mp4"
        config = Mock()
        config.get_operational_profile_key.return_value = OperationalProfileKey(
            profile_key.component,
            profile_key.platform,
            profile_key.profile_id,
        )
        config.get_profile_config.return_value = {}
        config.get_subtitle_profile_by_key.return_value = subtitle_profile
        renderer = Mock()
        renderer.render.return_value = (output, 2.0, ("ffmpeg",))
        resolver_output = Mock()
        resolver_output.resolve.return_value = output

        with patch(
            "app.modules.studio.execution_coordinator.SubtitleCueTransformer"
        ) as transformer:
            result = ejecutar_studio_video_audio_srt(
                StudioVideoAudioSrtPlan(video, audio, subtitle),
                subtitle_profile_key=subtitle_profile.key,
                project=Mock(),
                config_manager=config,
                profile_loader=Mock(load=Mock(return_value=profile)),
                output_path_resolver=resolver_output,
                service=renderer,
            )

        transformer.assert_not_called()
        assert subtitle.read_text(encoding="utf-8") == (
            "1\n00:00:00,000 --> 00:00:01,500\nTexto humano intacto.\n"
        )
        assert result.generated_subtitle_path != result.base_subtitle_path
        assert result.generated_subtitle_path.read_text(encoding="utf-8") == (
            "1\n00:00:00,000 --> 00:00:01,500\nTEXTO HUMANO INTACTO.\n"
        )


def test_subtitle_display_name_falls_back_when_profile_does_not_exist():
    missing_key = SubtitleProfileKey(
        "studio",
        "youtube",
        "dummy_profile",
        "test_family",
    )

    assert main._subtitle_display_name(
        {"subtitle_profile_key": missing_key}
    ) == "dummy_profile"


def test_subtitle_display_name_falls_back_on_resolver_operational_error():
    missing_key = _standard_subtitle_key("single_line")
    error = OperationalError(
        ErrorContext(
            family="PROFILE",
            severity=ErrorSeverity.RECOVERABLE,
            user_message="No se encontró el perfil de subtítulos solicitado.",
            exit_kind=ExitKind.OPERATIONAL_ERROR,
        )
    )

    with patch.object(
        main.SubtitleProfileResolver,
        "load",
        side_effect=error,
    ):
        display_name = main._subtitle_display_name(
            {"subtitle_profile_key": missing_key}
        )

    assert display_name == missing_key.profile_id


def test_video_audio_srt_summary_identifies_all_required_inputs_and_durations():
    plan = StudioVideoAudioSrtPlan(
        Path("input/studio/video_audio_srt/source.mp4"),
        Path("input/studio/video_audio_srt/new-audio.wav"),
        Path("input/studio/video_audio_srt/human.srt"),
        video_duration=12.345,
        audio_duration=18.0,
    )
    options = {
        "project_name": "video-audio-srt",
        "profile_id": "studio_youtube",
        "profile_platform": "youtube",
        "studio_input_mode": "video_audio_srt",
        "studio_video_audio_srt_plan": plan,
        "subtitle_profile_key": _standard_subtitle_key("single_line"),
    }
    result = SimpleNamespace(
        output_path=Path("output/video/final.mp4"),
        generated_duration=12.345,
        base_subtitle_path=Path("output/subtitles/final.srt"),
        generated_subtitle_path=Path("output/subtitles/final.srt"),
    )
    summary = Mock()
    with patch.object(main, "PipelineSummary", return_value=summary), patch.object(
        main,
        "_subtitle_display_name",
        return_value="Línea única",
    ):
        main._print_studio_summary(options, result, 1.0)

    details = [call.args for call in summary.add_detail.call_args_list]
    assert ("Proyecto", "video-audio-srt") in details
    assert ("Perfil / plataforma", "studio_youtube / Youtube") in details
    assert ("Video fuente", plan.video_path) in details
    assert ("Audio nuevo", plan.audio_path) in details
    assert ("Subtítulos", "Sí") in details
    assert ("Perfil de subtítulos", "Línea única") in details
    assert ("Duración vídeo", "12.345 s") in details
    assert ("Duración audio original", "18.000 s") in details
    assert ("Duración final", "12.345 s") in details
    assert ("Tratamiento audio", "Recortado al vídeo") in details
    assert ("Video final", result.output_path) in details
    assert ("Estado final", "VIDEO + AUDIO SRT COMPLETADO") in details
