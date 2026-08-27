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

        if normalized_category.lower() == "random":
            return self._select_random_track()

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

        tracks = self._valid_tracks(
            category_path
        )

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

    def _select_random_track(
        self
    ):
        if not self.music_path.exists():
            raise FileNotFoundError(
                "No existe la carpeta de música: "
                f"{self.music_path}"
            )

        valid_categories = []

        for category_path in sorted(
            self.music_path.iterdir()
        ):
            if not category_path.is_dir():
                continue

            tracks = self._valid_tracks(
                category_path
            )

            if tracks:
                valid_categories.append(
                    (
                        category_path,
                        tracks
                    )
                )

        if not valid_categories:
            raise FileNotFoundError(
                "No se encontraron pistas musicales "
                f"válidas en: {self.music_path}"
            )

        selected_category, tracks = random.choice(
            valid_categories
        )
        selected_track = random.choice(
            tracks
        )

        ProgressLogger.info(
            "Música seleccionada: "
            f"{selected_category.name} / "
            f"{selected_track.name}"
        )

        return selected_track

    def _valid_tracks(
        self,
        category_path
    ):
        return [
            file
            for file in sorted(
                category_path.iterdir()
            )
            if (
                file.is_file()
                and not file.name.startswith(".")
                and not file.name.startswith("~")
                and not file.name.endswith(".tmp")
                and file.suffix.lower()
                in self.SUPPORTED_EXTENSIONS
            )
        ]
