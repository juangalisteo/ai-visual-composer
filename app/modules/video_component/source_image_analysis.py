from math import gcd
from pathlib import Path
import struct

from app.modules.video_component.models import (
    MinimalVisualContext,
    SourceImageAnalysisError,
)


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class SourceImageAnalyzer:

    def analyze(
        self,
        source_path
    ) -> MinimalVisualContext:
        path = Path(
            source_path
        )

        if not path.exists():
            raise FileNotFoundError(
                f"Source image does not exist: {path}"
            )

        if not path.is_file():
            raise SourceImageAnalysisError(
                f"Source image path is not a file: {path}"
            )

        width, height, image_format = (
            self._read_image_metadata(
                path
            )
        )

        return MinimalVisualContext(
            source_path=path,
            width=width,
            height=height,
            aspect_ratio=self._aspect_ratio(
                width,
                height
            ),
            orientation=self._orientation(
                width,
                height
            ),
            image_format=image_format,
            stability_constraints=(
                "preserve_source_composition",
                "preserve_source_geometry",
                "avoid_identity_or_subject_changes",
            )
        )

    def _read_image_metadata(
        self,
        path
    ):
        with path.open(
            "rb"
        ) as image_file:
            header = image_file.read(
                32
            )

        if header.startswith(
            PNG_SIGNATURE
        ):
            return self._read_png_metadata(
                header
            )

        raise SourceImageAnalysisError(
            "Unsupported or invalid source image. "
            "Block 1 currently supports PNG source images."
        )

    def _read_png_metadata(
        self,
        header
    ):
        if len(
            header
        ) < 24:
            raise SourceImageAnalysisError(
                "Invalid PNG source image."
            )

        chunk_type = header[
            12:16
        ]

        if chunk_type != b"IHDR":
            raise SourceImageAnalysisError(
                "Invalid PNG source image."
            )

        width, height = struct.unpack(
            ">II",
            header[16:24]
        )

        if width <= 0 or height <= 0:
            raise SourceImageAnalysisError(
                "Invalid PNG dimensions."
            )

        return width, height, "PNG"

    def _aspect_ratio(
        self,
        width,
        height
    ):
        divisor = gcd(
            width,
            height
        )

        return (
            f"{width // divisor}:"
            f"{height // divisor}"
        )

    def _orientation(
        self,
        width,
        height
    ):
        if width > height:
            return "landscape"

        if height > width:
            return "portrait"

        return "square"
