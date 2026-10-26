from dataclasses import dataclass
from pathlib import Path

from app.modules.video.intro_outro import IntroOutroPlan


class StudioIntroOutroInputError(ValueError):
    """Expected user-facing error while selecting a STUDIO source video."""


@dataclass(frozen=True)
class StudioIntroOutroPlan:
    source_path: Path
    intro_outro_plan: IntroOutroPlan

    def __post_init__(self):
        source_path = Path(self.source_path)
        if not source_path.is_file():
            raise StudioIntroOutroInputError(
                f"No existe el video para INTRO / OUTRO: {source_path}."
            )
        if not isinstance(self.intro_outro_plan, IntroOutroPlan):
            raise TypeError("INTRO / OUTRO requiere un plan común válido.")
        object.__setattr__(self, "source_path", source_path)


class StudioIntroOutroInputService:

    def __init__(
        self,
        input_directory=Path("input/studio/intro_outro"),
        video_extensions=(".mp4",),
    ):
        self.input_directory = Path(input_directory)
        self.video_extensions = tuple(
            str(extension).lower()
            for extension in video_extensions
        )

    def create_plan(self, intro_outro_plan, source_path=None):
        source_path = (
            self.discover_source()
            if source_path is None
            else Path(source_path)
        )
        return StudioIntroOutroPlan(source_path, intro_outro_plan)

    def discover_source(self):
        candidates = self.discover_sources()
        if len(candidates) > 1:
            names = ", ".join(path.name for path in candidates)
            raise StudioIntroOutroInputError(
                "INTRO / OUTRO requiere exactamente un archivo MP4. "
                f"Se encontraron: {names}."
            )
        return candidates[0]

    def discover_sources(self):
        directory = self.input_directory
        if not directory.exists():
            raise StudioIntroOutroInputError(
                "No existe la carpeta de entrada para INTRO / OUTRO: "
                f"{directory}."
            )
        if not directory.is_dir():
            raise StudioIntroOutroInputError(
                "La entrada de INTRO / OUTRO debe ser una carpeta: "
                f"{directory}."
            )
        candidates = tuple(sorted(
            (
                path
                for path in directory.iterdir()
                if path.is_file()
                and path.suffix.lower() in self.video_extensions
            ),
            key=lambda path: path.name.casefold(),
        ))
        if not candidates:
            raise StudioIntroOutroInputError(
                "No se encontró ningún archivo MP4 para INTRO / OUTRO en "
                f"{directory}."
            )
        return candidates
