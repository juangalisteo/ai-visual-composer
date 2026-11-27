"""GUION summary: real order, Spanish names, scenes for clips (A2, fallo 12)."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.core.pipeline_telemetry import PipelineTelemetry
from app.managers.pipeline_summary import PipelineSummary
from app.modules.video.video_build_context_factory import VideoBuildContextFactory


FACTORY = "app.modules.video.video_build_context_factory"


def test_stage_order_is_the_order_of_execution_with_spanish_names():
    assert PipelineTelemetry.STAGE_ORDER == (
        "Guion",
        "Voz",
        "Audio",
        "Subtítulos",
        "Storyboard",
        "Imágenes",
        "Clips de vídeo",
        "Vídeo final",
    )


def test_complete_lists_the_stages_in_execution_order():
    summary = PipelineSummary("test_project")
    stage_times = {name: 1.0 for name in reversed(PipelineTelemetry.STAGE_ORDER)}
    with patch.object(summary, "print"):
        PipelineTelemetry(clock=lambda: 0.0).complete(
            summary=summary,
            stage_times=stage_times,
            pipeline_start=0.0,
        )
    assert tuple(summary.stage_times) == PipelineTelemetry.STAGE_ORDER


def _summary(still_images):
    summary = PipelineSummary("test_project", still_images=still_images)
    summary.set_scene_count(3)
    summary.set_image_count(3)
    summary.set_scene_durations((5.29, 5.731, 7.0))
    summary.set_media_duration(18.0)
    return summary.render()


def test_clips_summary_has_scenes_with_each_duration_and_no_images():
    rendered = _summary(still_images=False)
    assert "Escenas.................... 3" in rendered
    assert "Duración de cada escena.... 5.29 · 5.73 · 7.00 s" in rendered
    assert "Imágenes" not in rendered
    assert "Segundos por imagen" not in rendered
    assert "por imagen" not in rendered


def test_still_images_summary_is_unchanged():
    rendered = _summary(still_images=True)
    assert "Imágenes................... 3" in rendered
    assert "Segundos por imagen........ 6.00" in rendered
    assert "Duración de cada escena" not in rendered


def test_telemetry_reads_each_scene_duration_from_the_storyboard(tmp_path):
    storyboard = tmp_path / "storyboard.json"
    storyboard.write_text(
        json.dumps([{"scene": 1, "duration": 5.5}, {"scene": 2, "duration": 6}]),
        encoding="utf-8",
    )
    assert PipelineTelemetry._scene_durations(storyboard) == (5.5, 6.0)


def test_telemetry_leaves_durations_out_if_one_scene_has_none(tmp_path):
    storyboard = tmp_path / "storyboard.json"
    storyboard.write_text(
        json.dumps([{"scene": 1, "duration": 5.5}, {"scene": 2, "duration": True}]),
        encoding="utf-8",
    )
    assert PipelineTelemetry._scene_durations(storyboard) == ()
    assert PipelineTelemetry._scene_durations(tmp_path / "missing.json") == ()
    storyboard.write_text("{}", encoding="utf-8")
    assert PipelineTelemetry._scene_durations(storyboard) == ()


def _factory_messages(**build_options):
    project = SimpleNamespace(
        subtitle_path=lambda: Path("project.srt"),
        storyboard_path=lambda: Path("project_storyboard.json"),
        images_manifest_path=lambda: Path("project_images.json"),
        video_path=lambda: Path("project.mp4"),
    )
    config = SimpleNamespace(
        subtitle_offset=0.0,
        transitions=SimpleNamespace(duration=0.4),
        width=640,
        height=360,
        fps=24,
    )
    media = SimpleNamespace(
        audio_path=Path("audio.mp3"),
        subtitle_path=None,
        output_path=Path("out.mp4"),
        image_paths=(Path("one"), Path("two")),
        scene_durations=(6.6, 7.4),
    )
    timeline = SimpleNamespace(
        audio_duration=14.0,
        image_duration=7.0,
        scene_durations=(6.6, 7.4),
    )
    messages = []
    with patch(f"{FACTORY}.ProjectManager", return_value=project), patch(
        f"{FACTORY}.AudioResolver"
    ) as audio_resolver, patch(f"{FACTORY}.VideoConfigLoader") as config_loader, patch(
        f"{FACTORY}.MediaLoader"
    ) as media_loader, patch(f"{FACTORY}.TimelineBuilder") as timeline_builder, patch(
        f"{FACTORY}.ProgressLogger.info",
        side_effect=lambda message, **_: messages.append(message),
    ):
        audio_resolver.return_value.resolve.return_value = Path("audio.mp3")
        config_loader.return_value.load.return_value = config
        media_loader.return_value.load.return_value = media
        timeline_builder.return_value.build.return_value = timeline
        VideoBuildContextFactory().build(
            audio_path="audio.mp3",
            output_path="out.mp4",
            render_subtitles=False,
            **build_options,
        )
    return messages


def test_final_video_of_clips_talks_about_scenes():
    messages = _factory_messages(video_clips_manifest_path="video_clips.json")
    assert "Escenas: 2" in messages
    assert "Duración de cada escena: 6.60 · 7.40 segundos" in messages
    assert not any("imagen" in message.lower() for message in messages)


def test_final_video_of_still_images_still_talks_about_images():
    messages = _factory_messages(images_manifest_path="images.json")
    assert "Imágenes: 2" in messages
    assert "Duración por imagen: de 6.60 a 7.40 segundos (storyboard)" in messages


def test_completing_the_summary_reads_the_scene_durations(tmp_path):
    from app.core.pipeline_telemetry import PipelineTelemetryArtifacts

    storyboard = tmp_path / "storyboard.json"
    storyboard.write_text(
        json.dumps([{"scene": 1, "duration": 5.29}, {"scene": 2, "duration": 6.5}]),
        encoding="utf-8",
    )
    summary = PipelineSummary("test_project", still_images=False)
    with patch.object(summary, "print"):
        PipelineTelemetry(clock=lambda: 0.0).complete(
            summary=summary,
            stage_times={},
            pipeline_start=0.0,
            artifacts=PipelineTelemetryArtifacts(
                storyboard_path=storyboard,
                images_manifest_path=tmp_path / "images.json",
                final_audio_path=tmp_path / "audio_final.mp3",
                audio_path=tmp_path / "voz.mp3",
            ),
        )

    assert summary.scene_durations == (5.29, 6.5)
    assert "Duración de cada escena.... 5,29 · 6,50 s" in summary.render()
