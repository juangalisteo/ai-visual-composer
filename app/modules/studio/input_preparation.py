from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import re


class StudioInputMode(str, Enum):
    SRT_VIDEO = "srt_video"
    VIDEO = "video"
    MONTAJE_VIDEOS = "montaje_videos"
    EXPORTAR_SRT = "exportar_srt"
    INTRO_OUTRO = "intro_outro"
    VIDEO_AUDIO_SRT = "video_audio_srt"

    @property
    def label(self):
        """Visible name of the mode, the same in menu, summaries and errors."""
        return STUDIO_INPUT_MODE_LABELS[self]


STUDIO_INPUT_MODE_LABELS = {
    StudioInputMode.VIDEO: "SOLO VIDEO",
    StudioInputMode.SRT_VIDEO: "SRT + VIDEO",
    StudioInputMode.INTRO_OUTRO: "INTRO / OUTRO",
    StudioInputMode.MONTAJE_VIDEOS: "MONTAJE VÍDEOS",
    StudioInputMode.VIDEO_AUDIO_SRT: "VIDEO + AUDIO | SRT",
    StudioInputMode.EXPORTAR_SRT: "EXPORTAR SRT",
}


def coerce_studio_input_mode(value):
    if isinstance(value, StudioInputMode):
        return value
    try:
        return StudioInputMode(str(value).strip().lower())
    except ValueError as error:
        raise ValueError(
            "Modo de entrada STUDIO no soportado: "
            f"{value}."
        ) from error


@dataclass(frozen=True)
class PreparedStudioInput:
    video_path: Path
    subtitle_path: Path | None
    mode: StudioInputMode


@dataclass(frozen=True)
class StudioInputCandidates:
    directory: Path
    videos: tuple[Path, ...]
    subtitles: tuple[Path, ...]
    mode: StudioInputMode


class StudioInputPreparationService:

    def __init__(
        self,
        input_directory=Path("input/studio")
    ):
        self.input_directory = Path(input_directory)

    def prepare(
        self,
        profile,
        input_mode,
        video_path=None,
        subtitle_path=None,
    ):
        candidates = self.discover(profile, input_mode)
        video_path = self._selected_candidate(
            candidates.videos,
            video_path,
            "MP4",
        )

        if candidates.mode in {
            StudioInputMode.VIDEO,
        }:
            return PreparedStudioInput(
                video_path=video_path,
                subtitle_path=None,
                mode=candidates.mode,
            )

        if candidates.mode is StudioInputMode.MONTAJE_VIDEOS:
            raise ValueError(
                f"{StudioInputMode.MONTAJE_VIDEOS.label} "
                "requiere un plan de clips ordenado."
            )

        subtitle_path = self._selected_candidate(
            candidates.subtitles,
            subtitle_path,
            "SRT",
        )
        return PreparedStudioInput(
            video_path=video_path,
            subtitle_path=subtitle_path,
            mode=candidates.mode,
        )

    def discover(self, profile, input_mode):
        input_mode = coerce_studio_input_mode(input_mode)
        directory = self._require_directory(input_mode)
        videos = self._candidates(
            directory=directory,
            extensions=profile.video_extensions,
        )
        self._require_candidates(videos, "MP4", directory)

        subtitles = ()
        if input_mode is StudioInputMode.SRT_VIDEO:
            subtitles = self._valid_subtitle_candidates(
                directory=directory,
                extensions=profile.subtitle_extensions,
            )
            self._require_candidates(subtitles, "SRT", directory)

        return StudioInputCandidates(
            directory=directory,
            videos=videos,
            subtitles=subtitles,
            mode=input_mode,
        )

    def _require_directory(self, input_mode):
        directory = self.input_directory / input_mode.value
        if not directory.exists():
            raise FileNotFoundError(
                "No existe la carpeta de entrada STUDIO: "
                f"{directory}"
            )
        if not directory.is_dir():
            raise NotADirectoryError(
                "La entrada STUDIO debe ser una carpeta: "
                f"{directory}"
            )
        return directory

    @staticmethod
    def _candidates(
        directory,
        extensions,
    ):
        return tuple(
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

    def _valid_subtitle_candidates(self, directory, extensions):
        candidates = self._candidates(directory, extensions)
        valid = []
        errors = []
        for candidate in candidates:
            try:
                self._validate_subtitle(candidate)
            except ValueError as error:
                errors.append(str(error))
            else:
                valid.append(candidate)

        if candidates and not valid:
            raise ValueError(errors[0])
        return tuple(valid)

    @staticmethod
    def _require_candidates(candidates, label, directory):
        if not candidates:
            raise FileNotFoundError(
                f"No se encontró ningún archivo {label} "
                f"en {directory}."
            )

    def _selected_candidate(self, candidates, selected_path, label):
        if selected_path is not None:
            selected_path = Path(selected_path)
            if selected_path not in candidates:
                raise ValueError(
                    f"La selección STUDIO de {label} no es válida: "
                    f"{selected_path}."
                )
            return selected_path

        if len(candidates) > 1:
            names = ", ".join(path.name for path in candidates)
            raise ValueError(
                f"Entrada STUDIO ambigua: se encontraron varios "
                f"archivos {label}: {names}."
            )
        return candidates[0]

    @staticmethod
    def _validate_subtitle(subtitle_path):
        try:
            content = subtitle_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise ValueError(
                "El archivo SRT de STUDIO debe estar codificado "
                f"en UTF-8: {subtitle_path}."
            ) from error

        if not content.strip():
            raise ValueError(
                "El archivo SRT de STUDIO está vacío: "
                f"{subtitle_path}."
            )

        blocks = re.split(
            r"\n\s*\n",
            content.replace("\r\n", "\n").strip(),
        )
        if not any(
            StudioInputPreparationService._is_usable_cue(block)
            for block in blocks
        ):
            raise ValueError(
                "El archivo SRT de STUDIO no contiene cues utilizables: "
                f"{subtitle_path}."
            )

    @staticmethod
    def _is_usable_cue(block):
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

        start = StudioInputPreparationService._time_to_milliseconds(
            match.groups()[:4]
        )
        end = StudioInputPreparationService._time_to_milliseconds(
            match.groups()[4:]
        )
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
