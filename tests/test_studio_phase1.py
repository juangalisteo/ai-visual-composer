import json
import os
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import main
from app.controllers.interaction.contracts import (
    StudioOperationalSelection,
    StudioProfileSelection,
    StudioSubtitleSelection,
)
from app.controllers.run_controller import RunController
from app.core.start import ejecutar_studio, preparar_studio, iniciar
from app.modules.studio import (
    StudioInputPreparationService,
    StudioInputMode,
    StudioProfileLoader,
)
from app.shared.config_manager import ConfigManager
from app.shared.operational_error import OperationalError
from app.shared.profile_identity import (
    OperationalProfileKey,
    ProfileComponent,
)
from app.shared.profile_resolver import ProfileResolver
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


STUDIO_INSTAGRAM_THREE_TWO_PROFILE_ID = (
    "subtitulo_studio_instagram_dos_tres"
)
STUDIO_INSTAGRAM_THREE_TWO_KEY = SubtitleProfileKey(
    "studio",
    "instagram",
    STUDIO_INSTAGRAM_THREE_TWO_PROFILE_ID,
    "estandar",
)


STUDIO_PROFILE_IDS = {
    "instagram": "studio_instagram",
    "youtube": "studio_youtube",
}


class StudioPhase1Test(unittest.TestCase):

    def setUp(self):
        self.profile_key = OperationalProfileKey(
            ProfileComponent.STUDIO,
            "instagram",
            "studio_instagram",
        )
        self.operational_key = OperationalProfileKey(
            ProfileComponent.STUDIO,
            "instagram",
            "studio_instagram",
        )
        self.profile = StudioProfileLoader().load(
            ProfileResolver().load_operational(self.operational_key),
            self.operational_key,
        )

    def test_studio_is_an_official_component_with_exact_profiles(self):
        resolver = ProfileResolver()
        self.assertEqual(ProfileComponent.STUDIO.value, "studio")
        self.assertEqual(
            Path(
                "config/profiles/studio/instagram/"
                "perfil_studio_instagram.json"
            ),
            resolver.resolve_operational(self.operational_key),
        )
        youtube_operational_key = OperationalProfileKey(
            "studio", "youtube", "studio_youtube"
        )
        self.assertEqual(
            Path(
                "config/profiles/studio/youtube/"
                "perfil_studio_youtube.json"
            ),
            resolver.resolve_operational(youtube_operational_key),
        )

    def test_studio_does_not_fall_back_to_video_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video_path = root / "video/instagram"
            video_path.mkdir(parents=True)
            (video_path / "perfil_video_instagram.json").write_text(
                "{}",
                encoding="utf-8",
            )
            with self.assertRaises(OperationalError) as captured:
                ProfileResolver(root).resolve_operational(self.operational_key)
            self.assertEqual("PROFILE", captured.exception.context.family)
            self.assertIsInstance(captured.exception.__cause__, FileNotFoundError)

    def test_studio_subtitle_profiles_are_exact_and_independent(self):
        resolver = SubtitleProfileResolver()
        resolved = []
        for platform in ("instagram", "youtube"):
            profile_key = OperationalProfileKey(
                "studio", platform, STUDIO_PROFILE_IDS[platform]
            )
            for descriptor in resolver.discover_profiles_for_family(
                "studio", platform, "estandar",
            ):
                profile = resolver.load(descriptor.key)
                resolved.append(profile.path)
                self.assertEqual(profile_key.component, profile.key.component)
                self.assertEqual(profile_key.platform, profile.key.platform)
        self.assertEqual(len(resolved), len(set(resolved)))

    def test_studio_subtitle_discovery_rejects_an_unregistered_future_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "profiles"
            subtitle_dir = root / "studio/instagram/estandar/subtitulos"
            subtitle_dir.mkdir(parents=True)
            data = {
                "component": "studio",
                "platform": "instagram",
                "family": "estandar",
                "profile_id": "subtitulo_studio_instagram_cinematografico",
                "display_name": "Cinematografico",
                "cue_policy": {"mode": "cinematografico"},
                "render_style": {
                    "font": "unisans",
                    "font_size": 14,
                    "bold": False,
                    "primary_colour": "&H00FFFFFF",
                    "outline_colour": "&H80000000",
                    "back_colour": "&H00000000",
                    "border_style": 1,
                    "outline": 0,
                    "shadow": 1,
                    "alignment": 2,
                    "margin_v": 55,
                    "offset": 0.0,
                },
            }
            path = subtitle_dir / "subtitulo_studio_instagram_cinematografico.json"
            path.write_text(json.dumps(data), encoding="utf-8")

            resolver = SubtitleProfileResolver(root)
            with self.assertRaises(OperationalError) as captured:
                resolver.discover_profiles_for_family(
                    "studio", "instagram", "estandar",
                )
            self.assertEqual("VALIDATION", captured.exception.context.family)
            self.assertIsInstance(captured.exception.__cause__, ValueError)

    def test_input_accepts_one_dynamic_mp4_and_one_valid_srt_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            input_root = Path(directory)
            input_dir = input_root / "srt_video"
            input_dir.mkdir()
            video_path = input_dir / "source-export.MP4"
            subtitle_path = input_dir / "captions-final.SRT"
            video_bytes = b"external video bytes"
            subtitle_bytes = (
                b"1\r\n00:00:00,000 --> 00:00:01,000\r\nHola Studio\r\n"
            )
            video_path.write_bytes(video_bytes)
            subtitle_path.write_bytes(subtitle_bytes)
            (input_dir / "notes.txt").write_text("ignored", encoding="utf-8")

            prepared = StudioInputPreparationService(input_root).prepare(
                self.profile,
                StudioInputMode.SRT_VIDEO,
            )

            self.assertEqual(video_path, prepared.video_path)
            self.assertEqual(subtitle_path, prepared.subtitle_path)
            self.assertEqual(video_bytes, video_path.read_bytes())
            self.assertEqual(subtitle_bytes, subtitle_path.read_bytes())

    def test_input_rejects_missing_or_ambiguous_candidates(self):
        cases = (
            ((), ("captions.srt",), "MP4"),
            (("one.mp4", "two.mp4"), ("captions.srt",), "ambigua"),
            (("source.mp4",), (), "SRT"),
            (("source.mp4",), ("one.srt", "two.srt"), "ambigua"),
        )
        for videos, subtitles, error in cases:
            with self.subTest(videos=videos, subtitles=subtitles), tempfile.TemporaryDirectory() as directory:
                input_root = Path(directory)
                input_dir = input_root / "srt_video"
                input_dir.mkdir()
                for name in videos:
                    (input_dir / name).write_bytes(b"video")
                for name in subtitles:
                    (input_dir / name).write_text(
                        "1\n00:00:00,000 --> 00:00:01,000\nHola\n",
                        encoding="utf-8",
                    )
                with self.assertRaisesRegex((FileNotFoundError, ValueError), error):
                    StudioInputPreparationService(input_root).prepare(
                        self.profile,
                        StudioInputMode.SRT_VIDEO,
                    )

    def test_input_accepts_explicit_selection_from_multiple_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            input_root = Path(directory)
            input_dir = input_root / "srt_video"
            input_dir.mkdir()
            first_video = input_dir / "first.mp4"
            second_video = input_dir / "second.mp4"
            first_srt = input_dir / "first.srt"
            second_srt = input_dir / "second.srt"
            for video in (first_video, second_video):
                video.write_bytes(b"video")
            for subtitle in (first_srt, second_srt):
                subtitle.write_text(
                    "1\n00:00:00,000 --> 00:00:01,000\nHola\n",
                    encoding="utf-8",
                )

            prepared = StudioInputPreparationService(input_root).prepare(
                self.profile,
                StudioInputMode.SRT_VIDEO,
                video_path=second_video,
                subtitle_path=first_srt,
            )

        self.assertEqual(second_video, prepared.video_path)
        self.assertEqual(first_srt, prepared.subtitle_path)

    def test_controller_skips_file_menus_for_single_video(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video_directory = root / "video"
            video_directory.mkdir()
            source = video_directory / "source.mp4"
            source.write_bytes(b"video")
            controller = RunController(
                studio_input_preparation_service=(
                    StudioInputPreparationService(root)
                )
            )
            with patch.object(controller, "_print") as printed, patch(
                "builtins.input"
            ) as user_input:
                prepared = controller.select_studio_input_files(
                    self.profile,
                    StudioInputMode.VIDEO,
                )

        self.assertEqual(source, prepared.video_path)
        self.assertIsNone(prepared.subtitle_path)
        printed.assert_not_called()
        user_input.assert_not_called()

    def test_controller_skips_file_menus_for_single_srt_video_pair(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_directory = root / "srt_video"
            source_directory.mkdir()
            video = source_directory / "source.mp4"
            subtitle = source_directory / "captions.srt"
            video.write_bytes(b"video")
            subtitle.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\nHola\n",
                encoding="utf-8",
            )
            controller = RunController(
                studio_input_preparation_service=(
                    StudioInputPreparationService(root)
                )
            )
            with patch.object(controller, "_print") as printed, patch(
                "builtins.input"
            ) as user_input:
                prepared = controller.select_studio_input_files(
                    self.profile,
                    StudioInputMode.SRT_VIDEO,
                )

        self.assertEqual(video, prepared.video_path)
        self.assertEqual(subtitle, prepared.subtitle_path)
        printed.assert_not_called()
        user_input.assert_not_called()

    def test_controller_shows_video_menu_for_multiple_video_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video_directory = root / "video"
            video_directory.mkdir()
            first = video_directory / "first.mp4"
            second = video_directory / "second.mp4"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            controller = RunController(
                studio_input_preparation_service=(
                    StudioInputPreparationService(root)
                )
            )
            with patch("builtins.input", return_value="2"), patch.object(
                controller, "_print"
            ) as printed:
                prepared = controller.select_studio_input_files(
                    self.profile,
                    StudioInputMode.VIDEO,
                )

        output = "\n".join(
            str(call.args[0])
            for call in printed.call_args_list
            if call.args
        )
        self.assertEqual(second, prepared.video_path)
        self.assertIn("VIDEO", output)
        self.assertIn("first.mp4", output)
        self.assertIn("second.mp4", output)

    def test_controller_selects_both_srt_video_files_when_not_exactly_one_each(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_directory = root / "srt_video"
            source_directory.mkdir()
            first_video = source_directory / "first.mp4"
            second_video = source_directory / "second.mp4"
            subtitle = source_directory / "captions.srt"
            first_video.write_bytes(b"first")
            second_video.write_bytes(b"second")
            subtitle.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\nHola\n",
                encoding="utf-8",
            )
            controller = RunController(
                studio_input_preparation_service=(
                    StudioInputPreparationService(root)
                )
            )
            with patch("builtins.input", side_effect=("2", "1")), patch.object(
                controller, "_print"
            ) as printed:
                prepared = controller.select_studio_input_files(
                    self.profile,
                    StudioInputMode.SRT_VIDEO,
                )

        output = "\n".join(
            str(call.args[0])
            for call in printed.call_args_list
            if call.args
        )
        self.assertEqual(second_video, prepared.video_path)
        self.assertEqual(subtitle, prepared.subtitle_path)
        self.assertIn("VIDEO", output)
        self.assertIn("SRT", output)
        self.assertIn("first.mp4", output)
        self.assertIn("captions.srt", output)

    def test_input_rejects_empty_or_unusable_srt(self):
        for content in ("", "not a cue"):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as directory:
                input_root = Path(directory)
                input_dir = input_root / "srt_video"
                input_dir.mkdir()
                (input_dir / "source.mp4").write_bytes(b"video")
                (input_dir / "captions.srt").write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError):
                    StudioInputPreparationService(input_root).prepare(
                        self.profile,
                        StudioInputMode.SRT_VIDEO,
                    )

    def test_profile_contract_fails_fast_for_missing_critical_field(self):
        raw = ProfileResolver().load_operational(self.operational_key)
        incomplete = deepcopy(raw)
        del incomplete["studio"]["output"]["video"]["crf"]
        with self.assertRaisesRegex(ValueError, "studio.output.video.crf"):
            StudioProfileLoader().load(incomplete, self.profile_key)

    def test_transition_duration_is_isolated_by_studio_platform(self):
        youtube_operational_key = OperationalProfileKey(
            "studio", "youtube", "studio_youtube"
        )
        youtube_profile = StudioProfileLoader().load(
            ProfileResolver().load_operational(youtube_operational_key),
            youtube_operational_key,
        )

        self.assertEqual(0.25, self.profile.transition_duration)
        self.assertEqual(0.50, youtube_profile.transition_duration)

    def test_transition_duration_fails_fast_when_missing_or_invalid(self):
        raw = ProfileResolver().load_operational(self.operational_key)
        invalid_values = (
            ("missing", None),
            ("zero", 0),
            ("negative", -0.1),
            ("text", "invalid"),
            ("nan", float("nan")),
            ("infinite", float("inf")),
        )

        for label, value in invalid_values:
            with self.subTest(label=label):
                invalid = deepcopy(raw)
                if label == "missing":
                    del invalid["studio"]["montage"]["transition_duration"]
                else:
                    invalid["studio"]["montage"]["transition_duration"] = value
                with self.assertRaisesRegex(
                    (ValueError, TypeError),
                    "studio.montage.transition_duration",
                ):
                    StudioProfileLoader().load(invalid, self.profile_key)

    def test_run_controller_transports_studio_without_future_options(self):
        controller = RunController()
        order = []
        with patch.object(
            controller,
            "select_visual_pipeline",
            return_value="studio",
        ), patch.object(
            controller,
            "_select_studio_profile_selection",
            side_effect=lambda *_: (
                order.append("subtitle"),
                StudioProfileSelection(
                    operational=StudioOperationalSelection(
                        self.profile_key,
                        self.profile,
                    ),
                    subtitle=StudioSubtitleSelection(
                        SubtitleProfileKey(
                            "studio",
                            "instagram",
                            "subtitulo_studio_instagram_linea_unica",
                            "estandar",
                        ),
                        False,
                    ),
                ),
            )[-1],
        ), patch.object(
            controller,
            "select_studio_input_mode",
            side_effect=lambda: order.append("input") or "srt_video",
        ), patch.object(
            controller,
            "select_studio_input_files",
            return_value=SimpleNamespace(
                video_path=Path("input/studio/srt_video/source.mp4"),
                subtitle_path=Path("input/studio/srt_video/source.srt"),
            ),
        ), patch.object(
            controller,
            "select_studio_music",
            return_value=None,
        ), patch.object(
            controller,
            "select_studio_intro_outro",
            return_value=None,
        ), patch.object(
            controller,
            "ask_project_name",
            return_value="studio project",
        ), patch.object(
            controller,
            "ask_clear_output",
            return_value=True,
        ):
            options = controller.run()

        self.assertEqual("studio", options["pipeline_mode"])
        self.assertEqual("studio", options["profile_component"])
        self.assertEqual(
            "subtitulo_studio_instagram_linea_unica",
            options["subtitle_config"],
        )
        self.assertFalse(options["studio_subtitle_original"])
        self.assertEqual("srt_video", options["studio_input_mode"])
        self.assertEqual(
            str(Path("input/studio/srt_video/source.mp4")),
            options["studio_video_path"],
        )
        self.assertEqual(
            str(Path("input/studio/srt_video/source.srt")),
            options["studio_subtitle_path"],
        )
        self.assertNotIn("studio_light_leaks_enabled", options)
        self.assertIsNone(options["studio_music_path"])
        self.assertEqual("studio project", options["project_name"])
        self.assertTrue(options["clear_output"])
        self.assertNotIn("overlays_mode", options)
        self.assertIsNone(options["intro_outro_selection"])
        self.assertEqual(["input", "subtitle"], order)

    def test_studio_profile_menu_lists_platforms_without_video_profile_label(self):
        with patch("builtins.input", side_effect=("1", "2", "1")), patch(
            "builtins.print"
        ) as print_mock:
            selected = RunController().select_profile("studio")

        printed = "\n".join(
            str(call.args[0])
            for call in print_mock.call_args_list
            if call.args
        )
        self.assertEqual(ProfileComponent.STUDIO, selected["profile_key"].component)
        self.assertIn("1. Instagram", printed)
        self.assertIn("2. Youtube", printed)
        self.assertIn("Línea única", printed)

    def test_main_transports_studio_identity_without_resetting_output(self):
        options = {
            "profile_component": "studio",
            "profile_platform": "instagram",
            "profile_id": "studio_instagram",
            "subtitle_config": "three_two_words",
            "voice_config": "",
            "music_category": None,
            "project_name": "studio transport",
            "visual_pipeline": "studio",
            "script_source": "external",
            "design_target": "",
            "pipeline_mode": "studio",
            "studio_music_path": None,
            "studio_input_mode": "srt_video",
            "studio_video_path": "input/studio/srt_video/source.mp4",
            "studio_subtitle_path": "input/studio/srt_video/source.srt",
            "clear_output": False,
        }
        with patch.dict(os.environ, {}, clear=True), patch(
            "main.RunController"
        ) as controller, patch("main.iniciar") as start, patch(
            "main.OutputManager"
        ) as output_manager:
            controller.return_value.run.return_value = options
            self.assertEqual(0, main.main())
            self.assertNotIn("MC_PROFILE_COMPONENT", os.environ)
            self.assertNotIn("MC_PROFILE_PLATFORM", os.environ)
            self.assertNotIn("MC_PROFILE_ID", os.environ)
            self.assertNotIn("MC_PIPELINE_MODE", os.environ)

        start.assert_called_once()
        request = start.call_args.kwargs["request"]
        self.assertEqual("srt_video", request.route.input_mode.value)
        self.assertEqual(
            Path("input/studio/srt_video/source.mp4"),
            request.route.video_path,
        )
        self.assertEqual(
            Path("input/studio/srt_video/source.srt"),
            request.route.subtitle_path,
        )
        self.assertEqual({"request"}, set(start.call_args.kwargs))
        output_manager.assert_not_called()

    def test_main_resets_output_for_studio_when_selected(self):
        options = {
            "profile_component": "studio",
            "profile_platform": "instagram",
            "profile_id": "studio_instagram",
            "subtitle_config": "three_two_words",
            "voice_config": "",
            "music_category": None,
            "project_name": "studio project",
            "visual_pipeline": "studio",
            "script_source": "external",
            "design_target": "",
            "pipeline_mode": "studio",
            "studio_music_path": None,
            "studio_input_mode": "srt_video",
            "clear_output": True,
        }
        with patch.dict(os.environ, {}, clear=True), patch(
            "main.RunController"
        ) as controller, patch("main.iniciar"), patch(
            "main.OutputManager"
        ) as output_manager:
            controller.return_value.run.return_value = options
            self.assertEqual(0, main.main())
            self.assertNotIn("MC_PROJECT_NAME", os.environ)
        output_manager.return_value.reset.assert_called_once_with()

    def test_start_routes_studio_without_initializing_project(self):
        subtitle_key = SubtitleProfileKey(
            "studio",
            "instagram",
            STUDIO_INSTAGRAM_THREE_TWO_PROFILE_ID,
            "estandar",
        )
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {
                "MC_PIPELINE_MODE": "studio",
                "MC_PROFILE_COMPONENT": "studio",
                "MC_PROFILE_PLATFORM": "instagram",
                "MC_PROFILE_ID": "studio_instagram",
            },
            clear=True,
        ), patch("app.core.start.ProjectManager") as project_manager, patch(
            "app.core.start.ejecutar_studio"
        ) as render:
            iniciar(
                subtitle_profile_key=subtitle_key,
                studio_input_mode="srt_video",
                studio_video_path="input/studio/srt_video/source.mp4",
                studio_subtitle_path="input/studio/srt_video/source.srt",
            )

        render.assert_called_once_with(
            subtitle_profile_key=subtitle_key,
            music_path=None,
            input_mode="srt_video",
            video_path="input/studio/srt_video/source.mp4",
            subtitle_path="input/studio/srt_video/source.srt",
        )
        project_manager.assert_not_called()

    def test_phase_one_preparation_uses_external_input_without_rendering(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {
                "MC_PROFILE_COMPONENT": "studio",
                "MC_PROFILE_PLATFORM": "instagram",
                "MC_PROFILE_ID": "studio_instagram",
            },
            clear=True,
        ):
            input_root = Path(directory)
            input_dir = input_root / "srt_video"
            input_dir.mkdir()
            video_path = input_dir / "clip.mp4"
            subtitle_path = input_dir / "source.srt"
            video_path.write_bytes(b"external")
            subtitle_path.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\nTexto intacto\n",
                encoding="utf-8",
            )
            result = preparar_studio(
                subtitle_profile_key=STUDIO_INSTAGRAM_THREE_TWO_KEY,
                input_mode="srt_video",
                input_preparation_service=StudioInputPreparationService(input_root),
            )

        self.assertEqual(video_path, result.video_path)
        self.assertEqual(subtitle_path, result.subtitle_path)
        self.assertEqual("three_two_words", result.subtitle_profile.cue_policy["mode"])

    def test_solo_video_requires_audio_before_whisper_or_render(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {
                "MC_PROFILE_COMPONENT": "studio",
                "MC_PROFILE_PLATFORM": "instagram",
                "MC_PROFILE_ID": "studio_instagram",
            },
            clear=True,
        ):
            input_root = Path(directory)
            input_dir = input_root / "video"
            input_dir.mkdir()
            video_path = input_dir / "silent.mp4"
            video_path.write_bytes(b"external")
            input_service = StudioInputPreparationService(input_root)
            probe = Mock(
                inspect=Mock(
                    return_value=SimpleNamespace(has_audio=False)
                )
            )
            subtitle_service = Mock()
            renderer = Mock()
            resolver = Mock()

            def prepare(**options):
                return preparar_studio(
                    input_preparation_service=input_service,
                    media_probe=probe,
                    **options,
                )

            with patch("app.core.start.ProjectManager") as projects, self.assertRaisesRegex(
                ValueError,
                "no contiene una pista de audio",
            ):
                ejecutar_studio(
                    subtitle_profile_key=STUDIO_INSTAGRAM_THREE_TWO_KEY,
                    input_mode="video",
                    preparation_service=prepare,
                    external_subtitle_preparation_service=subtitle_service,
                    render_service=renderer,
                    output_path_resolver=resolver,
                )

        probe.inspect.assert_called_once_with(video_path)
        projects.assert_not_called()
        subtitle_service.prepare.assert_not_called()
        renderer.render.assert_not_called()
        resolver.resolve.assert_not_called()

    def test_solo_video_with_audio_keeps_preparation_contract(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {
                "MC_PROFILE_COMPONENT": "studio",
                "MC_PROFILE_PLATFORM": "instagram",
                "MC_PROFILE_ID": "studio_instagram",
            },
            clear=True,
        ):
            input_root = Path(directory)
            input_dir = input_root / "video"
            input_dir.mkdir()
            video_path = input_dir / "source.mp4"
            video_path.write_bytes(b"external")
            probe = Mock(
                inspect=Mock(
                    return_value=SimpleNamespace(has_audio=True)
                )
            )

            prepared = preparar_studio(
                subtitle_profile_key=STUDIO_INSTAGRAM_THREE_TWO_KEY,
                input_mode="video",
                input_preparation_service=StudioInputPreparationService(
                    input_root
                ),
                media_probe=probe,
            )

        self.assertEqual(video_path, prepared.video_path)
        self.assertEqual("video", prepared.input_mode)
        probe.inspect.assert_called_once_with(video_path)

    def test_srt_video_does_not_probe_or_require_audio(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {
                "MC_PROFILE_COMPONENT": "studio",
                "MC_PROFILE_PLATFORM": "instagram",
                "MC_PROFILE_ID": "studio_instagram",
            },
            clear=True,
        ):
            input_root = Path(directory)
            input_dir = input_root / "srt_video"
            input_dir.mkdir()
            (input_dir / "silent.mp4").write_bytes(b"external")
            (input_dir / "source.srt").write_text(
                "1\n00:00:00,000 --> 00:00:01,000\nTexto\n",
                encoding="utf-8",
            )
            probe = Mock()

            prepared = preparar_studio(
                subtitle_profile_key=STUDIO_INSTAGRAM_THREE_TWO_KEY,
                input_mode="srt_video",
                input_preparation_service=StudioInputPreparationService(
                    input_root
                ),
                media_probe=probe,
            )

        self.assertEqual("srt_video", prepared.input_mode)
        probe.inspect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
