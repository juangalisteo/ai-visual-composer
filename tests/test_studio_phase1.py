import json
import os
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import main
from app.controllers.run_controller import RunController
from app.core.start import ejecutar_studio_fase_1, iniciar
from app.modules.studio import (
    StudioInputPreparationService,
    StudioProfileLoader,
)
from app.shared.config_manager import ConfigManager
from app.shared.profile_identity import (
    ProfileComponent,
    ProfileKey,
    ProfilePlatform,
)
from app.shared.profile_resolver import ProfileResolver
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


class StudioPhase1Test(unittest.TestCase):

    def setUp(self):
        self.profile_key = ProfileKey.for_component(
            ProfileComponent.STUDIO,
            ProfilePlatform.INSTAGRAM,
        )
        self.profile = StudioProfileLoader().load(
            ProfileResolver().load(self.profile_key),
            self.profile_key,
        )

    def test_studio_is_an_official_component_with_exact_profiles(self):
        resolver = ProfileResolver()
        self.assertEqual(ProfileComponent.STUDIO.value, "studio")
        self.assertEqual(
            Path(
                "config/profiles/studio/instagram/"
                "perfil_studio_instagram.json"
            ),
            resolver.resolve(self.profile_key),
        )
        youtube_key = ProfileKey.for_component("studio", "youtube")
        self.assertEqual(
            Path(
                "config/profiles/studio/youtube/"
                "perfil_studio_youtube.json"
            ),
            resolver.resolve(youtube_key),
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
            with self.assertRaises(FileNotFoundError):
                ProfileResolver(root).resolve(self.profile_key)

    def test_studio_subtitle_profiles_are_exact_and_independent(self):
        resolver = SubtitleProfileResolver()
        resolved = []
        for platform in ProfilePlatform:
            profile_key = ProfileKey.for_component("studio", platform)
            for style in ("single_line", "word_by_word"):
                key = SubtitleProfileKey.for_profile(profile_key, style)
                profile = resolver.load(key)
                resolved.append(profile.path)
                self.assertEqual(profile_key.component, profile.key.component)
                self.assertEqual(profile_key.platform, profile.key.platform)
        self.assertEqual(4, len(set(resolved)))

    def test_studio_subtitle_discovery_accepts_a_future_style(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "profiles"
            subtitle_dir = root / "studio/instagram/subtitulos"
            subtitle_dir.mkdir(parents=True)
            data = {
                "component": "studio",
                "platform": "instagram",
                "profile_id": "subtitulo_studio_instagram_cinematografico",
                "style": "cinematografico",
                "cue_policy": {},
                "render_style": {},
            }
            path = subtitle_dir / "subtitulo_studio_instagram_cinematografico.json"
            path.write_text(json.dumps(data), encoding="utf-8")

            resolver = SubtitleProfileResolver(root)
            styles = resolver.discover_styles(self.profile_key)
            self.assertEqual(("cinematografico",), styles)
            self.assertEqual(
                path,
                resolver.resolve(
                    SubtitleProfileKey.for_profile(
                        self.profile_key,
                        "cinematografico",
                    )
                ),
            )

    def test_input_accepts_one_dynamic_mp4_and_one_valid_srt_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            input_dir = Path(directory)
            video_path = input_dir / "source-export.MP4"
            subtitle_path = input_dir / "captions-final.SRT"
            video_bytes = b"external video bytes"
            subtitle_bytes = (
                b"1\r\n00:00:00,000 --> 00:00:01,000\r\nHola Studio\r\n"
            )
            video_path.write_bytes(video_bytes)
            subtitle_path.write_bytes(subtitle_bytes)
            (input_dir / "notes.txt").write_text("ignored", encoding="utf-8")

            prepared = StudioInputPreparationService(input_dir).prepare(
                self.profile
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
                input_dir = Path(directory)
                for name in videos:
                    (input_dir / name).write_bytes(b"video")
                for name in subtitles:
                    (input_dir / name).write_text(
                        "1\n00:00:00,000 --> 00:00:01,000\nHola\n",
                        encoding="utf-8",
                    )
                with self.assertRaisesRegex((FileNotFoundError, ValueError), error):
                    StudioInputPreparationService(input_dir).prepare(self.profile)

    def test_input_rejects_empty_or_unusable_srt(self):
        for content in ("", "not a cue"):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as directory:
                input_dir = Path(directory)
                (input_dir / "source.mp4").write_bytes(b"video")
                (input_dir / "captions.srt").write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError):
                    StudioInputPreparationService(input_dir).prepare(self.profile)

    def test_profile_contract_fails_fast_for_missing_critical_field(self):
        raw = ProfileResolver().load(self.profile_key)
        incomplete = deepcopy(raw)
        del incomplete["studio"]["output"]["video"]["crf"]
        with self.assertRaisesRegex(ValueError, "studio.output.video.crf"):
            StudioProfileLoader().load(incomplete, self.profile_key)

    def test_run_controller_transports_studio_without_future_options(self):
        controller = RunController()
        with patch.object(
            controller,
            "select_visual_pipeline",
            return_value="studio",
        ), patch.object(
            controller,
            "select_profile",
            return_value={"profile_key": self.profile_key},
        ), patch.object(
            controller,
            "select_studio_subtitle_config",
            return_value="single_line",
        ), patch.object(
            controller,
            "select_studio_light_leaks",
            return_value=False,
        ), patch.object(
            controller,
            "select_studio_music",
            return_value=None,
        ):
            options = controller.run()

        self.assertEqual("studio", options["pipeline_mode"])
        self.assertEqual("studio", options["profile_component"])
        self.assertEqual("single_line", options["subtitle_config"])
        self.assertFalse(options["studio_light_leaks_enabled"])
        self.assertIsNone(options["studio_music_path"])
        self.assertFalse(options["clear_output"])
        self.assertEqual("off", options["overlays_mode"])
        self.assertIsNone(options["intro_outro_selection"])

    def test_studio_profile_menu_lists_platforms_without_video_profile_label(self):
        with patch("builtins.input", return_value="1"), patch(
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
        self.assertIn("2. YouTube", printed)
        self.assertNotIn("Modo Conciencia", printed)

    def test_main_transports_studio_identity_without_resetting_output(self):
        options = {
            "profile_component": "studio",
            "profile_platform": "instagram",
            "profile_id": "studio_instagram",
            "subtitle_config": "single_line",
            "voice_config": "",
            "music_category": None,
            "overlays_mode": "off",
            "project_name": "",
            "visual_pipeline": "studio",
            "script_source": "external",
            "design_target": "",
            "pipeline_mode": "studio",
            "studio_light_leaks_enabled": False,
            "studio_music_path": None,
            "clear_output": False,
        }
        with patch.dict(os.environ, {}, clear=True), patch(
            "main.RunController"
        ) as controller, patch("main.iniciar") as start, patch(
            "main.OutputManager"
        ) as output_manager:
            controller.return_value.run.return_value = options
            self.assertEqual(0, main.main())
            self.assertEqual("studio", os.environ["MC_PROFILE_COMPONENT"])
            self.assertEqual("studio", os.environ["MC_PIPELINE_MODE"])

        start.assert_called_once_with(
            subtitle_style="single_line",
            studio_light_leaks_enabled=False,
            studio_music_path=None,
        )
        output_manager.assert_not_called()

    def test_start_routes_studio_to_phase_two_without_project_manager(self):
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
            "app.core.start.ejecutar_studio_fase_2"
        ) as render:
            iniciar(subtitle_style="single_line")

        render.assert_called_once_with(
            subtitle_style="single_line",
            light_leaks_enabled=False,
            music_path=None,
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
            input_dir = Path(directory)
            video_path = input_dir / "clip.mp4"
            subtitle_path = input_dir / "source.srt"
            video_path.write_bytes(b"external")
            subtitle_path.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\nTexto intacto\n",
                encoding="utf-8",
            )
            result = ejecutar_studio_fase_1(
                subtitle_style="single_line",
                input_preparation_service=StudioInputPreparationService(input_dir),
            )

        self.assertEqual(video_path, result.video_path)
        self.assertEqual(subtitle_path, result.subtitle_path)
        self.assertEqual("single_line", result.subtitle_profile.key.style.value)


if __name__ == "__main__":
    unittest.main()
