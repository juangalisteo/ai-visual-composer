import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from app.modules.studio.execution_coordinator import (
    StudioExecutionCoordinator,
)
from app.modules.studio.intro_outro import StudioIntroOutroPlan
from app.modules.studio.input_preparation import StudioInputMode
from app.modules.studio.montage import (
    StudioMontageClip,
    StudioMontagePlan,
    StudioMontageRenderResult,
    StudioMontageResult,
)
from app.modules.studio.profile import StudioPreparation
from app.modules.studio.render_service import StudioRenderResult
from app.modules.studio.subtitle_export import (
    StudioSubtitleExportMode,
    StudioSubtitleExportPlan,
)
from app.modules.studio.video_audio_srt import StudioVideoAudioSrtPlan
from app.modules.video.intro_outro import (
    IntroOutroPlan,
    IntroOutroSelection,
)
from app.shared.profile_identity import (
    OperationalProfileKey,
    ProfileComponent,
)


class _Config:

    def __init__(self, profile_key, subtitle_profile):
        self.profile_key = profile_key
        self.subtitle_profile = subtitle_profile
        self.requested_subtitle_key = None

    def get_operational_profile_key(self):
        return self.profile_key

    @staticmethod
    def get_profile_config():
        return {"profile": "raw"}

    def get_subtitle_profile_by_key(self, subtitle_key):
        self.requested_subtitle_key = subtitle_key
        return self.subtitle_profile


class _ProfileLoader:

    def __init__(self, profile):
        self.profile = profile
        self.calls = []

    def load(self, raw_profile, profile_key):
        self.calls.append((raw_profile, profile_key))
        return self.profile


class _InputPreparation:

    def __init__(self, prepared):
        self.prepared = prepared
        self.calls = []

    def prepare(self, profile, input_mode, **options):
        self.calls.append((profile, input_mode, options))
        return self.prepared


class _Renderer:

    def __init__(self):
        self.options = None

    def render(self, **options):
        self.options = options
        return StudioRenderResult(
            source_video_path=Path(options["video_path"]),
            source_subtitle_path=options.get("subtitle_path"),
            output_path=Path(options["output_path"]),
            command=(),
            expected_duration=1.0,
            generated_duration=1.0,
            source_had_audio=True,
            silence_added=False,
            music_path=None,
        )


class _ExternalSubtitlePreparation:

    def __init__(self):
        self.working_directory = None

    def prepare(self, video_path, working_directory):
        self.working_directory = Path(working_directory)
        subtitle_path = self.working_directory / "whisper.srt"
        subtitle_path.write_text(
            "1\n00:00:00,000 --> 00:00:01,000\ntexto\n",
            encoding="utf-8",
        )
        return SimpleNamespace(
            subtitle_path=subtitle_path,
            timing="timing",
        )


class StudioExecutionCoordinatorTest(unittest.TestCase):

    def setUp(self):
        self.coordinator = StudioExecutionCoordinator()
        self.profile_key = OperationalProfileKey(
            ProfileComponent.STUDIO,
            "instagram",
            "studio_instagram",
        )
        self.subtitle_key = object()
        self.profile = SimpleNamespace(fps=30)
        self.subtitle_profile = SimpleNamespace(cue_policy={})

    def test_prepare_standard_uses_technical_identity_and_injected_normalizer(self):
        prepared_input = SimpleNamespace(
            video_path=Path("input/studio/video/source.mp4"),
            subtitle_path=None,
            mode=StudioInputMode.VIDEO,
        )
        config = _Config(self.profile_key, self.subtitle_profile)
        profile_loader = _ProfileLoader(self.profile)
        input_preparation = _InputPreparation(prepared_input)
        normalizer_calls = []

        preparation = self.coordinator.prepare_standard(
            input_mode=StudioInputMode.VIDEO.value,
            subtitle_profile_key=self.subtitle_key,
            config_manager=config,
            profile_loader=profile_loader,
            input_preparation_service=input_preparation,
            media_probe=SimpleNamespace(
                inspect=lambda path: SimpleNamespace(has_audio=True),
            ),
            subtitle_profile_key_normalizer=(
                lambda current_config, **options: (
                    normalizer_calls.append((current_config, options))
                    or options["subtitle_profile_key"]
                )
            ),
        )

        self.assertEqual(self.profile_key, preparation.profile_key)
        self.assertIs(self.profile, preparation.profile)
        self.assertIs(self.subtitle_profile, preparation.subtitle_profile)
        self.assertEqual(StudioInputMode.VIDEO.value, preparation.input_mode)
        self.assertEqual([(config, {
            "subtitle_profile_key": self.subtitle_key,
            "subtitle_style": None,
        })], normalizer_calls)
        self.assertEqual(self.subtitle_key, config.requested_subtitle_key)
        self.assertEqual([(self.profile, "video", {})], input_preparation.calls)

    def test_prepare_standard_rejects_video_without_audio_before_rendering(self):
        prepared_input = SimpleNamespace(
            video_path=Path("input/studio/video/silent.mp4"),
            subtitle_path=None,
            mode=StudioInputMode.VIDEO,
        )

        with self.assertRaisesRegex(ValueError, "no contiene una pista de audio"):
            self.coordinator.prepare_standard(
                input_mode=StudioInputMode.VIDEO.value,
                subtitle_profile_key=self.subtitle_key,
                config_manager=_Config(self.profile_key, self.subtitle_profile),
                profile_loader=_ProfileLoader(self.profile),
                input_preparation_service=_InputPreparation(prepared_input),
                media_probe=SimpleNamespace(
                    inspect=lambda path: SimpleNamespace(has_audio=False),
                ),
                subtitle_profile_key_normalizer=(
                    lambda config, **options: options["subtitle_profile_key"]
                ),
            )

    def test_run_standard_preserves_human_srt_artifacts_and_render_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "human.srt"
            source.write_text("source", encoding="utf-8")
            base = root / "subtitles" / "final.srt"
            derived = root / "subtitles" / "final_single_line.srt"
            output_path = root / "video" / "final.mp4"
            preparation = StudioPreparation(
                profile_key=self.profile_key,
                profile=self.profile,
                subtitle_profile=self.subtitle_profile,
                video_path=root / "source.mp4",
                subtitle_path=source,
                input_mode=StudioInputMode.SRT_VIDEO.value,
            )
            renderer = _Renderer()
            persisted = []

            result = self.coordinator.run_standard(
                input_mode=StudioInputMode.SRT_VIDEO.value,
                preparation_service=lambda **options: preparation,
                render_service=renderer,
                output_path_resolver=SimpleNamespace(
                    resolve=lambda **options: output_path,
                ),
                project=object(),
                persist_subtitle_base=(
                    lambda subtitle_path, current_output: (
                        persisted.append((Path(subtitle_path), current_output))
                        or base
                    )
                ),
                persist_render_subtitle=(
                    lambda **options: derived
                ),
            )
            source_content = source.read_text(encoding="utf-8")

        self.assertEqual([(source, output_path)], persisted)
        self.assertEqual(derived, renderer.options["subtitle_path"])
        self.assertEqual(base, result.base_subtitle_path)
        self.assertEqual(derived, result.generated_subtitle_path)
        self.assertEqual("source", source_content)

    def test_render_prepared_cleans_whisper_workspace_after_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output_path = root / "video" / "final.mp4"
            preparation = StudioPreparation(
                profile_key=self.profile_key,
                profile=self.profile,
                subtitle_profile=self.subtitle_profile,
                video_path=root / "source.mp4",
                subtitle_path=None,
                input_mode=StudioInputMode.VIDEO.value,
            )
            renderer = _Renderer()
            external = _ExternalSubtitlePreparation()
            base = root / "subtitles" / "final.srt"
            derived = root / "subtitles" / "final_single_line.srt"

            result = self.coordinator.render_prepared(
                preparation=preparation,
                project=object(),
                music_path=None,
                intro_outro_selection=None,
                output_path=output_path,
                render_service=renderer,
                external_subtitle_preparation_service=external,
                persist_subtitle_base=lambda *args: base,
                persist_render_subtitle=lambda **options: derived,
            )

        self.assertFalse(external.working_directory.exists())
        self.assertEqual(derived, renderer.options["subtitle_path"])
        self.assertEqual("timing", renderer.options["subtitle_timing"])
        self.assertEqual(base, result.base_subtitle_path)
        self.assertEqual(derived, result.generated_subtitle_path)
        self.assertIsNotNone(result.subtitle_preparation_duration)

    def test_persist_subtitle_base_keeps_human_source_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "human.srt"
            source.write_text("texto humano", encoding="utf-8")
            output_path = root / "video" / "final.mp4"

            persisted = self.coordinator.persist_subtitle_base(
                source,
                output_path,
            )

            self.assertEqual(root / "subtitles" / "final.srt", persisted)
            self.assertEqual("texto humano", source.read_text(encoding="utf-8"))
            self.assertEqual("texto humano", persisted.read_text(encoding="utf-8"))

    def test_run_standard_rejects_original_outside_srt_video(self):
        with self.assertRaisesRegex(ValueError, "ORIGINAL solo esta disponible"):
            self.coordinator.run_standard(
                input_mode=StudioInputMode.VIDEO.value,
                subtitle_original=True,
            )

    def test_run_video_audio_srt_preserves_human_srt_and_delegates_service(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video_path = root / "source.mp4"
            audio_path = root / "replacement.wav"
            source_subtitle_path = root / "human.srt"
            output_path = root / "video" / "final.mp4"
            video_path.write_bytes(b"video")
            audio_path.write_bytes(b"audio")
            source_subtitle_path.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\nTexto humano\n",
                encoding="utf-8",
            )
            subtitle_profile = SimpleNamespace(
                cue_policy={"text_case": "uppercase"},
            )
            config = _Config(self.profile_key, subtitle_profile)
            project = Mock()
            resolver = SimpleNamespace(resolve=Mock(return_value=output_path))
            service = Mock()
            service.render.return_value = (
                output_path,
                2.5,
                ("ffmpeg",),
            )
            normalizer = Mock(return_value=self.subtitle_key)

            result = self.coordinator.run_video_audio_srt(
                StudioVideoAudioSrtPlan(
                    video_path,
                    audio_path,
                    source_subtitle_path,
                ),
                subtitle_style="single_line",
                subtitle_profile_key=self.subtitle_key,
                project=project,
                config_manager=config,
                profile_loader=_ProfileLoader(self.profile),
                output_path_resolver=resolver,
                service=service,
                subtitle_profile_key_normalizer=normalizer,
            )

            base_path = root / "subtitles" / "final.srt"
            derived_path = root / "subtitles" / "final_original.srt"
            rendered_plan = service.render.call_args.args[0]
            self.assertEqual(base_path, result.base_subtitle_path)
            self.assertEqual(derived_path, result.generated_subtitle_path)
            self.assertEqual(derived_path, rendered_plan.subtitle_path)
            self.assertEqual(output_path, result.output_path)
            self.assertEqual(2.5, result.generated_duration)
            self.assertEqual("Texto humano", source_subtitle_path.read_text(encoding="utf-8").splitlines()[2])
            self.assertEqual("TEXTO HUMANO", derived_path.read_text(encoding="utf-8").splitlines()[2])
            project.setup.assert_called_once_with()
            resolver.resolve.assert_called_once_with(
                profile_key=self.profile_key,
                project=project,
            )
            normalizer.assert_called_once_with(
                config,
                subtitle_profile_key=self.subtitle_key,
                subtitle_style="single_line",
            )

    def test_run_video_audio_srt_rejects_invalid_subtitle_combinations(self):
        plan_without_srt = StudioVideoAudioSrtPlan(
            Path("source.mp4"),
            Path("replacement.wav"),
        )
        plan_with_srt = StudioVideoAudioSrtPlan(
            Path("source.mp4"),
            Path("replacement.wav"),
            Path("human.srt"),
        )

        with self.assertRaisesRegex(ValueError, "sin SRT no admite"):
            self.coordinator.run_video_audio_srt(
                plan_without_srt,
                subtitle_style="single_line",
            )
        with self.assertRaisesRegex(ValueError, "con SRT requiere"):
            self.coordinator.run_video_audio_srt(plan_with_srt)

    def test_run_subtitle_export_transcribe_needs_no_profile_or_timing_key(self):
        export_plan = StudioSubtitleExportPlan(
            StudioSubtitleExportMode.TRANSCRIBIR,
            Path("source.mp3"),
        )
        project = Mock()
        config = Mock()
        service = Mock()
        expected = object()
        service.export.return_value = expected

        result = self.coordinator.run_subtitle_export(
            export_plan,
            project=project,
            config_manager=config,
            export_service=service,
        )

        self.assertIs(expected, result)
        project.setup.assert_called_once_with()
        service.export.assert_called_once_with(
            plan=export_plan,
            project=project,
        )
        config.get_operational_profile_key.assert_not_called()

    def test_run_subtitle_export_convert_uses_technical_profile_and_key(self):
        export_plan = StudioSubtitleExportPlan(
            StudioSubtitleExportMode.CONVERTIR,
            Path("source.srt"),
        )
        config = _Config(self.profile_key, self.subtitle_profile)
        project = Mock()
        service = Mock()
        expected = object()
        service.export.return_value = expected
        normalizer = Mock(return_value=self.subtitle_key)
        profile_loader = _ProfileLoader(self.profile)

        result = self.coordinator.run_subtitle_export(
            export_plan,
            subtitle_style="single_line",
            subtitle_profile_key=self.subtitle_key,
            project=project,
            config_manager=config,
            profile_loader=profile_loader,
            export_service=service,
            subtitle_profile_key_normalizer=normalizer,
        )

        self.assertIs(expected, result)
        project.setup.assert_called_once_with()
        self.assertEqual([(config.get_profile_config(), self.profile_key)], profile_loader.calls)
        self.assertEqual(self.subtitle_key, config.requested_subtitle_key)
        normalizer.assert_called_once_with(
            config,
            subtitle_profile_key=self.subtitle_key,
            subtitle_style="single_line",
        )
        service.export.assert_called_once_with(
            plan=export_plan,
            project=project,
            profile=self.profile,
            subtitle_profile=self.subtitle_profile,
        )

    def test_run_intro_outro_renders_without_subtitles(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "source.mp4"
            source_path.write_bytes(b"video")
            common_plan = IntroOutroPlan(
                intro=IntroOutroSelection(source_path, "intro"),
            )
            intro_outro_plan = StudioIntroOutroPlan(
                source_path,
                common_plan,
            )
            project = Mock()
            config = _Config(self.profile_key, self.subtitle_profile)
            resolver = SimpleNamespace(
                resolve=Mock(return_value=root / "final.mp4"),
            )
            renderer = Mock()
            renderer.render.return_value = "rendered"

            result = self.coordinator.run_intro_outro(
                intro_outro_plan,
                project=project,
                config_manager=config,
                profile_loader=_ProfileLoader(self.profile),
                output_path_resolver=resolver,
                render_service=renderer,
            )

        self.assertEqual("rendered", result)
        project.setup.assert_called_once_with()
        renderer.render.assert_called_once_with(
            video_path=source_path,
            subtitle_path=None,
            profile_key=self.profile_key,
            profile=self.profile,
            output_path=root / "final.mp4",
            intro_outro_selection=common_plan,
        )

    def test_run_intro_outro_rejects_non_studio_plan(self):
        with self.assertRaisesRegex(TypeError, "plan STUDIO estructurado"):
            self.coordinator.run_intro_outro(object())

    def test_prepare_montage_validates_the_structured_plan(self):
        with self.assertRaisesRegex(TypeError, "plan STUDIO estructurado"):
            self.coordinator.prepare_montage(object())

    def test_run_montage_composes_temporary_principal_then_renders_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.mp4"
            second = root / "second.mp4"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            plan = StudioMontagePlan(
                profile_key=self.profile_key,
                transitions_enabled=False,
                clips=(
                    StudioMontageClip(1, first, first.name),
                    StudioMontageClip(2, second, second.name),
                ),
            )
            project = Mock()
            profile_resolver = Mock()
            profile_resolver.load_operational.return_value = {"raw": True}
            profile_loader = _ProfileLoader(self.profile)
            output_path = root / "output" / "final.mp4"
            output_resolver = SimpleNamespace(
                resolve=Mock(return_value=output_path),
            )
            montage_service = Mock()
            renderer = _Renderer()
            captured = {}

            def compose(*, plan, output_path, profile):
                Path(output_path).write_bytes(b"principal")
                captured["principal_path"] = Path(output_path)
                return StudioMontageResult(
                    output_path=Path(output_path),
                    command=("ffmpeg",),
                    expected_duration=2.0,
                    generated_duration=2.0,
                    clip_count=2,
                    preparation_duration=0.1,
                    montage_duration=0.2,
                )

            montage_service.compose.side_effect = compose
            result = self.coordinator.run_montage(
                plan,
                music_path=Path("music.mp3"),
                intro_outro_selection="intro-outro",
                project=project,
                profile_resolver=profile_resolver,
                profile_loader=profile_loader,
                output_path_resolver=output_resolver,
                montage_service=montage_service,
                render_service=renderer,
            )

        self.assertIsInstance(result, StudioMontageRenderResult)
        project.setup.assert_called_once_with()
        profile_resolver.load_operational.assert_called_once_with(
            self.profile_key,
        )
        self.assertEqual(
            [({"raw": True}, self.profile_key)],
            profile_loader.calls,
        )
        montage_service.compose.assert_called_once_with(
            plan=plan,
            output_path=captured["principal_path"],
            profile=self.profile,
        )
        self.assertEqual(
            captured["principal_path"],
            renderer.options["video_path"],
        )
        self.assertNotIn("subtitle_path", renderer.options)
        self.assertNotIn("subtitle_profile", renderer.options)
        self.assertEqual(Path("music.mp3"), renderer.options["music_path"])
        self.assertEqual(
            "intro-outro",
            renderer.options["intro_outro_selection"],
        )
        self.assertEqual(output_path, renderer.options["output_path"])
        self.assertFalse(captured["principal_path"].exists())


if __name__ == "__main__":
    unittest.main()
