import hashlib
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.cli import studio_summary
from app.controllers.run_controller import RunController
from app.core.execution_request import (
    ApplicationExecutionRequest,
    StudioExecutionRequest,
)
from app.modules.studio.execution_coordinator import StudioExecutionCoordinator
from app.modules.studio import (
    StudioInputMode,
    StudioMontageClip,
    StudioMontagePlan,
    StudioMontageRenderResult,
    StudioMontageResult,
    StudioRenderResult,
)
from app.modules.video.intro_outro import IntroOutroPlan, IntroOutroSelection
from app.shared.profile_identity import OperationalProfileKey


class StudioMontagePhase4Test(unittest.TestCase):

    def setUp(self):
        self.profile_key = OperationalProfileKey("studio", "vertical", "studio_vertical")
        self.profile = SimpleNamespace(fps=30, max_duration_difference=0.2)

    def _plan(self, root, transitions_enabled=False):
        clips = []
        for index in range(1, 3):
            path = root / f"source-{index}.mp4"
            path.write_bytes(b"source")
            clips.append(StudioMontageClip(index, path, path.name))
        return StudioMontagePlan(
            profile_key=self.profile_key,
            transitions_enabled=transitions_enabled,
            clips=tuple(clips),
        )

    def _dependencies(self, root):
        project = Mock()
        profile_resolver = Mock()
        profile_resolver.load.return_value = {"studio": {}}
        profile_loader = Mock()
        profile_loader.load.return_value = self.profile
        output_path = root / "output" / "demo" / "video" / "demo.mp4"
        output_resolver = Mock()
        output_resolver.resolve.return_value = output_path
        return project, profile_resolver, profile_loader, output_resolver, output_path

    def test_montage_renders_without_subtitle_domain_and_preserves_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = self._plan(root, transitions_enabled=True)
            source_hashes = {
                clip.path: hashlib.sha256(clip.path.read_bytes()).digest()
                for clip in plan.clips
            }
            project, resolver, loader, output_resolver, output_path = self._dependencies(root)
            montage = Mock()

            def compose(*, plan, output_path, profile):
                Path(output_path).write_bytes(b"principal")
                return StudioMontageResult(
                    output_path=Path(output_path), command=("ffmpeg",),
                    expected_duration=2.0, generated_duration=2.0,
                    clip_count=2, preparation_duration=0.2, montage_duration=0.3,
                )

            montage.compose.side_effect = compose
            renderer = Mock()
            renderer.render.return_value = StudioRenderResult(
                source_video_path=Path("principal.mp4"), source_subtitle_path=None,
                output_path=output_path, command=("ffmpeg",), expected_duration=2.0,
                generated_duration=2.0, source_had_audio=True, silence_added=False,
                music_path=Path("music.mp3"), render_duration=0.4,
            )

            result = StudioExecutionCoordinator().run_montage(
                plan, music_path=Path("music.mp3"),
                intro_outro_selection=SimpleNamespace(intro=object(), outro=None),
                project=project, profile_resolver=resolver, profile_loader=loader,
                output_path_resolver=output_resolver, montage_service=montage,
                render_service=renderer,
            )
            sources_unchanged = all(
                source_hash == hashlib.sha256(path.read_bytes()).digest()
                for path, source_hash in source_hashes.items()
            )

        self.assertIsInstance(result, StudioMontageRenderResult)
        principal_path = montage.compose.call_args.kwargs["output_path"]
        self.assertNotEqual(output_path, principal_path)
        render_kwargs = renderer.render.call_args.kwargs
        self.assertEqual(principal_path, render_kwargs["video_path"])
        self.assertNotIn("subtitle_path", render_kwargs)
        self.assertNotIn("subtitle_profile", render_kwargs)
        self.assertEqual(Path("music.mp3"), render_kwargs["music_path"])
        self.assertTrue(plan.transitions_enabled)
        self.assertTrue(sources_unchanged)

    def test_run_controller_uses_operational_profile_then_only_montage_options(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = self._plan(root)
            controller = RunController()
            intro_outro = IntroOutroPlan(
                intro=IntroOutroSelection(root / "intro.mp4", "intro"),
                outro=IntroOutroSelection(root / "outro.mp4", "outro"),
            )
            controller.select_studio_input_mode = Mock(return_value="montaje_videos")
            controller._select_studio_operational_profile = Mock(
                return_value=(self.profile_key, self.profile)
            )
            controller.select_studio_montage_plan = Mock(return_value=plan)
            controller.select_studio_music = Mock(return_value=Path("music.mp3"))
            controller.select_studio_intro_outro = Mock(return_value=intro_outro)
            controller.ask_project_name = Mock(return_value="demo")
            controller.ask_clear_output = Mock(return_value=False)

            request = controller._run_studio()

        self.assertNotIn("subtitle_config", vars(request))
        self.assertNotIn("subtitle_config", vars(request.route))
        self.assertIsNone(request.subtitle_profile_key)
        self.assertEqual(Path("music.mp3"), request.route.music_path)
        self.assertIs(intro_outro, request.route.intro_outro_plan)
        controller._select_studio_operational_profile.assert_called_once_with()
        controller.select_studio_montage_plan.assert_called_once_with(
            self.profile_key, self.profile
        )
        controller.select_studio_music.assert_called_once_with()
        controller.select_studio_intro_outro.assert_called_once_with(self.profile_key)

    def test_montage_summary_has_no_mode_or_subtitle_stages(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = self._plan(root)
            montage = StudioMontageResult(
                output_path=root / "principal.mp4", command=("ffmpeg",),
                expected_duration=2.0, generated_duration=2.0, clip_count=2,
                preparation_duration=0.2, montage_duration=0.3,
            )
            rendered = StudioRenderResult(
                source_video_path=montage.output_path, source_subtitle_path=None,
                output_path=root / "final.mp4", command=("ffmpeg",),
                expected_duration=2.0, generated_duration=2.0, source_had_audio=True,
                silence_added=False, music_path=None, render_duration=0.4,
            )
            result = StudioMontageRenderResult(montage, rendered)
            request = ApplicationExecutionRequest(
                project_name="demo", clear_output=False,
                operational_profile_key=OperationalProfileKey(
                    "studio", "vertical", "studio_vertical"
                ),
                subtitle_profile_key=None,
                route=StudioExecutionRequest(
                    input_mode=StudioInputMode.MONTAJE_VIDEOS, plan=plan,
                    music_path=None, intro_outro_plan=None,
                ),
            )
            with patch("app.managers.pipeline_summary.ProgressLogger.info") as logger:
                studio_summary.print_studio_summary(request, result, 1.0)

        output = logger.call_args.args[0]
        self.assertIn("Montaje de videos", output)
        self.assertIn("Música", output)
        self.assertNotIn("Subtítulos", output)
        self.assertNotIn("Estilo", output)
        self.assertNotIn("Modo", output)
        self.assertNotIn("Preparación subtítulos", output)


if __name__ == "__main__":
    unittest.main()
