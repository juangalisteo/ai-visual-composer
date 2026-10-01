import ast
import inspect
import unittest

from app.cli.error_presenter import CliPresentation, ErrorPresenter
from app.shared.error_context import ErrorContext, ErrorSeverity, ExitKind
from app.shared.operational_error import OperationalError
from app.shared.operation_warnings import OperationWarning


class ErrorPresenterTest(unittest.TestCase):

    def setUp(self):
        self.presenter = ErrorPresenter()

    def make_context(self, **overrides):
        values = {
            "family": "filesystem",
            "severity": ErrorSeverity.FATAL_OPERATIONAL,
            "user_message": "No se pudo completar la operación.",
            "exit_kind": ExitKind.OPERATIONAL_ERROR,
        }
        values.update(overrides)
        return ErrorContext(**values)

    def test_fatal_operational_presentation_is_clear_and_safe(self):
        presentation = self.presenter.present_context(self.make_context())

        self.assertEqual("ERROR", presentation.heading)
        self.assertEqual(
            ("No se pudo completar la operación.",),
            presentation.user_lines,
        )
        self.assertEqual((), presentation.diagnostic_lines)

    def test_operational_presentation_includes_optional_user_details(self):
        context = self.make_context(
            operation="Preparar entrada",
            resource="input/archivo.txt",
            recommended_action="Revise el archivo y vuelva a intentarlo.",
            diagnostic_reference="output/diagnostics/run-001.json",
        )

        presentation = self.presenter.present_context(context)

        self.assertEqual(
            (
                "No se pudo completar la operación.",
                "Operación: Preparar entrada",
                "Recurso: input/archivo.txt",
                "Acción recomendada: Revise el archivo y vuelva a intentarlo.",
            ),
            presentation.user_lines,
        )
        self.assertEqual(
            ("Diagnóstico técnico: output/diagnostics/run-001.json",),
            presentation.diagnostic_lines,
        )

    def test_operational_wrapper_uses_context_without_exposing_cause(self):
        context = self.make_context(technical_metadata={"stderr": "secret stderr"})
        error = OperationalError(context)
        error.__cause__ = RuntimeError("internal cause")

        presentation = self.presenter.present_operational_error(error)

        self.assertEqual("ERROR", presentation.heading)
        self.assertNotIn("secret stderr", presentation.text)
        self.assertNotIn("internal cause", presentation.text)

    def test_internal_error_uses_a_distinct_safe_heading(self):
        presentation = self.presenter.present_context(
            self.make_context(
                severity=ErrorSeverity.FATAL_INTERNAL,
                user_message="Ocurrió un problema interno inesperado.",
                exit_kind=ExitKind.INTERNAL_ERROR,
                diagnostic_reference="output/diagnostics/internal.json",
                technical_metadata={"traceback": "private details"},
            )
        )

        self.assertEqual("ERROR INTERNO", presentation.heading)
        self.assertIn("Ocurrió un problema interno inesperado.", presentation.text)
        self.assertIn("output/diagnostics/internal.json", presentation.text)
        self.assertNotIn("private details", presentation.text)

    def test_warning_is_non_fatal_and_uses_warning_heading(self):
        warning = OperationWarning(
            family="degradation",
            user_message="Se usó una salida parcial.",
            operation="Generación",
        )

        presentation = self.presenter.present_warning(warning)

        self.assertEqual("AVISO", presentation.heading)
        self.assertIn("Se usó una salida parcial.", presentation.text)
        self.assertNotIn("ERROR", presentation.heading)

    def test_cancellation_is_distinct_from_success_and_error(self):
        presentation = self.presenter.present_context(
            self.make_context(
                severity=ErrorSeverity.RECOVERABLE,
                user_message="La operación fue cancelada.",
                exit_kind=ExitKind.CANCELLATION,
            )
        )

        self.assertEqual("CANCELADO", presentation.heading)
        self.assertNotEqual("ERROR", presentation.heading)
        self.assertNotEqual("AVISO", presentation.heading)

    def test_recoverable_context_has_its_own_presentation(self):
        presentation = self.presenter.present_context(
            self.make_context(
                severity=ErrorSeverity.RECOVERABLE,
                user_message="Falta un archivo requerido.",
                exit_kind=ExitKind.OPERATIONAL_ERROR,
                recommended_action="Seleccione un archivo válido.",
            )
        )

        self.assertEqual("CORREGIR", presentation.heading)
        self.assertIn("Seleccione un archivo válido.", presentation.text)

    def test_optional_fields_never_render_none_or_placeholder_text(self):
        presentation = self.presenter.present_context(self.make_context())

        self.assertNotIn("None", presentation.text)
        self.assertNotIn("null", presentation.text.lower())

    def test_presentation_is_deterministic_and_does_not_write(self):
        context = self.make_context(
            operation="Procesar",
            resource="input/a.txt",
        )

        first = self.presenter.present(context)
        second = self.presenter.present(context)

        self.assertEqual(first, second)
        self.assertIsInstance(first, CliPresentation)
        self.assertEqual(first.text, "\n".join(first.lines))

    def test_present_accepts_only_shared_incident_contracts(self):
        with self.assertRaises(TypeError):
            self.presenter.present(RuntimeError("not shared"))

    def test_presenter_has_no_domain_imports_or_nominal_knowledge(self):
        import app.cli.error_presenter as presenter_module

        source = inspect.getsource(presenter_module).lower()
        tree = ast.parse(source)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)

        forbidden_imports = (
            "main",
            "app.core.start",
            "app.controllers",
            "app.providers",
            "app.modules",
        )
        for imported in imports:
            for forbidden in forbidden_imports:
                self.assertFalse(
                    imported == forbidden or imported.startswith(forbidden + "."),
                    f"El presentador no debe importar {imported}",
                )
        for forbidden_name in ("studio", "ffmpeg", "comfyui", "ollama"):
            self.assertNotIn(forbidden_name, source)
        self.assertNotIn("print(", source)


if __name__ == "__main__":
    unittest.main()
