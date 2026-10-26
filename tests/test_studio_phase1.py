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
from app.core.start import ejecutar_studio, preparar_studio
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
from tests.test_menu_helpers import MenuAnswers


STUDIO_VERTICAL_THREE_TWO_PROFILE_ID = (
    "subtitulo_studio_vertical_dos_tres"
)
STUDIO_VERTICAL_THREE_TWO_KEY = SubtitleProfileKey(
    "studio",
    "vertical",
    STUDIO_VERTICAL_THREE_TWO_PROFILE_ID,
    "estandar",
)


STUDIO_PROFILE_IDS = {
    "vertical": "studio_vertical",
    "horizontal": "studio_horizontal",
}


class StudioPhase1Test(unittest.TestCase):

    def setUp(self):
        self.profile_key = OperationalProfileKey(
            ProfileComponent.STUDIO,
            "vertical",
            "studio_vertical",
        )
        self.operational_key = OperationalProfileKey(
            ProfileComponent.STUDIO,
            "vertical",
            "studio_vertical",
        )
        self.profile = StudioProfileLoader().load(
            ProfileResolver().load_operational(self.operational_key),
            self.operational_key,
        )

    def _config_manager(self):
        return ConfigManager(operational_profile_key=self.operational_key)

    def test_studio_is_an_official_component_with_exact_profiles(self):
        resolver = ProfileResolver()
        self.assertEqual(ProfileComponent.STUDIO.value, "studio")
        self.assertEqual(
            Path(
                "config/profiles/studio/vertical/"
                "perfil_studio_vertical.json"
            ),
            resolver.resolve_operational(self.operational_key),
        )
        horizontal_operational_key = OperationalProfileKey(
            "studio", "horizontal", "studio_horizontal"
        )
        self.assertEqual(
            Path(
                "config/profiles/studio/horizontal/"
                "perfil_studio_horizontal.json"
            ),
            resolver.resolve_operational(horizontal_operational_key),
        )

    def test_studio_does_not_fall_back_to_video_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video_path = root / "video/vertical"
            video_path.mkdir(parents=True)
            (video_path / "perfil_video_vertical.json").write_text(
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
        for profile_format in ("horizontal", "vertical"):
            profile_key = OperationalProfileKey(
                "studio", profile_format, STUDIO_PROFILE_IDS[profile_format]
            )
            for descriptor in resolver.discover_profiles_for_family(
                "studio", profile_format, "estandar",
            ):
                profile = resolver.load(descriptor.key)
                resolved.append(profile.path)
                self.assertEqual(profile_key.component, profile.key.component)
                self.assertEqual(profile_key.format, profile.key.format)
        self.assertEqual(len(resolved), len(set(resolved)))

    def test_studio_subtitle_discovery_rejects_an_unregistered_future_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "profiles"
            subtitle_dir = root / "studio/vertical/estandar/subtitulos"
            subtitle_dir.mkdir(parents=True)
            data = {
                "component": "studio",
                "format": "vertical",
                "family": "estandar",
                "profile_id": "subtitulo_studio_vertical_cinematografico",
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
            path = subtitle_dir / "subtitulo_studio_vertical_cinematografico.json"
            path.write_text(json.dumps(data), encoding="utf-8")

            resolver = SubtitleProfileResolver(root)
            with self.assertRaises(OperationalError) as captured:
                resolver.discover_profiles_for_family(
                    "studio", "vertical", "estandar",
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
            answers = MenuAnswers("second.mp4")
            with patch("builtins.input", side_effect=answers.input), patch.object(
                controller, "_print", side_effect=answers.write
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
            answers = MenuAnswers("second.mp4", "captions.srt")
            with patch("builtins.input", side_effect=answers.input), patch.object(
                controller, "_print", side_effect=answers.write
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

    def test_video_extensions_accept_what_every_studio_mode_supports(self):
        for profile_format in ("horizontal", "vertical"):
            with self.subTest(profile_format=profile_format):
                key = OperationalProfileKey(
                    "studio", profile_format, f"studio_{profile_format}"
                )
                profile = StudioProfileLoader().load(
                    ProfileResolver().load_operational(key),
                    key,
                )
                self.assertEqual((".mp4",), profile.video_extensions)

        raw = ProfileResolver().load_operational(self.operational_key)
        variant = deepcopy(raw)
        variant["studio"]["input"]["video_extensions"] = [".mp4", ".MP3"]

        profile = StudioProfileLoader().load(variant, self.profile_key)

        self.assertEqual((".mp4", ".mp3"), profile.video_extensions)

    def test_video_extensions_reject_what_whisper_does_not_support(self):
        raw = ProfileResolver().load_operational(self.operational_key)
        invalid = deepcopy(raw)
        invalid["studio"]["input"]["video_extensions"] = [".mp4", ".mov"]

        with self.assertRaises(OperationalError) as caught:
            StudioProfileLoader().load(invalid, self.profile_key)

        context = caught.exception.context
        self.assertEqual("CONFIG", context.family)
        self.assertIn("incluye .mov, pero", context.user_message)
        self.assertIn("SOLO VIDEO", context.user_message)
        self.assertIn("Whisper", context.user_message)
        self.assertEqual(
            "studio/vertical/studio_vertical",
            context.resource,
        )
        self.assertIsInstance(caught.exception.__cause__, ValueError)

    def test_transition_duration_is_isolated_by_studio_format(self):
        horizontal_operational_key = OperationalProfileKey(
            "studio", "horizontal", "studio_horizontal"
        )
        horizontal_profile = StudioProfileLoader().load(
            ProfileResolver().load_operational(horizontal_operational_key),
            horizontal_operational_key,
        )

        self.assertEqual(0.25, self.profile.transition_duration)
        self.assertEqual(0.50, horizontal_profile.transition_duration)

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
                            "vertical",
                            "subtitulo_studio_vertical_linea_unica",
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
            "subtitulo_studio_vertical_linea_unica",
            options["subtitle_profile_key"].profile_id,
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

    def test_studio_profile_menu_lists_formats_without_video_profile_label(self):
        answers = MenuAnswers("Vertical 9:16", "ESTILO ESTÁNDAR", "Doble línea")
        with patch("builtins.input", side_effect=answers.input), patch(
            "builtins.print", side_effect=answers.print
        ) as print_mock:
            selected = RunController().select_profile("studio")

        printed = "\n".join(
            str(call.args[0])
            for call in print_mock.call_args_list
            if call.args
        )
        self.assertEqual(ProfileComponent.STUDIO, selected["profile_key"].component)
        self.assertIn("1. Vertical 9:16", printed)
        self.assertIn("2. Horizontal 16:9", printed)
        self.assertIn("Línea única", printed)

    def test_main_transports_studio_identity_without_resetting_output(self):
        options = {
            "profile_component": "studio",
            "profile_format": "vertical",
            "profile_id": "studio_vertical",
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
            "profile_format": "vertical",
            "profile_id": "studio_vertical",
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
        output_manager.return_value.reset.assert_called_once_with()

    def test_phase_one_preparation_uses_external_input_without_rendering(self):
        with tempfile.TemporaryDirectory() as directory:
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
                subtitle_profile_key=STUDIO_VERTICAL_THREE_TWO_KEY,
                input_mode="srt_video",
                config_manager=self._config_manager(),
                input_preparation_service=StudioInputPreparationService(input_root),
            )

        self.assertEqual(video_path, result.video_path)
        self.assertEqual(subtitle_path, result.subtitle_path)
        self.assertEqual("three_two_words", result.subtitle_profile.cue_policy["mode"])

    def test_solo_video_requires_audio_before_whisper_or_render(self):
        with tempfile.TemporaryDirectory() as directory:
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
                    config_manager=self._config_manager(),
                    input_preparation_service=input_service,
                    media_probe=probe,
                    **options,
                )

            with patch("app.core.start.ProjectManager") as projects, self.assertRaisesRegex(
                ValueError,
                "no contiene una pista de audio",
            ):
                ejecutar_studio(
                    subtitle_profile_key=STUDIO_VERTICAL_THREE_TWO_KEY,
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
        with tempfile.TemporaryDirectory() as directory:
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
                subtitle_profile_key=STUDIO_VERTICAL_THREE_TWO_KEY,
                input_mode="video",
                config_manager=self._config_manager(),
                input_preparation_service=StudioInputPreparationService(
                    input_root
                ),
                media_probe=probe,
            )

        self.assertEqual(video_path, prepared.video_path)
        self.assertEqual("video", prepared.input_mode)
        probe.inspect.assert_called_once_with(video_path)

    def test_srt_video_does_not_probe_or_require_audio(self):
        with tempfile.TemporaryDirectory() as directory:
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
                subtitle_profile_key=STUDIO_VERTICAL_THREE_TWO_KEY,
                input_mode="srt_video",
                config_manager=self._config_manager(),
                input_preparation_service=StudioInputPreparationService(
                    input_root
                ),
                media_probe=probe,
            )

        self.assertEqual("srt_video", prepared.input_mode)
        probe.inspect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
