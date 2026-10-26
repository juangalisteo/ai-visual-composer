import unittest
import os
import tempfile
import inspect
from unittest.mock import patch

import main
from app.controllers.run_controller import RunController
from app.core import start
from app.modules.studio import (
    StudioMontageError,
    StudioSubtitleExportInputError,
    StudioVideoAudioSrtError,
)
from app.managers.output_manager import OutputResetBlockedError
from app.shared.error_context import ErrorContext, ErrorSeverity, ExitKind
from app.shared.operational_error import OperationalError


class MainErrorHandlingTest(unittest.TestCase):

    def design_options(self):
        return {
            "profile_component": "video",
            "profile_format": "vertical",
            "profile_id": "video_vertical",
            "voice_config": "",
            "music_category": None,
            "overlays_mode": "off",
            "project_name": "error test",
            "visual_pipeline": "video",
            "script_source": "manual_design",
            "design_target": "video",
            "pipeline_mode": "design_video",
            "clear_output": False,
        }

    def test_external_operational_error_is_user_visible_without_traceback(self):
        options = self.design_options()
        error = OperationalError(
            ErrorContext(
                family="EXTERNAL_SERVICE",
                severity=ErrorSeverity.FATAL_OPERATIONAL,
                user_message="La interpretacion visual no pudo completarse.",
                exit_kind=ExitKind.OPERATIONAL_ERROR,
                operation="Interpretar diseno visual",
                recommended_action="Comprueba el proveedor e intentalo de nuevo.",
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
            "main.iniciar",
            side_effect=error
        ), patch(
            "builtins.print"
        ) as print_mock:
            controller_mock.return_value.run.return_value = options

            result = main.main()

        self.assertEqual(
            1,
            result
        )
        print_mock.assert_called_once_with(
            "ERROR\n"
            "La interpretacion visual no pudo completarse.\n"
            "Operación: Interpretar diseno visual\n"
            "Acción recomendada: Comprueba el proveedor e intentalo de nuevo."
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
            "main.iniciar",
            side_effect=OperationalError(context),
        ), patch("builtins.print") as print_mock:
            controller_mock.return_value.run.return_value = self.design_options()

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
        options = self.design_options()
        error = OperationalError(
            ErrorContext(
                family="VALIDATION",
                severity=ErrorSeverity.FATAL_OPERATIONAL,
                user_message=(
                    "La imagen candidata requiere revision manual "
                    "antes de continuar."
                ),
                exit_kind=ExitKind.OPERATIONAL_ERROR,
                operation="Validar calidad visual de scene_001",
                resource="output/images/scene_001.png",
                recommended_action=(
                    "Revise la imagen candidata y la evidencia de "
                    "validacion; no se ha aprobado como asset final."
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
            "main.iniciar", side_effect=error
        ), patch("builtins.print") as print_mock:
            controller_mock.return_value.run.return_value = options

            result = main.main()

        self.assertEqual(1, result)
        output = print_mock.call_args.args[0]
        self.assertTrue(output.startswith("ERROR\n"))
        self.assertIn("revision manual", output)
        self.assertIn("no se ha aprobado como asset final", output)
        self.assertIn("visual_quality_result.json", output)
        self.assertNotIn("ERROR INTERNO", output)
        self.assertNotIn("Traceback", output)

    def test_menu_cancellation_is_clean_and_uses_exit_code_zero(self):
        error = OperationalError(
            ErrorContext(
                family="CANCELLATION",
                severity=ErrorSeverity.RECOVERABLE,
                user_message="La operacion fue cancelada por el usuario.",
                exit_kind=ExitKind.CANCELLATION,
                operation="Seleccion de opciones",
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
                "main.iniciar", side_effect=KeyboardInterrupt
            ) as iniciar_mock, patch("builtins.print") as print_mock:
                controller_mock.return_value.run.return_value = self.design_options()

                result = main.main()

            self.assertEqual(130, result)
            iniciar_mock.assert_called_once()
            self.assertEqual(
                "design_video",
                iniciar_mock.call_args.kwargs["request"].route.mode,
            )
            self.assertTrue(os.path.exists(artifact))
            output = print_mock.call_args.args[0]
            self.assertTrue(output.startswith("CANCELADO\n"))
            self.assertNotIn("Traceback", output)
            self.assertNotIn("ERROR INTERNO", output)

    def test_eof_is_clean_input_cancellation_without_runtime(self):
        with patch("main.RunController") as controller_mock, patch(
            "main.iniciar"
        ) as iniciar_mock, patch("builtins.print") as print_mock:
            controller_mock.return_value.run.side_effect = EOFError()

            result = main.main()

        self.assertEqual(0, result)
        iniciar_mock.assert_not_called()
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
                    "main.iniciar", side_effect=error
                ), patch("builtins.print") as print_mock:
                    options = self.design_options()
                    options.update(
                        profile_component="studio",
                        profile_id="studio_vertical",
                        pipeline_mode="studio",
                        studio_input_mode="srt_video",
                    )
                    controller_mock.return_value.run.return_value = options
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
            "main.iniciar",
            side_effect=unexpected,
        ), patch("main.ErrorPresenter") as presenter_mock, patch(
            "builtins.print"
        ) as print_mock:
            controller_mock.return_value.run.return_value = self.design_options()
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
            "main.iniciar",
            side_effect=ValueError("internal validation detail"),
        ), patch("builtins.print") as print_mock:
            controller_mock.return_value.run.return_value = self.design_options()

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
                "main.iniciar",
                side_effect=error,
            ), patch("builtins.print") as print_mock:
                options = self.design_options()
                options.update(
                    profile_component="studio",
                    profile_id="studio_vertical",
                    pipeline_mode="studio",
                    studio_input_mode="srt_video",
                )
                controller_mock.return_value.run.return_value = options

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
        boundary_source = (
            inspect.getsource(main.main)
            + inspect.getsource(main._present_unexpected_error)
        ).lower()
        for forbidden_name in ("ffmpeg", "comfyui", "ollama"):
            self.assertNotIn(forbidden_name, boundary_source)

    def test_studio_export_empty_input_is_user_visible_without_starting_runtime(self):
        with patch("main.RunController") as controller_mock, patch(
            "main.iniciar"
        ) as iniciar_mock, patch("builtins.print") as print_mock:
            controller_mock.return_value.run.side_effect = (
                StudioSubtitleExportInputError(
                    "No se encontro ningun archivo MP4 o MP3 en:\n"
                    "input/studio/exportar_srt/transcribir/\n\n"
                    "Anade un archivo valido e intentalo de nuevo."
                )
            )

            result = main.main()

        self.assertEqual(1, result)
        iniciar_mock.assert_not_called()
        print_mock.assert_called_once_with(
            "ERROR: No se encontro ningun archivo MP4 o MP3 en:\n"
            "input/studio/exportar_srt/transcribir/\n\n"
            "Anade un archivo valido e intentalo de nuevo."
        )

    def test_studio_solo_video_input_error_is_user_visible(self):
        options = {
            "profile_component": "studio",
            "profile_format": "vertical",
            "profile_id": "studio_vertical",
            "voice_config": "",
            "music_category": None,
            "project_name": "studio silent video",
            "visual_pipeline": "studio",
            "script_source": "",
            "design_target": "",
            "pipeline_mode": "studio",
            "studio_input_mode": "video",
            "clear_output": False,
        }

        with patch.dict(os.environ, {}, clear=True), patch(
            "main.RunController"
        ) as controller_mock, patch(
            "main.iniciar",
            side_effect=ValueError(
                "El video seleccionado no contiene una pista de audio. "
                "SOLO VIDEO necesita audio para generar los subtitulos."
            ),
        ), patch("builtins.print") as print_mock:
            controller_mock.return_value.run.return_value = options

            result = main.main()

        self.assertEqual(1, result)
        output = print_mock.call_args.args[0]
        self.assertTrue(output.startswith("ERROR\n"))
        self.assertIn("SOLO VIDEO necesita audio", output)
        self.assertIn("STUDIO/video", output)
        self.assertNotIn("Traceback", output)

    def test_output_reset_blocked_error_stops_pipeline_cleanly(self):
        options = {
            "profile_component": "video",
            "profile_format": "vertical",
            "profile_id": "video_vertical",
            "voice_config": "",
            "music_category": None,
            "overlays_mode": "off",
            "project_name": "blocked output",
            "visual_pipeline": "video",
            "script_source": "manual_design",
            "design_target": "video",
            "pipeline_mode": "design_video",
            "clear_output": True,
        }

        with patch.dict(os.environ, {}, clear=True), patch(
            "main.RunController"
        ) as controller_mock, patch("main.OutputManager") as output_manager, patch(
            "main.iniciar"
        ) as iniciar_mock, patch("builtins.print") as print_mock:
            controller_mock.return_value.run.return_value = options
            output_manager.return_value.reset.side_effect = (
                OutputResetBlockedError(
                    "No se puede eliminar OUTPUT porque uno de sus archivos "
                    "esta siendo utilizado por otro programa.\n\n"
                    "Cierra el archivo y vuelve a intentarlo."
                )
            )

            result = main.main()

        self.assertEqual(1, result)
        iniciar_mock.assert_not_called()
        print_mock.assert_called_once_with(
            "ERROR: No se puede eliminar OUTPUT porque uno de sus archivos "
            "esta siendo utilizado por otro programa.\n\n"
            "Cierra el archivo y vuelve a intentarlo."
        )

    def test_output_reset_normal_path_continues_to_runtime(self):
        options = {
            "profile_component": "video",
            "profile_format": "vertical",
            "profile_id": "video_vertical",
            "voice_config": "",
            "music_category": None,
            "overlays_mode": "off",
            "project_name": "reset output",
            "visual_pipeline": "video",
            "script_source": "manual_design",
            "design_target": "video",
            "pipeline_mode": "design_video",
            "clear_output": True,
        }

        with patch.dict(os.environ, {}, clear=True), patch(
            "main.RunController"
        ) as controller_mock, patch("main.OutputManager") as output_manager, patch(
            "main.iniciar"
        ) as iniciar_mock:
            controller_mock.return_value.run.return_value = options

            result = main.main()

        self.assertEqual(0, result)
        output_manager.return_value.reset.assert_called_once_with()
        iniciar_mock.assert_called_once()
        self.assertEqual(
            "design_video",
            iniciar_mock.call_args.kwargs["request"].route.mode,
        )


if __name__ == "__main__":
    unittest.main()
