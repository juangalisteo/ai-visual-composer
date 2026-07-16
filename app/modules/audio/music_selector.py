import random
from pathlib import Path

from app.shared.progress_logger import ProgressLogger


class MusicSelector:

    SUPPORTED_EXTENSIONS = {
        ".mp3",
        ".wav",
        ".m4a",
        ".aac",
        ".flac"
    }

    def __init__(
        self,
        music_path="assets/music"
    ):
        self.music_path = Path(
            music_path
        )

    def get_categories(
        self
    ):
        if not self.music_path.exists():
            raise FileNotFoundError(
                "No existe la carpeta de música: "
                f"{self.music_path}"
            )

        categories = [
            folder.name
            for folder in self.music_path.iterdir()
            if folder.is_dir()
        ]

        return sorted(
            categories
        )

    def select(
        self,
        category
    ):
        if not category:
            return None

        normalized_category = (
            category.strip()
        )

        if normalized_category.lower() in {
            "none",
            "sin_musica",
            "sin música"
        }:
            return None

        category_path = (
            self.music_path
            / normalized_category
        )

        if not category_path.exists():
            raise FileNotFoundError(
                "No existe la categoría musical: "
                f"{category_path}"
            )

        if not category_path.is_dir():
            raise NotADirectoryError(
                "La categoría musical no es una carpeta: "
                f"{category_path}"
            )

        tracks = [
            file
            for file in category_path.iterdir()
            if (
                file.is_file()
                and file.suffix.lower()
                in self.SUPPORTED_EXTENSIONS
            )
        ]

        if not tracks:
            raise FileNotFoundError(
                "No se encontraron pistas musicales en: "
                f"{category_path}"
            )

        selected_track = random.choice(
            tracks
        )

        ProgressLogger.info(
            "Música seleccionada: "
            f"{normalized_category} / "
            f"{selected_track.name}"
        )

        return selected_track