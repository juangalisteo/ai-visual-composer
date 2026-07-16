from dataclasses import dataclass
from pathlib import Path
import json


@dataclass(frozen=True)
class VideoMedia:
    audio_path: Path
    subtitle_path: Path
    images_manifest_path: Path
    output_path: Path
    image_paths: tuple[Path, ...]


class MediaLoader:

    def load(
        self,
        audio_path,
        subtitle_path,
        images_manifest_path,
        output_path
    ):
        audio_path = Path(
            audio_path
        )

        subtitle_path = Path(
            subtitle_path
        )

        images_manifest_path = Path(
            images_manifest_path
        )

        output_path = Path(
            output_path
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        self._validate_input_files(
            audio_path=audio_path,
            subtitle_path=subtitle_path,
            images_manifest_path=images_manifest_path
        )

        image_paths = self._load_image_paths(
            images_manifest_path
        )

        return VideoMedia(
            audio_path=audio_path,
            subtitle_path=subtitle_path,
            images_manifest_path=images_manifest_path,
            output_path=output_path,
            image_paths=tuple(
                image_paths
            )
        )

    def _validate_input_files(
        self,
        audio_path,
        subtitle_path,
        images_manifest_path
    ):
        if not audio_path.exists():
            raise FileNotFoundError(
                f"No existe el audio: "
                f"{audio_path}"
            )

        if not subtitle_path.exists():
            raise FileNotFoundError(
                f"No existen los subtítulos: "
                f"{subtitle_path}"
            )

        if not images_manifest_path.exists():
            raise FileNotFoundError(
                f"No existe el manifiesto "
                f"de imágenes: "
                f"{images_manifest_path}"
            )

    def _load_image_paths(
        self,
        images_manifest_path
    ):
        try:
            images_data = json.loads(
                images_manifest_path.read_text(
                    encoding="utf-8"
                )
            )

        except json.JSONDecodeError as error:
            raise ValueError(
                "No se pudo interpretar el manifiesto "
                "de imágenes."
            ) from error

        if not isinstance(
            images_data,
            list
        ):
            raise ValueError(
                "El manifiesto de imágenes "
                "debe contener una lista."
            )

        image_paths = []

        for item in images_data:
            if not isinstance(
                item,
                dict
            ):
                continue

            image_value = item.get(
                "image"
            )

            if not image_value:
                continue

            image_path = Path(
                image_value
            )

            if image_path.exists():
                image_paths.append(
                    image_path
                )

        if not image_paths:
            raise FileNotFoundError(
                "No se encontraron imágenes válidas "
                "para montar el vídeo."
            )

        return image_paths