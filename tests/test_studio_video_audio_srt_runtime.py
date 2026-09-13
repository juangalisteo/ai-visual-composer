import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, call, patch

import pytest

from app.core.start import ejecutar_studio_video_audio_srt, iniciar
from app.controllers.run_controller import RunController
from app.modules.studio import (
    StudioProfileLoader,
    StudioVideoAudioSrtInputError,
    StudioVideoAudioSrtInputService,
    StudioVideoAudioSrtPlan,
    StudioVideoAudioSrtService,
)
from app.shared.media_probe import MediaInfo
from app.shared.profile_identity import ProfileKey
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


def _profile_and_subtitles():
    profile_key = ProfileKey.for_component("studio", "youtube")
    profile = StudioProfileLoader().load(
        ProfileResolver().load(profile_key),
        profile_key,
    )
    return profile_key, profile, SubtitleProfileResolver()


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


def test_video_audio_runtime_dispatches_service():
    with tempfile.TemporaryDirectory() as directory:
        video, audio, _ = _write_sources(Path(directory))
        plan = StudioVideoAudioSrtPlan(video, audio)
        with patch.dict(os.environ, {"MC_PIPELINE_MODE": "studio"}, clear=True), patch(
            "app.core.start.ejecutar_studio_video_audio_srt",
            return_value="ok",
        ) as run:
            assert iniciar(studio_video_audio_srt_plan=plan) == "ok"
        run.assert_called_once_with(
            plan,
            subtitle_style=None,
            subtitle_original=False,
        )


@pytest.mark.parametrize("subtitles", (False, True))
def test_menu_option_seven_never_asks_for_or_returns_music(subtitles):
    profile_key, _, _ = _profile_and_subtitles()
    planner = Mock()
    controller = RunController(studio_video_audio_srt_input_service=planner)
    controller.select_studio_input_mode = Mock(return_value="video_audio_srt")
    controller._select_studio_profile = Mock(return_value=(profile_key, Mock()))
    controller._select_from_list = Mock(return_value=subtitles)
    controller.select_studio_subtitle_options = Mock(
        return_value=("word_by_word", False)
    )
    controller.select_studio_video_audio_srt_plan = Mock(return_value=Mock())
    controller.select_studio_music = Mock()
    controller.ask_project_name = Mock(return_value="project")
    controller.ask_clear_output = Mock(return_value=False)

    options = controller._run_studio()

    controller.select_studio_video_audio_srt_plan.assert_called_once_with(
        subtitles
    )
    controller._select_from_list.assert_called_once_with((True, False))
    controller.select_studio_music.assert_not_called()
    assert "studio_music_path" not in options
    assert options["subtitle_config"] == (
        "word_by_word" if subtitles else None
    )


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
        with pytest.raises(StudioVideoAudioSrtInputError, match="exactamente un archivo SRT"):
            service.create_plan(True)


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
        assert tuple(path.name for path in candidates.subtitles) == (
            "a.srt", "z.srt",
        )
        plan = service.create_plan(
            True,
            video_path=selected_video,
            audio_path=selected_audio,
            subtitle_path=selected_subtitle,
        )
        assert plan == StudioVideoAudioSrtPlan(
            selected_video,
            selected_audio,
            selected_subtitle,
        )


def test_controller_lists_multiple_video_audio_and_srt_candidates():
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
            studio_video_audio_srt_input_service=(
                StudioVideoAudioSrtInputService(root)
            )
        )
        messages = []
        controller._print = messages.append
        controller._select_from_list = Mock(
            side_effect=(video_two, audio_one, subtitle_two)
        )

        plan = controller.select_studio_video_audio_srt_plan(True)

        assert plan == StudioVideoAudioSrtPlan(
            video_two,
            audio_one,
            subtitle_two,
        )
        assert controller._select_from_list.call_args_list == [
            call((video_one, video_two)),
            call((audio_one, audio_two)),
            call((subtitle_one, subtitle_two)),
        ]
        assert "VIDEO" in "\n".join(messages)
        assert "AUDIO" in "\n".join(messages)
        assert "SRT" in "\n".join(messages)


def test_video_audio_subtitle_options_offer_original_without_second_selector():
    profile_key, _, _ = _profile_and_subtitles()
    controller = RunController()
    controller._select_from_list = Mock(return_value="original")
    with patch.object(controller, "select_studio_subtitle_config") as visual:
        style, original = controller.select_studio_subtitle_options(
            profile_key,
            "video_audio_srt",
        )

    assert style == "single_line"
    assert original is True
    visual.assert_not_called()
    controller._select_from_list.assert_called_once_with(
        (
            "original",
            "subtitulo_studio_youtube_linea_unica",
            "subtitulo_studio_youtube_palabra_por_palabra",
        )
    )


@pytest.mark.parametrize(
    ("video_duration", "audio_duration", "expects_loop"),
    ((10.0, 3.0, False), (2.0, 3.0, True)),
)
def test_video_is_trimmed_or_looped_and_new_audio_is_the_only_audio(
    video_duration,
    audio_duration,
    expects_loop,
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
        ).render(StudioVideoAudioSrtPlan(video, audio), output, profile)

        graph = command[command.index("-filter_complex") + 1]
        assert rendered == output
        assert duration == audio_duration
        assert output.read_bytes() == b"rendered"
        assert ("-stream_loop" in command) is expects_loop
        assert f"trim=duration={audio_duration:.6f}" in graph
        assert f"[1:a:0]aresample={profile.audio_sample_rate}" in graph
        assert "[0:a:0]" not in graph
        assert "amix=" not in graph
        assert "subtitles=" not in graph
        assert validator.profile is profile
        assert video.read_bytes() == b"video-original"
        assert audio.read_bytes() == b"audio-new"


@pytest.mark.parametrize("style", ("single_line", "word_by_word"))
def test_render_uses_the_common_studio_style_for_human_srt(style):
    profile_key, profile, resolver = _profile_and_subtitles()
    subtitle_profile = resolver.load(
        SubtitleProfileKey.for_profile(profile_key, style)
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


@pytest.mark.parametrize(
    "style, original",
    (("single_line", True), ("single_line", False), ("word_by_word", False)),
)
def test_human_srt_is_persisted_and_transformed_without_whisper(style, original):
    profile_key, profile, resolver = _profile_and_subtitles()
    subtitle_profile = resolver.load(
        SubtitleProfileKey.for_profile(profile_key, style)
    )
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        video, audio, subtitle = _write_sources(root, with_subtitle=True)
        output = root / "output" / "video" / "final.mp4"
        config = Mock()
        config.get_profile_key.return_value = profile_key
        config.get_profile_config.return_value = {}
        config.get_subtitle_profile.return_value = subtitle_profile
        project = Mock()
        resolver_output = Mock()
        resolver_output.resolve.return_value = output
        renderer = Mock()
        renderer.render.return_value = (output, 2.0, ("ffmpeg",))

        options = dict(
            subtitle_style=style,
            subtitle_original=original,
            project=project,
            config_manager=config,
            profile_loader=Mock(load=Mock(return_value=profile)),
            output_path_resolver=resolver_output,
            service=renderer,
        )
        with patch("app.core.start.ExternalMediaSubtitlePreparationService") as whisper:
            if original:
                with patch("app.core.start.SubtitleCueTransformer") as transformer:
                    result = ejecutar_studio_video_audio_srt(
                        StudioVideoAudioSrtPlan(video, audio, subtitle),
                        **options,
                    )
                transformer.assert_not_called()
            else:
                result = ejecutar_studio_video_audio_srt(
                    StudioVideoAudioSrtPlan(video, audio, subtitle),
                    **options,
                )

        whisper.assert_not_called()
        assert subtitle.read_text(encoding="utf-8") == (
            "1\n00:00:00,000 --> 00:00:01,500\nTexto humano intacto.\n"
        )
        assert result.base_subtitle_path.is_file()
        assert result.generated_subtitle_path.is_file()
        if original:
            assert result.generated_subtitle_path == result.base_subtitle_path
        else:
            assert result.generated_subtitle_path != result.base_subtitle_path
        render_plan = renderer.render.call_args.args[0]
        assert render_plan.subtitle_path == result.generated_subtitle_path
        assert renderer.render.call_args.kwargs["subtitle_profile"] == subtitle_profile
