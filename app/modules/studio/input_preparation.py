from dataclasses import dataclass
from pathlib import Path
import re

@dataclass(frozen=True)
class PreparedStudioInput:
    video_path: Path
    subtitle_path: Path


class StudioInputPreparationService:

    def __init__(
        self,
        input_directory=Path("input/studio")
    ):
        self.input_directory = Path(input_directory)

    def prepare(self, profile):
        directory = self._require_directory()
        video_path = self._single_candidate(
            directory=directory,
            extensions=profile.video_extensions,
            label="MP4"
        )
        subtitle_path = self._single_candidate(
            directory=directory,
            extensions=profile.subtitle_extensions,
            label="SRT"
        )
        self._validate_subtitle(subtitle_path)
        return PreparedStudioInput(
            video_path=video_path,
            subtitle_path=subtitle_path
        )

    def _require_directory(self):
        if not self.input_directory.exists():
            raise FileNotFoundError(
                "No existe la carpeta de entrada STUDIO: "
                f"{self.input_directory}"
            )
        if not self.input_directory.is_dir():
            raise NotADirectoryError(
                "La entrada STUDIO debe ser una carpeta: "
                f"{self.input_directory}"
            )
        return self.input_directory

    def _single_candidate(
        self,
        directory,
        extensions,
        label
    ):
        candidates = tuple(
            sorted(
                (
                    path
                    for path in directory.iterdir()
                    if (
                        path.is_file()
                        and path.suffix.lower() in extensions
                    )
                ),
                key=lambda path: path.name.lower()
            )
        )
        if not candidates:
            raise FileNotFoundError(
                f"No se encontro ningun archivo {label} "
                "en input/studio/."
            )
        if len(candidates) > 1:
            names = ", ".join(path.name for path in candidates)
            raise ValueError(
                f"Entrada STUDIO ambigua: se encontraron varios "
                f"archivos {label}: {names}."
            )
        return candidates[0]

    def _validate_subtitle(self, subtitle_path):
        try:
            content = subtitle_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise ValueError(
                "El archivo SRT de STUDIO debe estar codificado "
                f"en UTF-8: {subtitle_path}."
            ) from error

        if not content.strip():
            raise ValueError(
                "El archivo SRT de STUDIO esta vacio: "
                f"{subtitle_path}."
            )

        blocks = re.split(
            r"\n\s*\n",
            content.replace("\r\n", "\n").strip(),
        )
        if not any(self._is_usable_cue(block) for block in blocks):
            raise ValueError(
                "El archivo SRT de STUDIO no contiene cues utilizables: "
                f"{subtitle_path}."
            )

    def _is_usable_cue(self, block):
        lines = str(block).strip().splitlines()
        if len(lines) < 3 or not lines[0].strip().isdigit():
            return False

        match = re.fullmatch(
            r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*"
            r"(\d{2}):(\d{2}):(\d{2}),(\d{3})",
            lines[1].strip(),
        )
        if not match or not " ".join(lines[2:]).strip():
            return False

        start = self._time_to_milliseconds(match.groups()[:4])
        end = self._time_to_milliseconds(match.groups()[4:])
        return end > start

    @staticmethod
    def _time_to_milliseconds(parts):
        hours, minutes, seconds, milliseconds = (
            int(part)
            for part in parts
        )
        return (
            hours * 3_600_000
            + minutes * 60_000
            + seconds * 1_000
            + milliseconds
        )
