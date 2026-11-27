"""The STUDIO summaries share one block (A2, PRUEBA-GS fallo 10)."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.cli import studio_summary
from app.core.execution_request import (
    ApplicationExecutionRequest,
    StudioExecutionRequest,
)
from app.modules.studio import StudioInputMode
from app.modules.studio.video_audio_srt import StudioVideoAudioSrtPlan
from app.shared.profile_identity import OperationalProfileKey
from app.shared.subtitle_profile_identity import SubtitleProfileKey


SUBTITLE_KEY = SubtitleProfileKey(
    component="studio",
    format="vertical",
    family="test_family",
    profile_id="dummy_subtitle_profile",
)


def _request(route, subtitle_profile_key=SUBTITLE_KEY):
    return ApplicationExecutionRequest(
        project_name="test_project",
        overwrite_project=False,
        operational_profile_key=OperationalProfileKey(
            "studio",
            "vertical",
            "dummy_profile",
        ),
        subtitle_profile_key=subtitle_profile_key,
        route=route,
    )


def _printed(request, result, *, profile_document=None):
    resolver = SimpleNamespace(
        load_operational=lambda key: profile_document or {"profile_id": key.profile_id}
    )
    with patch.object(studio_summary, "ProfileResolver", return_value=resolver), patch.object(
        studio_summary,
        "_subtitle_display_name",
        return_value="Perfil De Prueba",
    ), patch("builtins.print") as print_mock:
        studio_summary.print_studio_summary(request, result, 3.0)
    return "\n".join(str(call.args[0]) for call in print_mock.call_args_list if call.args)


def _lines(printed):
    return [line.split(".", 1)[0] for line in printed.splitlines() if "...." in line]


def _video_audio_plan(tmp_path, audio_tail_mode="none"):
    video = tmp_path / "source.mp4"
    audio = tmp_path / "new.wav"
    subtitle = tmp_path / "source.srt"
    for path in (video, audio, subtitle):
        path.write_bytes(b"x")
    return StudioVideoAudioSrtPlan(
        video_path=video,
        audio_path=audio,
        subtitle_path=subtitle,
        video_duration=10.0,
        audio_duration=9.95,
        audio_tail_mode=audio_tail_mode,
    )


def test_video_audio_summary_names_the_project_once_and_has_times(tmp_path):
    plan = _video_audio_plan(tmp_path)
    request = _request(
        StudioExecutionRequest(input_mode=StudioInputMode.VIDEO_AUDIO_SRT, plan=plan)
    )
    result = SimpleNamespace(
        output_path=Path("output/test_project/video/test_project.mp4"),
        generated_duration=10.0,
        render_duration=4.25,
        base_subtitle_path=Path("output/test_project/subtitles/test_project.srt"),
        generated_subtitle_path=Path(
            "output/test_project/subtitles/test_project_pintado.srt"
        ),
    )

    printed = _printed(request, result)

    assert _lines(printed).count("Proyecto") == 1
    assert "Duración audio nuevo" in printed
    assert "Duración audio original" not in printed
    times = printed.split("-" * 40)[1]
    assert "Render STUDIO.............. 4,25 s" in times
    assert "Perfil de subtítulos....... Perfil De Prueba" in printed


def test_srt_video_summary_names_the_chosen_subtitle_profile_not_original():
    route = StudioExecutionRequest(
        input_mode=StudioInputMode.SRT_VIDEO,
        video_path=Path("input/source.mp4"),
        subtitle_path=Path("input/source.srt"),
        subtitle_original=True,
    )
    result = SimpleNamespace(
        output_path=Path("output/test_project/video/test_project.mp4"),
        generated_duration=12.0,
        render_duration=2.0,
    )

    printed = _printed(_request(route), result)

    assert "ORIGINAL" not in printed
    assert "Perfil de subtítulos....... Perfil De Prueba" in printed
    assert "Video fuente" in printed and "SRT fuente" in printed
    assert "Duración final............. 12,00 s" in printed


def test_same_base_and_generated_srt_is_one_line():
    route = StudioExecutionRequest(input_mode=StudioInputMode.SRT_VIDEO)
    same = Path("output/test_project/subtitles/test_project.srt")
    result = SimpleNamespace(
        output_path=Path("output/test_project/video/test_project.mp4"),
        base_subtitle_path=same,
        generated_subtitle_path=Path(str(same)),
    )

    names = _lines(_printed(_request(route), result))

    assert "SRT" in names
    assert "SRT base" not in names and "SRT generado" not in names


def test_different_base_and_generated_srt_are_two_lines():
    route = StudioExecutionRequest(input_mode=StudioInputMode.SRT_VIDEO)
    result = SimpleNamespace(
        output_path=Path("output/test_project/video/test_project.mp4"),
        base_subtitle_path=Path("output/test_project/subtitles/a.srt"),
        generated_subtitle_path=Path("output/test_project/subtitles/b.srt"),
    )

    names = _lines(_printed(_request(route), result))

    assert "SRT base" in names and "SRT generado" in names
    assert "SRT" not in names


def test_profile_line_only_with_a_declared_display_name():
    route = StudioExecutionRequest(input_mode=StudioInputMode.SRT_VIDEO)
    result = SimpleNamespace(output_path=Path("output/test_project/video/x.mp4"))

    without_name = _printed(_request(route), result)
    with_name = _printed(
        _request(route),
        result,
        profile_document={"profile_id": "dummy_profile", "display_name": " Nombre visible "},
    )

    assert "dummy_profile" not in without_name
    assert "Perfil....................." not in without_name
    assert "Formato" in without_name
    assert "Perfil..................... Nombre visible" in with_name
    assert "dummy_profile" not in with_name


def test_every_mode_ends_with_its_label_completed():
    route = StudioExecutionRequest(input_mode=StudioInputMode.VIDEO)
    result = SimpleNamespace(output_path=Path("output/test_project/video/x.mp4"))

    printed = _printed(_request(route, subtitle_profile_key=None), result)

    assert "Estado final............... SOLO VIDEO COMPLETADO" in printed
    assert "Subtítulos................. No" in printed
    assert "Perfil de subtítulos" not in printed
