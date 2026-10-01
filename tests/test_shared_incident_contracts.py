import ast
from pathlib import Path
import unittest

from app.shared.error_context import (
    ErrorContext,
    ErrorSeverity,
    ExitKind,
)
from app.shared.operational_error import OperationalError
from app.shared.operation_warnings import OperationWarning, OperationWarnings


class SharedIncidentContractsTest(unittest.TestCase):

    def make_context(self, **overrides):
        values = {
            "family": "external_service",
            "severity": "fatal_operational",
            "user_message": "El servicio no respondió.",
            "exit_kind": "operational_error",
        }
        values.update(overrides)
        return ErrorContext(**values)

    def test_context_normalizes_valid_values_and_keeps_optional_fields(self):
        context = self.make_context(
            family=" external_service ",
            severity="fatal_operational",
            exit_kind="operational_error",
            recommended_action="Reintenta cuando el servicio esté disponible.",
            operation="Generación de imagen",
            resource="input/source.png",
            diagnostic_reference="output/diagnostics.json",
        )

        self.assertEqual("EXTERNAL_SERVICE", context.family)
        self.assertIs(ErrorSeverity.FATAL_OPERATIONAL, context.severity)
        self.assertIs(ExitKind.OPERATIONAL_ERROR, context.exit_kind)
        self.assertEqual("Generación de imagen", context.operation)
        self.assertEqual("input/source.png", context.resource)
        self.assertEqual("output/diagnostics.json", context.diagnostic_reference)

    def test_context_optional_fields_default_to_none(self):
        context = self.make_context()

        self.assertIsNone(context.recommended_action)
        self.assertIsNone(context.operation)
        self.assertIsNone(context.resource)
        self.assertIsNone(context.diagnostic_reference)
        self.assertEqual({}, dict(context.technical_metadata))

    def test_context_freezes_metadata_without_shared_mutable_state(self):
        metadata = {
            "zeta": ["one", {"nested": True}],
            "alpha": 2,
        }
        context = self.make_context(technical_metadata=metadata)
        metadata["zeta"].append("later")
        metadata["zeta"][1]["nested"] = False

        self.assertEqual(("one", {"nested": True}), context.technical_metadata["zeta"])
        self.assertEqual(("alpha", "zeta"), tuple(context.technical_metadata))
        with self.assertRaises(TypeError):
            context.technical_metadata["alpha"] = 3
        with self.assertRaises(TypeError):
            context.technical_metadata["zeta"][1]["nested"] = False

    def test_operational_error_carries_context_and_preserves_explicit_cause(self):
        context = self.make_context()
        source = OSError("socket closed")

        try:
            try:
                raise source
            except OSError as error:
                raise OperationalError(context) from error
        except OperationalError as error:
            self.assertIs(context, error.context)
            self.assertIs(source, error.__cause__)
            self.assertEqual(context.user_message, str(error))
        else:
            self.fail("OperationalError debía propagarse.")

    def test_warning_is_non_fatal_and_associates_operation(self):
        warning = OperationWarning(
            family="degradation",
            user_message="No se pudieron resolver overlays.",
            operation="VIDEO",
            technical_metadata={"attempt": 1},
        )

        self.assertEqual("DEGRADATION", warning.family)
        self.assertEqual("VIDEO", warning.operation)
        self.assertEqual(1, warning.technical_metadata["attempt"])

    def test_warning_collections_do_not_share_state(self):
        first = OperationWarnings()
        second = OperationWarnings()
        first.add(
            OperationWarning(
                family="degradation",
                user_message="Resumen incompleto.",
            )
        )

        self.assertEqual(1, len(first))
        self.assertEqual(0, len(second))
        self.assertEqual((), second.snapshot())

    def test_shared_contracts_do_not_import_runtime_or_domain_layers(self):
        modules = (
            "app.shared.error_context",
            "app.shared.operational_error",
            "app.shared.operation_warnings",
        )
        forbidden = (
            "main",
            "app.core.start",
            "app.controllers",
            "app.providers",
            "app.modules.studio",
        )

        for module_name in modules:
            module = __import__(module_name, fromlist=["*"])
            tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module)
            for imported in imports:
                for forbidden_import in forbidden:
                    self.assertFalse(
                        imported == forbidden_import
                        or imported.startswith(forbidden_import + "."),
                        f"{module_name} no debe importar {imported}",
                    )
