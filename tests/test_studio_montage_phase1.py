import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import main
from app.controllers.run_controller import RunController
from app.core.start import iniciar
from app.modules.studio.execution_coordinator import (
    StudioExecutionCoordinator,
)
from app.modules.studio import (
    StudioInputMode,
    StudioInputPreparationService,
    StudioMontageInputError,
    StudioMontagePlanningService,
)
from app.shared.profile_identity import (
    OperationalProfileKey,
    ProfileComponent,
)


class StudioMontagePhase1Test(unittest.TestCase):

    def setUp(self):
        self.profile = SimpleNamespace(video_extensions=(".mp4",))
        self.profile_key = OperationalProfileKey(
            ProfileComponent.STUDIO,
            "instagram",
            "studio_instagram",
        )

    def _service(self, root):
        return StudioMontagePlanningService(
            StudioInputPreparationService(root)
        )

    def _write_clips(self, root, names):
        directory = root / "montaje_videos"
        directory.mkdir()
        for name in names:
            (directory / name).write_bytes(b"video")
        return directory

    def test_fourth_studio_input_mode_is_montage_videos(self):
        controller = RunController()
        with patch("builtins.input", return_value="4"), patch(
            "app.controllers.interaction.terminal.ProgressLogger.info"
        ) as logger:
            selected = controller.select_studio_input_mode()

        self.assertEqual(StudioInputMode.MONTAJE_VIDEOS.value, selected)
        printed = "\n".join(call.args[0] for call in logger.call_args_list)
        self.assertIn("4. MONTAJE VÍDEOS", printed)

    def test_discovery_is_deterministic_and_keeps_original_names(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_clips(
                root,
                ("Zeta.mp4", "alpha.mp4", "ignore.txt", "Bravo.MP4"),
            )

            candidates = self._service(root).discover(self.profile)

        self.assertEqual(
            ("alpha.mp4", "Bravo.MP4", "Zeta.mp4"),
            tuple(clip.original_name for clip in candidates.clips),
        )
        self.assertEqual(
            (1, 2, 3),
            tuple(clip.temporary_id for clip in candidates.clips),
        )

    def test_discovery_fails_cleanly_for_missing_or_empty_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            service = self._service(Path(directory))
            with self.assertRaisesRegex(
                StudioMontageInputError,
                "No existe la carpeta de entrada STUDIO",
            ):
                service.discover(self.profile)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "montaje_videos").mkdir()
            with self.assertRaisesRegex(
                StudioMontageInputError,
                "No se encontro ningun archivo MP4",
            ):
                self._service(root).discover(self.profile)

    def test_parser_preserves_partial_selection_and_exact_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_clips(root, ("A.mp4", "B.mp4", "C.mp4", "D.mp4"))
            service = self._service(root)
            candidates = service.discover(self.profile)
            clips = service.parse_order(" 1  3 2 ", candidates)
            plan = service.create_plan(
                self.profile_key,
                True,
                clips,
            )

        self.assertEqual(
            ("A.mp4", "C.mp4", "B.mp4"),
            tuple(clip.original_name for clip in plan.clips),
        )
        self.assertEqual((1, 3, 2), tuple(clip.temporary_id for clip in plan.clips))
        self.assertEqual("instagram", plan.platform)
        self.assertEqual("studio_instagram", plan.profile_id)
        self.assertTrue(plan.transitions_enabled)

    def test_plan_preserves_youtube_studio_identity(self):
        youtube_key = OperationalProfileKey(
            ProfileComponent.STUDIO,
            "youtube",
            "studio_youtube",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_clips(root, ("A.mp4", "B.mp4"))
            service = self._service(root)
            plan = service.create_plan(
                youtube_key,
                False,
                service.parse_order("1 2", service.discover(self.profile)),
            )

        self.assertEqual("youtube", plan.platform)
        self.assertEqual("studio_youtube", plan.profile_id)

    def test_parser_requires_multiple_clips_and_accepts_large_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            names = tuple(f"clip_{index:03}.mp4" for index in range(1, 231))
            self._write_clips(root, names)
            service = self._service(root)
            candidates = service.discover(self.profile)
            with self.assertRaisesRegex(StudioMontageInputError, "al menos dos"):
                service.parse_order("230", candidates)
            all_clips = service.parse_order(
                " ".join(str(index) for index in range(230, 0, -1)),
                candidates,
            )

        self.assertEqual(230, len(all_clips))
        self.assertEqual(230, all_clips[0].temporary_id)
        self.assertEqual(1, all_clips[-1].temporary_id)

    def test_parser_rejects_invalid_values_and_duplicates(self):
        invalid_cases = (
            "",
            "   ",
            "0",
            "-1",
            "1.0",
            "uno",
            "1,2",
            "1/2",
            "4",
            "1 2 1",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_clips(root, ("A.mp4", "B.mp4", "C.mp4"))
            service = self._service(root)
            candidates = service.discover(self.profile)
            for value in invalid_cases:
                with self.subTest(value=value), self.assertRaises(
                    StudioMontageInputError
                ):
                    service.parse_order(value, candidates)

    def test_parser_rejects_clip_that_disappears_after_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clips_directory = self._write_clips(root, ("A.mp4",))
            service = self._service(root)
            candidates = service.discover(self.profile)
            (clips_directory / "A.mp4").unlink()
            with self.assertRaisesRegex(
                StudioMontageInputError,
                "ya no existe",
            ):
                service.parse_order("1", candidates)

    def test_cli_shows_discovery_order_and_transitions_without_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_clips(root, ("A.mp4", "B.mp4", "C.mp4"))
            controller = RunController(
                studio_input_preparation_service=StudioInputPreparationService(root)
            )
            with patch(
                "builtins.input",
                side_effect=("1 3 2", "1"),
            ), patch(
                "app.controllers.interaction.terminal.ProgressLogger.info"
            ) as logger:
                plan = controller.select_studio_montage_plan(
                    self.profile_key,
                    self.profile,
                )

        rendered = "\n".join(call.args[0] for call in logger.call_args_list)
        self.assertLess(
            rendered.index("VÍDEOS ENCONTRADOS"),
            rendered.index("Introduce el orden de montaje:"),
        )
        self.assertLess(
            rendered.index("Introduce el orden de montaje:"),
            rendered.index("TRANSICIONES"),
        )
        self.assertIn("[1] A.mp4", rendered)
        self.assertIn("[3] C.mp4", rendered)
        self.assertTrue(plan.transitions_enabled)
        self.assertEqual(("A.mp4", "C.mp4", "B.mp4"), tuple(
            clip.original_name for clip in plan.clips
        ))

    def test_cli_records_transitions_no_without_a_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_clips(root, ("A.mp4", "B.mp4"))
            controller = RunController(
                studio_input_preparation_service=StudioInputPreparationService(root)
            )
            with patch("builtins.input", side_effect=("1 2", "2")):
                plan = controller.select_studio_montage_plan(
                    self.profile_key,
                    self.profile,
                )

        self.assertFalse(plan.transitions_enabled)

    def test_run_controller_transports_montage_without_legacy_studio_options(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_clips(root, ("A.mp4", "B.mp4"))
            clip_service = self._service(root)
            candidates = clip_service.discover(self.profile)
            plan = clip_service.create_plan(
                self.profile_key,
                False,
                clip_service.parse_order("1 2", candidates),
            )
            controller = RunController()
            with patch.object(
                controller,
                "_select_studio_operational_profile",
                return_value=(self.profile_key, self.profile),
            ), patch.object(
                controller,
                "select_studio_input_mode",
                return_value=StudioInputMode.MONTAJE_VIDEOS.value,
            ), patch.object(
                controller.studio_profile_loader,
                "load",
                return_value=self.profile,
            ), patch.object(
                controller,
                "select_studio_montage_plan",
                return_value=plan,
            ), patch.object(
                controller,
                "select_studio_input_files",
                side_effect=AssertionError("legacy input must not run"),
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
                return_value="montaje",
            ), patch.object(
                controller,
                "ask_clear_output",
                return_value=False,
            ):
                options = controller._run_studio()

        self.assertIs(plan, options["studio_montage_plan"])
        self.assertEqual("montaje_videos", options["studio_input_mode"])
        self.assertIsNone(options["subtitle_config"])
        self.assertIsNone(options["studio_music_path"])

    def test_start_transports_montage_plan_to_phase_two_orchestrator(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_clips(root, ("A.mp4", "B.mp4"))
            service = self._service(root)
            plan = service.create_plan(
                self.profile_key,
                False,
                service.parse_order("1 2", service.discover(self.profile)),
            )
            with patch.dict(
                os.environ,
                {"MC_PIPELINE_MODE": "studio"},
                clear=True,
            ), patch(
                "app.core.start.ejecutar_studio_montaje",
                return_value="montage-result",
            ) as montage:
                result = iniciar(studio_montage_plan=plan)

        self.assertEqual("montage-result", result)
        montage.assert_called_once_with(plan)
        self.assertIs(plan, StudioExecutionCoordinator.prepare_montage(plan))

    def test_main_transports_montage_with_reset_and_montage_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_clips(root, ("A.mp4", "B.mp4"))
            service = self._service(root)
            plan = service.create_plan(
                self.profile_key,
                False,
                service.parse_order("1 2", service.discover(self.profile)),
            )
            options = {
                "profile_component": "studio",
                "profile_platform": "instagram",
                "profile_id": "studio_instagram",
                "subtitle_config": "",
                "voice_config": "",
                "music_category": None,
                "project_name": "montaje",
                "visual_pipeline": "studio",
                "script_source": "external",
                "design_target": "",
                "pipeline_mode": "studio",
                "studio_input_mode": "montaje_videos",
                "studio_montage_plan": plan,
                "studio_music_path": None,
                "intro_outro_selection": None,
                "clear_output": True,
            }
            with patch.dict(os.environ, {}, clear=True), patch(
                "main.RunController"
            ) as controller, patch("main.iniciar", return_value=object()) as start, patch(
                "main.OutputManager.reset"
            ) as reset, patch("main._print_studio_summary") as summary, patch(
                "main._print_studio_montage_summary"
            ) as montage_summary:
                controller.return_value.run.return_value = options
                result = main.main()

        self.assertEqual(0, result)
        self.assertIs(plan, start.call_args.kwargs["request"].route.plan)
        reset.assert_called_once_with()
        summary.assert_not_called()
        montage_summary.assert_called_once()

    def test_main_shows_expected_montage_input_error_without_traceback(self):
        with patch("main.RunController") as controller, patch(
            "builtins.print"
        ) as printer:
            controller.return_value.run.side_effect = StudioMontageInputError(
                "No se encontro ningun archivo MP4."
            )
            result = main.main()

        self.assertEqual(1, result)
        printer.assert_called_once_with(
            "ERROR: No se encontro ningun archivo MP4."
        )


if __name__ == "__main__":
    unittest.main()
