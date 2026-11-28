"""VIDEO + AUDIO | SRT says when it renders, like the other modes (A2-F)."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.modules.studio.execution_coordinator import StudioExecutionCoordinator
from app.modules.studio.video_audio_srt import StudioVideoAudioSrtPlan
from app.shared.profile_identity import OperationalProfileKey

COORDINATOR = "app.modules.studio.execution_coordinator"


def test_render_is_announced_before_and_finished_after(tmp_path, capsys):
    events = []
    profile_key = OperationalProfileKey("studio", "vertical", "dummy_profile")
    config = SimpleNamespace(
        get_operational_profile_key=lambda: profile_key,
        get_profile_config=lambda: {},
    )
    output_path = tmp_path / "video" / "final.mp4"

    def render(plan, output, profile, subtitle_profile=None):
        events.append(("render", capsys.readouterr().out))
        return output, 2.0, ("ffmpeg",)

    service = Mock(render=Mock(side_effect=render))
    with patch(f"{COORDINATOR}.time.perf_counter", side_effect=(10.0, 13.5)):
        result = StudioExecutionCoordinator().run_video_audio_srt(
            StudioVideoAudioSrtPlan(Path("source.mp4"), Path("new.wav")),
            project=Mock(),
            config_manager=config,
            profile_loader=SimpleNamespace(load=lambda raw, key: SimpleNamespace(fps=30)),
            output_path_resolver=SimpleNamespace(resolve=lambda **_: output_path),
            service=service,
        )

    assert events == [("render", "\nRENDERIZANDO STUDIO...\n")]
    assert capsys.readouterr().out == "RENDER STUDIO COMPLETADO (3,50 s)\n"
    assert result.render_duration == 3.5
