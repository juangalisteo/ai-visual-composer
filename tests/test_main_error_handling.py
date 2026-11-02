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
    StudioMontageError,
    StudioSubtitleExportInputError,
    StudioVideoAudioSrtError,
)
from app.managers.output_manager import OutputResetBlockedError
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
        with patch("main.RunController") as controller_mock, patch(
            "main.run_application"
        ) as run_application_mock, patch("builtins.print") as print_mock:
            controller_mock.return_value.run.side_effect = (
                StudioSubtitleExportInputError(
                    "No se encontró ningún archivo MP4 o MP3 en:\n"
                    "input/studio/exportar_srt/transcribir/\n\n"
                    "Añade un archivo válido e inténtalo de nuevo."
                )
            )

            result = main.main()

        self.assertEqual(1, result)
        run_application_mock.assert_not_called()
        print_mock.assert_called_once_with(
            "ERROR: No se encontró ningún archivo MP4 o MP3 en:\n"
            "input/studio/exportar_srt/transcribir/\n\n"
            "Añade un archivo válido e inténtalo de nuevo."
        )

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
        ) as run_application_mock, patch("builtins.print") as print_mock:
            controller_mock.return_value.run.return_value = request
            output_manager.return_value.reset.side_effect = (
                OutputResetBlockedError(
                    "No se puede eliminar OUTPUT porque uno de sus archivos "
                    "está siendo utilizado por otro programa.\n\n"
                    "Cierra el archivo y vuelve a intentarlo."
                )
            )

            result = main.main()

        self.assertEqual(1, result)
        run_application_mock.assert_not_called()
        print_mock.assert_called_once_with(
            "ERROR: No se puede eliminar OUTPUT porque uno de sus archivos "
            "está siendo utilizado por otro programa.\n\n"
            "Cierra el archivo y vuelve a intentarlo."
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
