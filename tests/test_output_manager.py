import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.managers.output_manager import (
    OutputManager,
    OutputResetBlockedError,
)


class OutputManagerTest(unittest.TestCase):

    def _manager(self, root):
        manager = OutputManager()
        manager.output_path = root / "output"
        manager.output_path.mkdir()
        return manager

    def test_reset_removes_existing_output_and_reports_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = self._manager(Path(directory))
            (manager.output_path / "result.mp4").write_bytes(b"video")
            nested = manager.output_path / "project" / "video"
            nested.mkdir(parents=True)
            (nested / "result.mp4").write_bytes(b"video")

            with patch(
                "app.managers.output_manager.ProgressLogger.info"
            ) as info:
                manager.reset()
            remaining = list(manager.output_path.iterdir())

        self.assertEqual([], remaining)
        info.assert_called_once_with("Output reseteado.")

    def test_reset_converts_windows_file_in_use_to_domain_error(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = self._manager(Path(directory))
            locked = manager.output_path / "locked.mp4"
            locked.write_bytes(b"video")
            error = PermissionError(13, "in use", str(locked), 32)

            with patch.object(Path, "unlink", side_effect=error), self.assertRaisesRegex(
                OutputResetBlockedError,
                "No se puede eliminar OUTPUT",
            ):
                manager.reset()

    def test_reset_reraises_unrelated_permission_error(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = self._manager(Path(directory))
            blocked = manager.output_path / "denied.mp4"
            blocked.write_bytes(b"video")
            error = PermissionError(13, "access denied", str(blocked), 5)

            with patch.object(Path, "unlink", side_effect=error), self.assertRaises(
                PermissionError
            ):
                manager.reset()


if __name__ == "__main__":
    unittest.main()
