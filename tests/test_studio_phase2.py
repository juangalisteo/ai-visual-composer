import hashlib
import shutil
import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.core.execution_request import (
    ApplicationExecutionRequest,
    StudioExecutionRequest,
)
from app.core.start import (
    run_application,
)
from app.modules.studio.execution_coordinator import StudioExecutionCoordinator
from app.managers.project_manager import ProjectManager
from app.modules.studio import (
    StudioInputMode,
    StudioOutputPathResolver,
    StudioOutputValidator,
    StudioProfileLoader,
    StudioRenderService,
)
from app.shared.media_probe import MediaInfo, MediaProbe
from app.shared.profile_identity import OperationalProfileKey
from app.shared.profile_resolver import ProfileResolver
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


STUDIO_PROFILE_IDS = {
    "vertical": "studio_vertical",
    "horizontal": "studio_horizontal",
}

STUDIO_SINGLE_LINE_SUBTITLE_PROFILE_IDS = {
    "vertical": "subtitulo_studio_vertical_linea_unica",
    "horizontal": "subtitulo_studio_horizontal_linea_unica",
}


def _load_studio_profile(profile_key):
    operational_key = OperationalProfileKey(
        profile_key.component,
        profile_key.format,
        profile_key.profile_id,
    )
    return StudioProfileLoader().load(
        ProfileResolver().load_operational(operational_key),
        operational_key,
    )


class StudioPhase2Test(unittest.TestCase):

    def setUp(self):
        self.profile_key = OperationalProfileKey(
            "studio", "vertical", "studio_vertical"
        )
        self.profile = _load_studio_profile(self.profile_key)
        self.subtitle_profile = SubtitleProfileResolver().load(
            SubtitleProfileKey(
                "studio", "vertical",
                "subtitulo_studio_vertical_linea_unica", "estandar",
            )
        )
        self.source_info = MediaInfo(
            duration=2.0,
            width=640,
            height=360,
            fps=24.0,
            pixel_format="yuv420p",
            video_codec="h264",
            audio_codec="aac",
            audio_sample_rate=44100,
            audio_channels=1,
        )

    def _sources(self, root):
        video_path = root / "external source.mp4"
        subtitle_path = root / "external captions.srt"
        video_path.write_bytes(b"source-video")
        subtitle_path.write_bytes(
            b"1\r\n00:00:00,300 --> 00:00:01,200\r\nTexto intacto\r\n"
        )
        return video_path, subtitle_path

    def _service(self, source_info=None, runner=None, validator=None):
        probe = Mock()
        probe.inspect.return_value = source_info or self.source_info
        return StudioRenderService(
            runner=runner or Mock(),
            probe=probe,
            output_validator=validator or Mock(),
        )

    def test_phase_two_passes_phase_one_contract_to_renderer(self):
        preparation = SimpleNamespace(
            video_path=Path("input/studio/srt_video/source.mp4"),
            subtitle_path=Path("input/studio/srt_video/source.srt"),
            input_mode="srt_video",
            profile_key=self.profile_key,
            profile=self.profile,
            subtitle_profile=self.subtitle_profile,
        )
        prepare = Mock(return_value=preparation)
        renderer = Mock()
        renderer.render.return_value = "rendered"
        resolver = Mock()
        resolver.resolve.return_value = Path("output/studio/result.mp4")
        project = Mock()

        base_path = Path("output/studio/subtitles/result.srt")
        derived_path = Path("output/studio/subtitles/result_three_two_words.srt")
        with patch.object(
            StudioExecutionCoordinator,
            "persist_subtitle_base",
            return_value=base_path,
        ), patch.object(
            StudioExecutionCoordinator,
            "persist_render_subtitle",
            return_value=derived_path,
        ):
            result = StudioExecutionCoordinator().run_standard(
                subtitle_profile_key=self.subtitle_profile.key,
                input_mode="srt_video",
                preparation_service=prepare,
                render_service=renderer,
                output_path_resolver=resolver,
                project=project,
            )

        self.assertEqual("rendered", result)
        prepare.assert_called_once_with(
            subtitle_profile_key=self.subtitle_profile.key,
            input_mode="srt_video",
        )
        resolver.resolve.assert_called_once_with(
            profile_key=preparation.profile_key,
            project=project,
        )
        renderer.render.assert_called_once_with(
            video_path=preparation.video_path,
            subtitle_path=derived_path,
            profile_key=preparation.profile_key,
            profile=preparation.profile,
            subtitle_profile=preparation.subtitle_profile,
            output_path=Path("output/studio/result.mp4"),
            music_path=None,
        )

    def test_runtime_studio_bypasses_all_audiovisual_builders(self):
        request = ApplicationExecutionRequest(
            project_name="demo",
            clear_output=False,
            operational_profile_key=self.profile_key,
            subtitle_profile_key=self.subtitle_profile.key,
            route=StudioExecutionRequest(input_mode=StudioInputMode.SRT_VIDEO),
        )
        with patch.object(StudioExecutionCoordinator, "run_standard") as studio, patch(
            "app.core.start.ProjectManager"
        ) as projects, patch("app.modules.standard.execution_coordinator.VideoBuilder") as video, patch(
            "app.modules.standard.execution_coordinator.SrtOptimizer"
        ) as optimizer:
            run_application(request=request)

        studio.assert_called_once()
        self.assertEqual(
            self.subtitle_profile.key,
            studio.call_args.kwargs["subtitle_profile_key"],
        )
        self.assertIsNone(studio.call_args.kwargs["music_path"])
        self.assertEqual("srt_video", studio.call_args.kwargs["input_mode"])
        projects.assert_called_once_with(project_name="demo")
        video.assert_not_called()
        optimizer.assert_not_called()

    def test_output_uses_standard_project_path_and_collision_is_visible(self):
        project = Mock()
        project.video_path.return_value = Path(
            "output/Proyecto Studio/video/Proyecto Studio.mp4"
        )
        resolver = StudioOutputPathResolver(project)
        first = resolver.resolve(
            self.profile_key,
        )
        second = resolver.resolve(
            self.profile_key,
        )
        self.assertEqual(first, second)
        self.assertEqual(
            Path(
                "output/Proyecto Studio/video/Proyecto Studio.mp4"
            ),
            first,
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video_path, subtitle_path = self._sources(root)
            output_path = root / "existing.mp4"
            output_path.write_bytes(b"valid-existing")
            with self.assertRaises(FileExistsError):
                self._service().render(
                    video_path,
                    subtitle_path,
                    self.profile_key,
                    self.profile,
                    self.subtitle_profile,
                    output_path,
                )
            self.assertEqual(b"valid-existing", output_path.read_bytes())

    def test_default_output_resolver_uses_project_manager_contract(self):
        output_path = StudioOutputPathResolver().resolve(
            self.profile_key,
            project=ProjectManager(project_name="Proyecto Studio"),
        )

        self.assertEqual(
            Path("output/Proyecto Studio/video/Proyecto Studio.mp4"),
            output_path,
        )

    def test_command_uses_one_scale_pad_subtitle_render_without_crop(self):
        service = StudioRenderService()
        command = service.build_command(
            video_path="source.mp4",
            subtitle_path="source.srt",
            output_path="result.rendering.mp4",
            source_info=self.source_info,
            profile=self.profile,
            subtitle_style="FontName=UniSansHeavyCAPS,FontSize=10",
        )
        graph = command[command.index("-filter_complex") + 1]
        self.assertIn("scale=1080:1920:force_original_aspect_ratio=decrease", graph)
        self.assertIn("pad=1080:1920:(ow-iw)/2:(oh-ih)/2", graph)
        self.assertIn("subtitles=", graph)
        self.assertIn("FontName=UniSansHeavyCAPS,FontSize=10", graph)
        self.assertNotIn("crop=", graph)
        self.assertEqual(1, command.count("-c:v"))
        self.assertNotIn("anullsrc=", " ".join(command))
        self.assertIn("[0:a:0]aresample=48000", graph)

    def test_no_audio_adds_explicit_stereo_silence(self):
        silent_info = MediaInfo(
            **{
                **self.source_info.__dict__,
                "audio_codec": None,
                "audio_sample_rate": None,
                "audio_channels": None,
            }
        )
        command = StudioRenderService().build_command(
            "source.mp4",
            "source.srt",
            "result.mp4",
            silent_info,
            self.profile,
            "FontName=Arial",
        )
        self.assertIn("anullsrc=r=48000:cl=stereo", command)
        graph = command[command.index("-filter_complex") + 1]
        self.assertIn("[1:a:0]aresample=48000", graph)

    def test_vertical_and_horizontal_keep_independent_output_contracts(self):
        horizontal_key = OperationalProfileKey("studio", "horizontal", "studio_horizontal")
        horizontal_profile = _load_studio_profile(horizontal_key)
        vertical_command = StudioRenderService().build_command(
            "source.mp4",
            "source.srt",
            "vertical.mp4",
            self.source_info,
            self.profile,
            "FontName=Arial",
        )
        horizontal_command = StudioRenderService().build_command(
            "source.mp4",
            "source.srt",
            "horizontal.mp4",
            self.source_info,
            horizontal_profile,
            "FontName=Arial",
        )
        vertical_graph = vertical_command[
            vertical_command.index("-filter_complex") + 1
        ]
        horizontal_graph = horizontal_command[
            horizontal_command.index("-filter_complex") + 1
        ]
        self.assertIn("scale=1080:1920", vertical_graph)
        self.assertIn("scale=1920:1080", horizontal_graph)
        self.assertEqual("slow", horizontal_profile.preset)
        self.assertEqual(16, horizontal_profile.crf)
        self.assertEqual(30, horizontal_profile.fps)

    def test_command_uses_render_style_with_supplied_render_srt(self):
        command = StudioRenderService().build_command(
            "source.mp4",
            "authoritative.srt",
            "result.mp4",
            self.source_info,
            self.profile,
            StudioRenderService().style_builder.build(
                self.subtitle_profile.render_style
            ),
        )
        graph = command[command.index("-filter_complex") + 1]
        self.assertIn("FontName=UniSansHeavyCAPS", graph)
        self.assertIn("FontSize=10", graph)
        self.assertIn("Alignment=2", graph)
        self.assertIn("MarginV=55", graph)
        video_graph = graph.split("[vout]", 1)[0]
        self.assertEqual(1, video_graph.count("setpts=PTS-STARTPTS"))
        self.assertNotIn("0.060000/TB", graph)
        self.assertIn("authoritative.srt", graph)

    def test_nonzero_offset_is_rejected_to_preserve_authoritative_timings(self):
        shifted_profile = replace(
            self.subtitle_profile,
            render_style={
                **self.subtitle_profile.render_style,
                "offset": -0.06,
            },
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video_path, subtitle_path = self._sources(root)
            with self.assertRaisesRegex(ValueError, "offset=0"):
                self._service().render(
                    video_path,
                    subtitle_path,
                    self.profile_key,
                    self.profile,
                    shifted_profile,
                    root / "result.mp4",
                )

    def test_cue_policy_is_applied_only_to_derived_render_srt(self):
        uppercase_profile = replace(
            self.subtitle_profile,
            cue_policy={
                "mode": "word_by_word",
                "min_duration": 0.3,
                "max_duration": 1.2,
                "significant_gap_threshold": 0.35,
                "micro_cues": {
                    "enabled": True,
                    "min_frames": 1,
                    "min_display_seconds": 0.05,
                    "merge_preference": "next",
                },
                "text_case": "uppercase",
                "punctuation": {
                    "remove_commas": False,
                    "remove_periods": False,
                    "remove_colons": False,
                    "remove_semicolons": False,
                    "remove_question_marks": False,
                    "remove_exclamation_marks": False,
                    "remove_ellipsis": False,
                    "remove_hyphens": False,
                    "remove_em_dashes": False,
                    "remove_double_quotes": False,
                    "remove_single_quotes": False,
                    "remove_parentheses": False,
                },
            },
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video_path, subtitle_path = self._sources(root)
            original = subtitle_path.read_bytes()
            rendered_path = StudioExecutionCoordinator.persist_render_subtitle(
                base_subtitle_path=subtitle_path,
                output_path=root / "demo" / "video" / "demo.mp4",
                subtitle_profile=uppercase_profile,
                render_fps=self.profile.fps,
            )

            self.assertIn("TEXTO", rendered_path.read_text(encoding="utf-8"))
            self.assertIn("INTACTO", rendered_path.read_text(encoding="utf-8"))
            self.assertEqual(original, subtitle_path.read_bytes())

    def test_render_preserves_sources_and_promotes_only_after_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video_path, subtitle_path = self._sources(root)
            output_path = root / "output" / "result.mp4"
            before_video = hashlib.sha256(video_path.read_bytes()).digest()
            before_srt = hashlib.sha256(subtitle_path.read_bytes()).digest()
            events = []
            runner = Mock()

            def render(command):
                events.append("render")
                Path(command[-1]).write_bytes(b"temporary")

            runner.run.side_effect = render
            validator = Mock()

            def validate(**kwargs):
                events.append("validate")
                self.assertTrue(Path(kwargs["output_path"]).exists())
                self.assertFalse(output_path.exists())
                return 2.0

            validator.validate.side_effect = validate
            service = self._service(runner=runner, validator=validator)
            original_promote = service.promote

            def promote(temporary, final):
                events.append("promote")
                original_promote(temporary, final)

            service.promote = promote
            result = service.render(
                video_path,
                subtitle_path,
                self.profile_key,
                self.profile,
                self.subtitle_profile,
                output_path,
            )

            self.assertEqual(["render", "validate", "promote"], events)
            self.assertEqual(output_path, result.output_path)
            self.assertTrue(output_path.exists())
            self.assertFalse(output_path.with_name("result.rendering.mp4").exists())
            self.assertEqual(before_video, hashlib.sha256(video_path.read_bytes()).digest())
            self.assertEqual(before_srt, hashlib.sha256(subtitle_path.read_bytes()).digest())

    def test_render_or_validation_failure_never_leaves_final_or_temporary(self):
        for stage in ("render", "validate"):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                video_path, subtitle_path = self._sources(root)
                output_path = root / "result.mp4"
                runner = Mock()
                validator = Mock()
                if stage == "render":
                    runner.run.side_effect = RuntimeError("render failed")
                else:
                    runner.run.side_effect = lambda command: Path(command[-1]).write_bytes(b"bad")
                    validator.validate.side_effect = RuntimeError("invalid")
                service = self._service(runner=runner, validator=validator)
                with self.assertRaises(RuntimeError):
                    service.render(
                        video_path,
                        subtitle_path,
                        self.profile_key,
                        self.profile,
                        self.subtitle_profile,
                        output_path,
                    )
                self.assertFalse(output_path.exists())
                self.assertFalse(root.joinpath("result.rendering.mp4").exists())

    def test_profile_and_subtitle_formats_cannot_cross(self):
        horizontal_subtitles = SubtitleProfileResolver().load(
            SubtitleProfileKey(
                "studio",
                "horizontal",
                "subtitulo_studio_horizontal_linea_unica",
                "estandar",
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            video_path, subtitle_path = self._sources(Path(directory))
            with self.assertRaisesRegex(ValueError, "compartir formato"):
                self._service().render(
                    video_path,
                    subtitle_path,
                    self.profile_key,
                    self.profile,
                    horizontal_subtitles,
                    Path(directory) / "result.mp4",
                )

    def test_output_validator_checks_contract_and_decodes_both_streams(self):
        probe = Mock()
        probe.inspect.return_value = MediaInfo(
            duration=2.0,
            width=1080,
            height=1920,
            fps=30.0,
            pixel_format="yuv420p",
            video_codec="h264",
            audio_codec="aac",
            audio_sample_rate=48000,
            audio_channels=2,
        )
        base_validator = Mock()
        base_validator.validate.return_value = 2.0
        runner = Mock()
        generated = StudioOutputValidator(
            probe=probe,
            validator=base_validator,
            runner=runner,
        ).validate("result.mp4", 2.0, self.profile)
        self.assertEqual(2.0, generated)
        decode = runner.run.call_args.args[0]
        self.assertEqual(2, decode.count("-map"))
        self.assertIn("0:v:0", decode)
        self.assertIn("0:a:0", decode)

    def test_output_validator_rejects_wrong_technical_contract(self):
        probe = Mock()
        probe.inspect.return_value = MediaInfo(
            duration=2.0,
            width=1920,
            height=1080,
            fps=24.0,
            pixel_format="yuv444p",
            video_codec="hevc",
            audio_codec=None,
            audio_sample_rate=None,
            audio_channels=None,
        )
        base_validator = Mock()
        base_validator.validate.return_value = 2.0
        runner = Mock()
        with self.assertRaisesRegex(RuntimeError, "incumple el contrato"):
            StudioOutputValidator(
                probe=probe,
                validator=base_validator,
                runner=runner,
            ).validate("result.mp4", 2.0, self.profile)
        runner.run.assert_not_called()

    def test_studio_media_files_are_ignored_but_gitkeep_is_not(self):
        for path in (
            "input/studio/srt_video/source.mp4",
            "input/studio/srt_video/source.srt",
            "input/studio/video/source.mp4",
        ):
            result = subprocess.run(
                ["git", "check-ignore", "-q", path],
                check=False,
            )
            self.assertEqual(0, result.returncode)
        result = subprocess.run(
            [
                "git", "check-ignore", "-q",
                "input/studio/srt_video/.gitkeep",
            ],
            check=False,
        )
        self.assertNotEqual(0, result.returncode)


@unittest.skipUnless(
    shutil.which("ffmpeg") and shutil.which("ffprobe"),
    "FFmpeg y FFprobe son obligatorios para la prueba real STUDIO.",
)
class StudioPhase2RealFFmpegTest(unittest.TestCase):

    def _profile(self, profile_format="vertical"):
        key = OperationalProfileKey(
            "studio", profile_format, STUDIO_PROFILE_IDS[profile_format]
        )
        profile = _load_studio_profile(key)
        subtitles = SubtitleProfileResolver().load(
            SubtitleProfileKey(
                "studio",
                profile_format,
                STUDIO_SINGLE_LINE_SUBTITLE_PROFILE_IDS[profile_format],
                "estandar",
            )
        )
        return key, profile, subtitles

    def _source(self, path, with_audio=True, size="320x180", color="red"):
        command = [
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            f"color=c={color}:s={size}:r=24:d=1.5",
        ]
        if with_audio:
            command.extend([
                "-f", "lavfi", "-i", "sine=frequency=440:duration=1.5",
                "-shortest",
            ])
        command.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p"])
        if with_audio:
            command.extend(["-c:a", "aac"])
        command.append(str(path))
        subprocess.run(command, capture_output=True, check=True)

    def _srt(self, path):
        path.write_text(
            "1\n00:00:00,300 --> 00:00:01,200\nSTUDIO TEST\n",
            encoding="utf-8",
        )

    def _render(self, root, with_audio=True, size="320x180", color="red"):
        key, profile, subtitles = self._profile()
        source = root / "source.mp4"
        srt = root / "source.srt"
        output = root / "result.mp4"
        self._source(source, with_audio=with_audio, size=size, color=color)
        self._srt(srt)
        source_hash = hashlib.sha256(source.read_bytes()).digest()
        srt_hash = hashlib.sha256(srt.read_bytes()).digest()
        result = StudioRenderService().render(
            source,
            srt,
            key,
            profile,
            subtitles,
            output,
        )
        self.assertEqual(source_hash, hashlib.sha256(source.read_bytes()).digest())
        self.assertEqual(srt_hash, hashlib.sha256(srt.read_bytes()).digest())
        return result, MediaProbe.inspect(output)

    def _pixel(self, path, x, y):
        result = subprocess.run(
            [
                "ffmpeg", "-v", "error", "-ss", "0.100", "-i", str(path),
                "-vf", f"crop=1:1:{x}:{y},format=rgb24", "-frames:v", "1",
                "-f", "rawvideo", "-",
            ],
            capture_output=True,
            check=True,
        )
        return tuple(result.stdout[:3])

    def _subtitle_frame_peak(self, path):
        result = subprocess.run(
            [
                "ffmpeg", "-v", "error", "-ss", "0.700", "-i", str(path),
                "-vf", "signalstats,metadata=print:file=-", "-frames:v", "1",
                "-f", "null", "-",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        values = [
            float(line.split("=", 1)[1])
            for line in result.stdout.splitlines()
            if "lavfi.signalstats.YMAX=" in line
        ]
        self.assertTrue(values)
        return values[-1]

    def test_real_audio_source_renders_subtitles_and_valid_output(self):
        with tempfile.TemporaryDirectory() as directory:
            result, info = self._render(Path(directory), with_audio=True, color="black")
            self.assertTrue(info.has_audio)
            self.assertFalse(result.silence_added)
            self.assertLessEqual(abs(info.duration - 1.5), 0.2)
            self.assertGreater(self._subtitle_frame_peak(result.output_path), 32.0)

    def test_real_silent_source_receives_compatible_silence(self):
        with tempfile.TemporaryDirectory() as directory:
            result, info = self._render(Path(directory), with_audio=False)
            self.assertTrue(result.silence_added)
            self.assertEqual("aac", info.audio_codec)
            self.assertEqual(48000, info.audio_sample_rate)
            self.assertEqual(2, info.audio_channels)

    def test_real_mismatched_aspect_ratio_uses_centered_scale_and_pad(self):
        with tempfile.TemporaryDirectory() as directory:
            result, info = self._render(
                Path(directory),
                with_audio=True,
                size="320x180",
                color="red",
            )
            self.assertEqual((1080, 1920), (info.width, info.height))
            corner = self._pixel(result.output_path, 10, 10)
            center = self._pixel(result.output_path, 540, 960)
            self.assertLess(sum(corner), 80)
            self.assertGreater(sum(center), sum(corner) + 80)


if __name__ == "__main__":
    unittest.main()
