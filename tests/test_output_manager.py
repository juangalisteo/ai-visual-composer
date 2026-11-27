"""Overwriting one project removes only its folder (A1, PRUEBA-GS fallos 2 y 3)."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.managers.output_manager import OutputManager, project_folder_in_output
from app.shared.operational_error import OperationalError


class OutputManagerTest(unittest.TestCase):

    def _manager(self, root):
        manager = OutputManager(root / "output")
        manager.output_path.mkdir()
        return manager

    def test_remove_project_removes_only_that_project(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = self._manager(Path(directory))
            target = manager.output_path / "demo" / "video"
            target.mkdir(parents=True)
            (target / "demo.mp4").write_bytes(b"video")
            other = manager.output_path / "otro" / "video"
            other.mkdir(parents=True)
            (other / "otro.mp4").write_bytes(b"video")
            (manager.output_path / "suelto.txt").write_text("x", encoding="utf-8")

            with patch(
                "app.managers.output_manager.ProgressLogger.info"
            ) as info:
                manager.remove_project("demo")
            remaining = sorted(
                path.relative_to(manager.output_path).as_posix()
                for path in manager.output_path.rglob("*")
            )

        self.assertEqual(
            ["otro", "otro/video", "otro/video/otro.mp4", "suelto.txt"],
            remaining,
        )
        info.assert_called_once_with(
            "Proyecto «demo» borrado para sobrescribirlo."
        )

    def test_remove_project_uses_the_folder_name_of_the_project(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = self._manager(Path(directory))
            (manager.output_path / "mi proyecto").mkdir()

            manager.remove_project("  mi:   proyecto ")

            self.assertEqual([], list(manager.output_path.iterdir()))

    def test_remove_project_removes_a_file_with_the_project_name(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = self._manager(Path(directory))
            (manager.output_path / "demo").write_bytes(b"x")

            manager.remove_project("demo")

            self.assertEqual([], list(manager.output_path.iterdir()))

    def test_missing_project_is_nothing_to_remove(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = self._manager(Path(directory))
            (manager.output_path / "otro").mkdir()

            with patch(
                "app.managers.output_manager.ProgressLogger.info"
            ) as info:
                manager.remove_project("demo")

            self.assertEqual(["otro"], [p.name for p in manager.output_path.iterdir()])
        info.assert_not_called()

    def test_a_name_outside_output_is_never_removed(self):
        for name in (".", ".."):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                manager = self._manager(root)
                (manager.output_path / "demo").mkdir()
                (root / "keep.txt").write_text("x", encoding="utf-8")

                with self.assertRaises(OperationalError) as raised:
                    manager.remove_project(name)

                self.assertTrue((manager.output_path / "demo").is_dir())
                self.assertTrue((root / "keep.txt").is_file())
                context = raised.exception.context
                self.assertEqual("VALIDATION", context.family)
                self.assertEqual(
                    f"«{name}» no es una carpeta de proyecto dentro de output/.",
                    context.user_message,
                )
                self.assertEqual("Sobrescribir el proyecto", context.operation)

    def test_project_folder_in_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            self.assertTrue(project_folder_in_output(output / "demo", output))
            self.assertFalse(project_folder_in_output(output, output))
            self.assertFalse(project_folder_in_output(output / "..", output))
            self.assertFalse(project_folder_in_output(output / "a" / "b", output))
            self.assertFalse(project_folder_in_output(output / ".", output))

    def test_windows_file_in_use_is_a_domain_error(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = self._manager(Path(directory))
            (manager.output_path / "demo").mkdir()
            locked = manager.output_path / "demo" / "locked.mp4"
            locked.write_bytes(b"video")
            error = PermissionError(13, "in use", str(locked), 32)

            with patch(
                "app.managers.output_manager.shutil.rmtree", side_effect=error
            ), self.assertRaises(OperationalError) as raised:
                manager.remove_project("demo")

        context = raised.exception.context
        self.assertEqual("FILESYSTEM", context.family)
        self.assertEqual(
            "No se puede sobrescribir el proyecto «demo» porque uno de sus "
            "archivos está siendo utilizado por otro programa.",
            context.user_message,
        )
        self.assertEqual(
            "Cierra el archivo y vuelve a intentarlo.",
            context.recommended_action,
        )
        self.assertEqual("Sobrescribir el proyecto", context.operation)
        self.assertEqual(str(locked), context.resource)
        self.assertIs(error, raised.exception.__cause__)

    def test_unrelated_permission_error_is_raised_again(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = self._manager(Path(directory))
            (manager.output_path / "demo").mkdir()
            error = PermissionError(13, "access denied", "x", 5)

            with patch(
                "app.managers.output_manager.shutil.rmtree", side_effect=error
            ), self.assertRaises(PermissionError):
                manager.remove_project("demo")

    def test_the_program_has_no_way_to_empty_output(self):
        self.assertFalse(hasattr(OutputManager, "reset"))


if __name__ == "__main__":
    unittest.main()
