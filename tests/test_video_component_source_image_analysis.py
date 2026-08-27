import struct
import tempfile
import unittest
from pathlib import Path

from app.modules.video_component import (
    SourceImageAnalysisError,
    SourceImageAnalyzer,
)


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def write_png_header(
    path,
    width,
    height
):
    path.write_bytes(
        PNG_SIGNATURE
        + struct.pack(
            ">I",
            13
        )
        + b"IHDR"
        + struct.pack(
            ">II",
            width,
            height
        )
        + b"\x08\x02\x00\x00\x00"
        + b"\x00\x00\x00\x00"
    )


class SourceImageAnalyzerTest(unittest.TestCase):

    def test_analyzes_valid_png_source_image(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = (
                Path(temp_dir)
                / "source.png"
            )
            write_png_header(
                source_path,
                1920,
                1080
            )

            context = SourceImageAnalyzer().analyze(
                source_path
            )

        self.assertEqual(
            1920,
            context.width
        )
        self.assertEqual(
            1080,
            context.height
        )
        self.assertEqual(
            "16:9",
            context.aspect_ratio
        )
        self.assertEqual(
            "landscape",
            context.orientation
        )
        self.assertEqual(
            "PNG",
            context.image_format
        )

    def test_detects_portrait_orientation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = (
                Path(temp_dir)
                / "source.png"
            )
            write_png_header(
                source_path,
                1080,
                1920
            )

            context = SourceImageAnalyzer().analyze(
                source_path
            )

        self.assertEqual(
            "portrait",
            context.orientation
        )
        self.assertEqual(
            "9:16",
            context.aspect_ratio
        )

    def test_detects_square_orientation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = (
                Path(temp_dir)
                / "source.png"
            )
            write_png_header(
                source_path,
                1024,
                1024
            )

            context = SourceImageAnalyzer().analyze(
                source_path
            )

        self.assertEqual(
            "square",
            context.orientation
        )
        self.assertEqual(
            "1:1",
            context.aspect_ratio
        )

    def test_fails_when_source_image_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = (
                Path(temp_dir)
                / "source.png"
            )

            with self.assertRaises(
                FileNotFoundError
            ):
                SourceImageAnalyzer().analyze(
                    source_path
                )

    def test_fails_when_source_image_is_invalid(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = (
                Path(temp_dir)
                / "source.png"
            )
            source_path.write_text(
                "not an image",
                encoding="utf-8"
            )

            with self.assertRaises(
                SourceImageAnalysisError
            ):
                SourceImageAnalyzer().analyze(
                    source_path
                )


if __name__ == "__main__":
    unittest.main()
