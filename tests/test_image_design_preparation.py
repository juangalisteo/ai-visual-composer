import tempfile
import unittest
from pathlib import Path

from app.modules.images import (
    ImageDesignPreparationService,
    PreparedImageDesign,
)


class ImageDesignPreparationServiceTest(unittest.TestCase):

    def test_reads_manual_image_design(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            design_path = (
                Path(temp_dir)
                / "guion_imagen.txt"
            )
            design_path.write_text(
                "\nRetrato cinematografico de una cientifica.\n",
                encoding="utf-8"
            )

            prepared = ImageDesignPreparationService().prepare(
                input_path=design_path
            )

        self.assertIsInstance(
            prepared,
            PreparedImageDesign
        )
        self.assertEqual(
            "Retrato cinematografico de una cientifica.",
            prepared.text
        )
        self.assertEqual(
            design_path,
            prepared.source_path
        )
        self.assertEqual(
            "manual_design",
            prepared.source
        )
        self.assertEqual(
            "image",
            prepared.target
        )
        self.assertEqual(
            1,
            prepared.expected_images
        )

    def test_fails_when_design_file_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_path = (
                Path(temp_dir)
                / "guion_imagen.txt"
            )

            with self.assertRaises(
                FileNotFoundError
            ):
                ImageDesignPreparationService().prepare(
                    input_path=missing_path
                )

    def test_fails_when_design_file_is_empty(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            design_path = (
                Path(temp_dir)
                / "guion_imagen.txt"
            )
            design_path.write_text(
                "",
                encoding="utf-8"
            )

            with self.assertRaises(
                ValueError
            ):
                ImageDesignPreparationService().prepare(
                    input_path=design_path
                )

    def test_fails_when_design_file_is_whitespace(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            design_path = (
                Path(temp_dir)
                / "guion_imagen.txt"
            )
            design_path.write_text(
                " \n\t ",
                encoding="utf-8"
            )

            with self.assertRaises(
                ValueError
            ):
                ImageDesignPreparationService().prepare(
                    input_path=design_path
                )


if __name__ == "__main__":
    unittest.main()
