import contextlib
import unittest
import os
import tempfile
import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import main
from app.controllers.run_controller import RunController
from app.core import start
from app.core.execution_request import (
    ApplicationExecutionRequest,
    DesignExecutionRequest,
    StudioExecutionRequest,
)
from app.modules.script import ScriptPreparationService
from app.modules.standard import execution_coordinator as standard
from app.modules.studio import (
    StudioInputPreparationService,
    StudioIntroOutroInputService,
    StudioMontageError,
    StudioSubtitleExportInputService,
    StudioSubtitleExportMode,
    StudioVideoAudioSrtError,
    StudioVideoAudioSrtInputService,
)
from app.managers.output_manager import OutputManager
from app.shared.error_context import ErrorContext, ErrorSeverity, ExitKind
from app.shared.operational_error import OperationalError
from app.shared.profile_identity import OperationalProfileKey


class MainErrorHandlingTest(unittest.TestCase):

    def design_request(self, project_name="error test", clear_output=False):
        return ApplicationExecutionRequest(
            project_name=project_name,
            clear_output=clear_output,
            operational_profile_key=OperationalProfileKey(
                "video",
                "vertical",
                "video_vertical",
            ),
            subtitle_profile_key=None,
            route=DesignExecutionRequest(mode="design_video"),
        )

    def studio_request(self, input_mode, project_name="error test"):
        return ApplicationExecutionRequest(
            project_name=project_name,
            clear_output=False,
            operational_profile_key=OperationalProfileKey(
                "studio",
                "vertical",
                "studio_vertical",
            ),
            subtitle_profile_key=None,
            route=StudioExecutionRequest(input_mode=input_mode),
        )

    def test_external_operational_error_is_user_visible_without_traceback(self):
        request = self.design_request()
        error = OperationalError(
            ErrorContext(
                family="EXTERNAL_SERVICE",
                severity=ErrorSeverity.FATAL_OPERATIONAL,
                user_message="La interpretación visual no pudo completarse.",
                exit_kind=ExitKind.OPERATIONAL_ERROR,
                operation="Interpretar diseño visual",
                recommended_action="Comprueba el proveedor e inténtalo de nuevo.",
                technical_metadata={"service": "visual_design"},
            )
        )

        with patch.dict(
            os.environ,
            {},
            clear=True
        ), patch(
            "main.RunController"
        ) as controller_mock, patch(
            "main.run_application",
            side_effect=error
        ), patch(
            "builtins.print"
        ) as print_mock:
            controller_mock.return_value.run.return_value = request

            result = main.main()

        self.assertEqual(
            1,
            result
        )
        print_mock.assert_called_once_with(
            "ERROR\n"
            "La interpretación visual no pudo completarse.\n"
            "Operación: Interpretar diseño visual\n"
            "Acción recomendada: Comprueba el proveedor e inténtalo de nuevo."
        )

    def test_operational_error_uses_the_presenter_with_controlled_output(self):
        context = ErrorContext(
            family="FILESYSTEM",
            severity=ErrorSeverity.FATAL_OPERATIONAL,
            user_message="No se pudo preparar el archivo solicitado.",
            exit_kind=ExitKind.OPERATIONAL_ERROR,
            operation="Preparar entrada",
            resource="input/fuente.txt",
            recommended_action="Revise la ruta e inténtelo de nuevo.",
            diagnostic_reference="output/diagnostics/run-001.json",
            technical_metadata={"stderr": "private stderr"},
        )

        with patch.dict(os.environ, {}, clear=True), patch(
            "main.RunController"
        ) as controller_mock, patch(
            "main.run_application",
            side_effect=OperationalError(context),
        ), patch("builtins.print") as print_mock:
            controller_mock.return_value.run.return_value = self.design_request()

            result = main.main()

        self.assertEqual(1, result)
        print_mock.assert_called_once_with(
            "ERROR\n"
            "No se pudo preparar el archivo solicitado.\n"
            "Operación: Preparar entrada\n"
            "Recurso: input/fuente.txt\n"
            "Acción recomendada: Revise la ruta e inténtelo de nuevo.\n"
            "Diagnóstico técnico: output/diagnostics/run-001.json"
        )
        self.assertNotIn("private stderr", print_mock.call_args.args[0])
        self.assertNotIn("Traceback", print_mock.call_args.args[0])

    def test_manual_review_validation_is_visible_without_internal_traceback(self):
        request = self.design_request()
        error = OperationalError(
            ErrorContext(
                family="VALIDATION",
                severity=ErrorSeverity.FATAL_OPERATIONAL,
                user_message=(
                    "La imagen candidata requiere revisión manual "
                    "antes de continuar."
                ),
                exit_kind=ExitKind.OPERATIONAL_ERROR,
                operation="Validar calidad visual de scene_001",
                resource="output/images/scene_001.png",
                recommended_action=(
                    "Revise la imagen candidata y la evidencia de "
                    "validación; no se ha aprobado como asset final."
                ),
                diagnostic_reference=(
                    "output/images/evidence/scene_001/"
                    "visual_quality_result.json"
                ),
            )
        )

        with patch.dict(os.environ, {}, clear=True), patch(
            "main.RunController"
        ) as controller_mock, patch(
            "main.run_application", side_effect=error
        ), patch("builtins.print") as print_mock:
            controller_mock.return_value.run.return_value = request

            result = main.main()

        self.assertEqual(1, result)
        output = print_mock.call_args.args[0]
        self.assertTrue(output.startswith("ERROR\n"))
        self.assertIn("revisión manual", output)
        self.assertIn("no se ha aprobado como asset final", output)
        self.assertIn("visual_quality_result.json", output)
        self.assertNotIn("ERROR INTERNO", output)
        self.assertNotIn("Traceback", output)

    def test_menu_cancellation_is_clean_and_uses_exit_code_zero(self):
        error = OperationalError(
            ErrorContext(
                family="CANCELLATION",
                severity=ErrorSeverity.RECOVERABLE,
                user_message="La operación fue cancelada por el usuario.",
                exit_kind=ExitKind.CANCELLATION,
                operation="Selección de opciones",
            )
        )
        with patch("main.RunController") as controller_mock, patch(
            "builtins.print"
        ) as print_mock:
            controller_mock.return_value.run.side_effect = error

            result = main.main()

        self.assertEqual(0, result)
        output = print_mock.call_args.args[0]
        self.assertTrue(output.startswith("CANCELADO\n"))
        self.assertNotIn("Traceback", output)
        self.assertNotIn("ERROR INTERNO", output)

    def test_keyboard_interrupt_is_clean_and_preserves_existing_artifacts(self):
        with patch.dict(
            os.environ,
            {},
            clear=True,
        ), tempfile.TemporaryDirectory() as directory:
            artifact = os.path.join(directory, "partial.png")
            with open(artifact, "wb") as handle:
                handle.write(b"partial")

            with patch("main.RunController") as controller_mock, patch(
                "main.run_application", side_effect=KeyboardInterrupt
            ) as run_application_mock, patch("builtins.print") as print_mock:
                controller_mock.return_value.run.return_value = self.design_request()

                result = main.main()

            self.assertEqual(130, result)
            run_application_mock.assert_called_once()
            self.assertEqual(
                "design_video",
                run_application_mock.call_args.kwargs["request"].route.mode,
            )
            self.assertTrue(os.path.exists(artifact))
            output = print_mock.call_args.args[0]
            self.assertTrue(output.startswith("CANCELADO\n"))
            self.assertNotIn("Traceback", output)
            self.assertNotIn("ERROR INTERNO", output)

    def test_eof_is_clean_input_cancellation_without_runtime(self):
        with patch("main.RunController") as controller_mock, patch(
            "main.run_application"
        ) as run_application_mock, patch("builtins.print") as print_mock:
            controller_mock.return_value.run.side_effect = EOFError()

            result = main.main()

        self.assertEqual(0, result)
        run_application_mock.assert_not_called()
        output = print_mock.call_args.args[0]
        self.assertTrue(output.startswith("CANCELADO\n"))
        self.assertIn("entrada de terminal", output)
        self.assertNotIn("Traceback", output)
        self.assertNotIn("ERROR INTERNO", output)

    def test_studio_preserves_primary_operational_context(self):
        for family, resource in (
            ("FFMPEG", "output/studio/ffmpeg_diagnostics.json"),
            ("SUBTITLES", "input/studio/source.srt"),
            ("PROFILE", "studio/vertical/estandar"),
            ("FILESYSTEM", "input/studio/source.mp4"),
        ):
            with self.subTest(family=family):
                error = OperationalError(
                    ErrorContext(
                        family=family,
                        severity=ErrorSeverity.FATAL_OPERATIONAL,
                        user_message="Fallo contextualizado de STUDIO.",
                        exit_kind=ExitKind.OPERATIONAL_ERROR,
                        operation="STUDIO/montaje_videos",
                        resource=resource,
                        diagnostic_reference=(
                            "output/studio/ffmpeg_diagnostics.json"
                            if family == "FFMPEG" else None
                        ),
                    )
                )
                with patch.dict(os.environ, {}, clear=True), patch(
                    "main.RunController"
                ) as controller_mock, patch(
                    "main.run_application", side_effect=error
                ), patch("builtins.print") as print_mock:
                    controller_mock.return_value.run.return_value = (
                        self.studio_request("srt_video")
                    )
                    result = main.main()

                self.assertEqual(1, result)
                output = print_mock.call_args.args[0]
                self.assertIn("Fallo contextualizado de STUDIO.", output)
                self.assertIn("STUDIO/montaje_videos", output)
                self.assertIn(resource, output)
                self.assertNotIn("Traceback", output)

    def test_unexpected_error_is_presented_as_internal_with_evidence_kept(self):
        unexpected = RuntimeError("private failure")

        with patch.dict(os.environ, {}, clear=True), patch(
            "main.RunController"
        ) as controller_mock, patch(
            "main.run_application",
            side_effect=unexpected,
        ), patch("main.ErrorPresenter") as presenter_mock, patch(
            "main.write_internal_error_log",
            return_value=None,
        ), patch(
            "builtins.print"
        ) as print_mock:
            controller_mock.return_value.run.return_value = self.design_request()
            presenter_mock.return_value.present_context.return_value.text = (
                "ERROR INTERNO\nSe produjo un error interno inesperado."
            )

            result = main.main()

        self.assertEqual(1, result)
        context = presenter_mock.return_value.present_context.call_args.args[0]
        self.assertEqual("INTERNAL", context.family)
        self.assertIs(ErrorSeverity.FATAL_INTERNAL, context.severity)
        self.assertIs(ExitKind.INTERNAL_ERROR, context.exit_kind)
        self.assertEqual("RuntimeError", context.technical_metadata["exception_type"])
        self.assertIn("private failure", context.technical_metadata["traceback"])
        print_mock.assert_called_once_with(
            "ERROR INTERNO\nSe produjo un error interno inesperado."
        )

    def test_non_studio_value_error_reaches_internal_boundary(self):
        with patch.dict(os.environ, {}, clear=True), patch(
            "main.RunController"
        ) as controller_mock, patch(
            "main.run_application",
            side_effect=ValueError("internal validation detail"),
        ), patch(
            "main.write_internal_error_log",
            return_value=None,
        ), patch("builtins.print") as print_mock:
            controller_mock.return_value.run.return_value = self.design_request()

            result = main.main()

        self.assertEqual(1, result)
        self.assertEqual(
            "ERROR INTERNO\n"
            "Se produjo un error interno inesperado.\n"
            "Operación: Ejecución principal",
            print_mock.call_args.args[0],
        )
        self.assertNotIn("internal validation detail", print_mock.call_args.args[0])

    def run_main_failing_with(self, error):
        """Run main() until run_application raises; return (code, terminal)."""
        with patch("main.FormatCatalog"), patch("main.FontManager"), patch(
            "main.RunController"
        ) as controller_mock, patch(
            "main.run_application",
            side_effect=error,
        ), patch("builtins.print") as print_mock:
            controller_mock.return_value.run.return_value = self.design_request()
            result = main.main()
        return result, print_mock.call_args.args[0]

    def test_internal_error_saves_its_detail_and_shows_the_relative_path(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.chdir(
            directory
        ):
            result, output = self.run_main_failing_with(
                RuntimeError("private failure ñ")
            )
            log_files = list(Path("logs").iterdir())
            self.assertEqual(1, len(log_files))
            log_name = log_files[0].name
            content = log_files[0].read_text(encoding="utf-8")

        self.assertEqual(1, result)
        self.assertRegex(
            log_name,
            r"^error_interno_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_\d{6}\.txt$",
        )
        self.assertEqual(
            "ERROR INTERNO\n"
            "Se produjo un error interno inesperado.\n"
            "Operación: Ejecución principal\n"
            f"Diagnóstico técnico: logs/{log_name}",
            output,
        )
        self.assertRegex(
            content,
            r"^Fecha: \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\n"
            r"Operación: Ejecución principal\n"
            r"Tipo: RuntimeError\n"
            r"Mensaje: private failure ñ\n\n"
            r"Traceback \(most recent call last\):\n",
        )
        self.assertIn("_run_main", content)
        self.assertTrue(content.endswith("RuntimeError: private failure ñ\n"))

    def test_each_internal_error_gets_its_own_log_file(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.chdir(
            directory
        ):
            self.run_main_failing_with(RuntimeError("first failure"))
            self.run_main_failing_with(RuntimeError("second failure"))
            contents = sorted(
                path.read_text(encoding="utf-8")
                for path in Path("logs").iterdir()
            )

        self.assertEqual(2, len(contents))
        self.assertIn("first failure", contents[0])
        self.assertIn("second failure", contents[1])

    def test_internal_error_log_escapes_text_utf8_cannot_encode(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.chdir(
            directory
        ):
            _, output = self.run_main_failing_with(
                RuntimeError("bad name \udc80")
            )
            (log_file,) = Path("logs").iterdir()
            content = log_file.read_text(encoding="utf-8")

        self.assertIn(f"logs/{log_file.name}", output)
        self.assertIn("Mensaje: bad name \\udc80\n", content)

    def test_internal_error_stays_the_same_when_its_log_cannot_be_written(self):
        for name, open_failure in (
            ("logs is a file", None),
            ("no permission", PermissionError("denied")),
            ("unexpected failure", ValueError("broken")),
        ):
            with self.subTest(name), tempfile.TemporaryDirectory(
            ) as directory, contextlib.chdir(directory), patch(
                "main.write_internal_error_log",
                wraps=main.write_internal_error_log,
            ) as write_log:
                if open_failure is None:
                    Path("logs").write_text("not a folder", encoding="utf-8")
                    failing_open = contextlib.nullcontext()
                else:
                    failing_open = patch.object(
                        Path,
                        "open",
                        side_effect=open_failure,
                    )
                with failing_open:
                    result, output = self.run_main_failing_with(
                        RuntimeError("private failure")
                    )

                self.assertEqual(1, result)
                self.assertEqual(
                    "ERROR INTERNO\n"
                    "Se produjo un error interno inesperado.\n"
                    "Operación: Ejecución principal",
                    output,
                )
                write_log.assert_called_once()

    def test_input_errors_and_cancellations_do_not_write_a_log(self):
        for error in (
            OperationalError(
                ErrorContext(
                    family="INPUT",
                    severity=ErrorSeverity.FATAL_OPERATIONAL,
                    user_message="Falta el guion.",
                    exit_kind=ExitKind.OPERATIONAL_ERROR,
                )
            ),
            KeyboardInterrupt(),
            EOFError(),
        ):
            with self.subTest(type(error).__name__), tempfile.TemporaryDirectory(
            ) as directory, contextlib.chdir(directory):
                self.run_main_failing_with(error)

                self.assertFalse(Path("logs").exists())

    def test_legacy_studio_runtime_errors_use_shared_presentation(self):
        for error in (
            StudioMontageError("No se pudo montar los clips."),
            StudioVideoAudioSrtError("No se pudo renderizar el vídeo."),
        ):
            with self.subTest(error_type=type(error).__name__), patch.dict(
                os.environ,
                {},
                clear=True,
            ), patch("main.RunController") as controller_mock, patch(
                "main.run_application",
                side_effect=error,
            ), patch("builtins.print") as print_mock:
                controller_mock.return_value.run.return_value = (
                    self.studio_request("srt_video")
                )

                result = main.main()

            self.assertEqual(1, result)
            output = print_mock.call_args.args[0]
            self.assertTrue(output.startswith("ERROR\n"))
            self.assertIn(str(error), output)
            self.assertIn("Operaci", output)
            self.assertNotIn("Traceback", output)

    def test_run_controller_and_start_remain_outside_presentation(self):
        self.assertNotIn("ErrorPresenter", inspect.getsource(RunController))
        self.assertNotIn("ErrorPresenter", inspect.getsource(start))
        self.assertNotIn("ErrorPresenter", inspect.getsource(standard))
        boundary_source = (
            inspect.getsource(main.main)
            + inspect.getsource(main._present_unexpected_error)
        ).lower()
        for forbidden_name in ("ffmpeg", "comfyui", "ollama"):
            self.assertNotIn(forbidden_name, boundary_source)

    def test_studio_export_empty_input_is_user_visible_without_starting_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            input_dir = Path(directory) / "exportar_srt" / "transcribir"
            input_dir.mkdir(parents=True)
            controller = RunController(
                studio_subtitle_export_input_service=(
                    StudioSubtitleExportInputService(directory)
                )
            )
            with patch("main.RunController") as controller_mock, patch(
                "main.run_application"
            ) as run_application_mock, patch("builtins.print") as print_mock:
                controller_mock.return_value.run.side_effect = (
                    lambda: controller.select_studio_subtitle_export_plan(
                        StudioSubtitleExportMode.TRANSCRIBIR
                    )
                )

                result = main.main()

        self.assertEqual(1, result)
        run_application_mock.assert_not_called()
        print_mock.assert_called_once_with(
            "ERROR\n"
            f"No se encontró ningún archivo MP4 o MP3 en {input_dir}.\n"
            "Operación: STUDIO/exportar_srt\n"
            "Acción recomendada: Pon en esa carpeta el vídeo .mp4 o el audio "
            ".mp3 que quieres transcribir y vuelve a intentarlo."
        )

    def test_studio_menu_input_errors_use_the_error_block(self):
        srt_action = (
            "Acción recomendada: Pon en esa carpeta un SRT en UTF-8, con "
            "bloques de número, tiempos y texto, y vuelve a intentarlo."
        )
        media_action = (
            "Acción recomendada: Pon en esa carpeta el vídeo .mp4 y el audio "
            "que pide VIDEO + AUDIO | SRT y vuelve a intentarlo."
        )
        bad_srt = "esto no es un srt\n"

        def intro_outro_without_folder(root):
            folder = root / "intro_outro"
            controller = RunController(
                studio_intro_outro_input_service=StudioIntroOutroInputService(
                    folder
                )
            )
            return (
                lambda: controller.select_studio_intro_outro_plan(
                    OperationalProfileKey("studio", "vertical", "studio_vertical")
                ),
                "No existe la carpeta de entrada para INTRO / OUTRO: "
                f"{folder}.\n"
                "Operación: STUDIO/intro_outro\n"
                "Acción recomendada: Pon en esa carpeta el vídeo .mp4 al que "
                "quieres añadir la intro o el outro y vuelve a intentarlo.",
            )

        def video_audio_srt_without_folder(root):
            folder = root / "video_audio_srt"
            controller = RunController(
                studio_video_audio_srt_input_service=(
                    StudioVideoAudioSrtInputService(folder)
                )
            )
            return (
                controller.select_studio_video_audio_srt_inputs,
                "No existe la carpeta de entrada VIDEO + AUDIO | SRT: "
                f"{folder}.\n"
                "Operación: STUDIO/video_audio_srt\n"
                f"{media_action}",
            )

        def video_audio_srt_with_invalid_srt(root):
            folder = root / "video_audio_srt"
            folder.mkdir()
            (folder / "clip.mp4").write_bytes(b"video")
            (folder / "voz.mp3").write_bytes(b"audio")
            (folder / "malo.srt").write_text(bad_srt, encoding="utf-8")
            controller = RunController(
                studio_video_audio_srt_input_service=(
                    StudioVideoAudioSrtInputService(folder)
                )
            )
            return (
                controller.select_studio_video_audio_srt_subtitle,
                "El archivo SRT de STUDIO no contiene cues utilizables: "
                f"{folder / 'malo.srt'}.\n"
                "Operación: STUDIO/video_audio_srt\n"
                f"{srt_action}",
            )

        def convert_with_invalid_srt(root):
            folder = root / "exportar_srt" / "convertir"
            folder.mkdir(parents=True)
            (folder / "malo.srt").write_text(bad_srt, encoding="utf-8")
            controller = RunController(
                studio_subtitle_export_input_service=(
                    StudioSubtitleExportInputService(root)
                )
            )
            return (
                lambda: controller.select_studio_subtitle_export_plan(
                    StudioSubtitleExportMode.CONVERTIR
                ),
                "El archivo SRT de STUDIO no contiene cues utilizables: "
                f"{folder / 'malo.srt'}.\n"
                "Operación: STUDIO/exportar_srt\n"
                f"{srt_action}",
            )

        cases = {
            "intro_outro_without_folder": intro_outro_without_folder,
            "video_audio_srt_without_folder": video_audio_srt_without_folder,
            "video_audio_srt_with_invalid_srt": video_audio_srt_with_invalid_srt,
            "convert_with_invalid_srt": convert_with_invalid_srt,
        }
        for name, build in cases.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as directory:
                run, expected = build(Path(directory))
                with patch("main.RunController") as controller_mock, patch(
                    "main.run_application"
                ) as run_application_mock, patch("builtins.print") as print_mock:
                    controller_mock.return_value.run.side_effect = run

                    result = main.main()

                self.assertEqual(1, result)
                run_application_mock.assert_not_called()
                print_mock.assert_called_once_with(f"ERROR\n{expected}")

    def test_studio_solo_video_input_error_is_user_visible(self):
        request = self.studio_request(
            "video",
            project_name="studio silent video",
        )

        with patch.dict(os.environ, {}, clear=True), patch(
            "main.RunController"
        ) as controller_mock, patch(
            "main.run_application",
            side_effect=ValueError(
                "El video seleccionado no contiene una pista de audio. "
                "SOLO VIDEO necesita audio para generar los subtítulos."
            ),
        ), patch("builtins.print") as print_mock:
            controller_mock.return_value.run.return_value = request

            result = main.main()

        self.assertEqual(1, result)
        output = print_mock.call_args.args[0]
        self.assertTrue(output.startswith("ERROR\n"))
        self.assertIn("SOLO VIDEO necesita audio", output)
        self.assertIn("STUDIO/video", output)
        self.assertNotIn("Traceback", output)

    def test_menu_input_error_is_user_visible_without_starting_runtime(self):
        profile = SimpleNamespace(
            video_extensions=(".mp4",),
            subtitle_extensions=(".srt",),
        )
        with tempfile.TemporaryDirectory() as directory:
            input_dir = Path(directory) / "video"
            input_dir.mkdir()
            controller = RunController(
                studio_input_preparation_service=StudioInputPreparationService(
                    directory
                )
            )
            with patch("main.RunController") as controller_mock, patch(
                "main.run_application"
            ) as run_application_mock, patch("builtins.print") as print_mock:
                controller_mock.return_value.run.side_effect = (
                    lambda: controller.select_studio_input_files(profile, "video")
                )

                result = main.main()

        self.assertEqual(1, result)
        run_application_mock.assert_not_called()
        print_mock.assert_called_once_with(
            "ERROR\n"
            f"No se encontró ningún archivo MP4 en {input_dir}.\n"
            "Operación: STUDIO/video\n"
            "Acción recomendada: Pon en esa carpeta los archivos que pide "
            "SOLO VIDEO y vuelve a intentarlo."
        )

    def test_runtime_input_error_is_user_visible_not_internal(self):
        with tempfile.TemporaryDirectory() as directory:
            input_script = Path(directory) / "guion.txt"
            input_script.write_text("", encoding="utf-8")

            def prepare_empty_script(request):
                ScriptPreparationService().prepare(
                    builders={"script": True},
                    ai_config={},
                    profile={},
                    input_script_path=input_script,
                    input_topic_path=Path(directory) / "tema.txt",
                    output_script_path=Path(directory) / "salida.txt",
                    source_mode="manual",
                )

            with patch.dict(os.environ, {}, clear=True), patch(
                "main.RunController"
            ) as controller_mock, patch(
                "main.run_application",
                side_effect=prepare_empty_script,
            ), patch("builtins.print") as print_mock:
                controller_mock.return_value.run.return_value = self.design_request()

                result = main.main()

        self.assertEqual(1, result)
        print_mock.assert_called_once_with(
            "ERROR\n"
            f"El archivo {input_script.as_posix()} está vacío.\n"
            "Operación: Preparar el guion\n"
            f"Acción recomendada: Escribe el guion en {input_script.as_posix()} "
            "y vuelve a intentarlo."
        )

    def test_output_reset_blocked_error_stops_pipeline_cleanly(self):
        request = self.design_request(
            project_name="blocked output",
            clear_output=True,
        )

        with patch.dict(os.environ, {}, clear=True), patch(
            "main.RunController"
        ) as controller_mock, patch("main.OutputManager") as output_manager, patch(
            "main.run_application"
        ) as run_application_mock, patch(
            "builtins.print"
        ) as print_mock, tempfile.TemporaryDirectory() as directory:
            controller_mock.return_value.run.return_value = request
            manager = OutputManager()
            manager.output_path = Path(directory) / "output"
            manager.output_path.mkdir()
            locked = manager.output_path / "locked.mp4"
            locked.write_bytes(b"video")
            output_manager.return_value = manager

            with patch.object(
                Path,
                "unlink",
                side_effect=PermissionError(13, "in use", str(locked), 32),
            ):
                result = main.main()

        self.assertEqual(1, result)
        run_application_mock.assert_not_called()
        print_mock.assert_called_once_with(
            "ERROR\n"
            "No se puede eliminar OUTPUT porque uno de sus archivos "
            "está siendo utilizado por otro programa.\n"
            "Operación: Eliminar OUTPUT\n"
            f"Recurso: {locked}\n"
            "Acción recomendada: Cierra el archivo y vuelve a intentarlo."
        )

    def test_output_reset_normal_path_continues_to_runtime(self):
        request = self.design_request(
            project_name="reset output",
            clear_output=True,
        )

        with patch.dict(os.environ, {}, clear=True), patch(
            "main.RunController"
        ) as controller_mock, patch("main.OutputManager") as output_manager, patch(
            "main.run_application"
        ) as run_application_mock:
            controller_mock.return_value.run.return_value = request

            result = main.main()

        self.assertEqual(0, result)
        output_manager.return_value.reset.assert_called_once_with()
        run_application_mock.assert_called_once()
        self.assertEqual(
            "design_video",
            run_application_mock.call_args.kwargs["request"].route.mode,
        )


if __name__ == "__main__":
    unittest.main()
