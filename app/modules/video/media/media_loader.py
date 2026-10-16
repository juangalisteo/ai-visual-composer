from dataclasses import dataclass
from pathlib import Path
import json


@dataclass(frozen=True)
class VideoMedia:
    audio_path: Path
    subtitle_path: Path | None
    images_manifest_path: Path
    output_path: Path
    image_paths: tuple[Path, ...]
    media_types: tuple[str, ...] = ()
    media_durations: tuple[float | None, ...] = ()
    scene_metadata: tuple[dict, ...] = ()


class MediaLoader:

    def load(
        self,
        audio_path,
        subtitle_path,
        images_manifest_path,
        output_path,
        media_manifest_type="images",
        storyboard_path=None,
        render_subtitles=True,
    ):
        audio_path = Path(
            audio_path
        )

        subtitle_path = (
            Path(subtitle_path)
            if subtitle_path is not None
            else None
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
            images_manifest_path=images_manifest_path,
            render_subtitles=render_subtitles,
        )

        if media_manifest_type == "video_clips":
            clip_entries = self._load_video_clip_entries(
                images_manifest_path
            )
            image_paths = tuple(
                clip_path
                for _, clip_path, _ in clip_entries
            )
            media_durations = tuple(
                duration
                for _, _, duration in clip_entries
            )
            media_types = tuple(
                "video"
                for _ in image_paths
            )
            scene_metadata = self._load_scene_metadata(
                storyboard_path=storyboard_path,
                image_entries=tuple(
                    (scene_number, clip_path)
                    for scene_number, clip_path, _ in clip_entries
                )
            )
        else:
            image_entries = self._load_image_entries(
                images_manifest_path
            )
            image_paths = tuple(
                image_path
                for _, image_path in image_entries
            )
            media_durations = tuple(
                None
                for _ in image_paths
            )
            media_types = tuple(
                "image"
                for _ in image_paths
            )
            scene_metadata = self._load_scene_metadata(
                storyboard_path=storyboard_path,
                image_entries=image_entries
            )

        return VideoMedia(
            audio_path=audio_path,
            subtitle_path=subtitle_path,
            images_manifest_path=images_manifest_path,
            output_path=output_path,
            image_paths=tuple(
                image_paths
            ),
            media_types=media_types,
            media_durations=media_durations,
            scene_metadata=scene_metadata
        )

    def _validate_input_files(
        self,
        audio_path,
        subtitle_path,
        images_manifest_path,
        render_subtitles,
    ):
        if not audio_path.exists():
            raise FileNotFoundError(
                f"No existe el audio: "
                f"{audio_path}"
            )

        if render_subtitles and subtitle_path is None:
            raise ValueError(
                "La renderizacion con subtitulos requiere subtitle_path."
            )

        if subtitle_path is not None and not subtitle_path.exists():
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

    def _load_image_entries(
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

        image_entries = []

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
                image_entries.append(
                    (
                        self._scene_number(
                            item
                        ),
                        image_path
                    )
                )

        if not image_entries:
            raise FileNotFoundError(
                "No se encontraron imágenes válidas "
                "para montar el vídeo."
            )

        return image_entries

    def _load_scene_metadata(
        self,
        storyboard_path,
        image_entries
    ):
        scenes = self._load_storyboard_scenes(
            storyboard_path
        )

        return tuple(
            scenes.get(
                scene_number,
                {}
            )
            for scene_number, _ in image_entries
        )

    def _load_storyboard_scenes(
        self,
        storyboard_path
    ):
        if storyboard_path is None:
            return {}

        storyboard_path = Path(
            storyboard_path
        )

        if not storyboard_path.exists():
            return {}

        try:
            data = json.loads(
                storyboard_path.read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            json.JSONDecodeError
        ):
            return {}

        if not isinstance(
            data,
            list
        ):
            return {}

        fields = (
            "visible_subject",
            "visible_action",
            "visible_environment",
            "key_objects",
            "visual_constraints"
        )
        scenes = {}

        for item in data:
            if not isinstance(
                item,
                dict
            ):
                continue

            scene_number = self._scene_number(
                item
            )

            if scene_number is None:
                continue

            scenes[scene_number] = {
                field_name: item.get(
                    field_name
                )
                for field_name in fields
                if field_name in item
            }

        return scenes

    def _scene_number(
        self,
        item
    ):
        try:
            return int(
                item.get(
                    "scene"
                )
            )
        except (
            AttributeError,
            TypeError,
            ValueError
        ):
            return None

    def _load_video_clip_entries(
        self,
        video_clips_manifest_path
    ):
        try:
            clips_data = json.loads(
                video_clips_manifest_path.read_text(
                    encoding="utf-8"
                )
            )

        except json.JSONDecodeError as error:
            raise ValueError(
                "No se pudo interpretar el manifiesto "
                "de clips de vídeo."
            ) from error

        if not isinstance(
            clips_data,
            list
        ):
            raise ValueError(
                "El manifiesto de clips de vídeo "
                "debe contener una lista."
            )

        entries = []
        seen_scenes = set()

        for item in clips_data:
            if not isinstance(
                item,
                dict
            ):
                raise ValueError(
                        "Cada clip de vídeo debe declararse "
                    "como un diccionario."
                )

            try:
                scene_number = int(
                    item[
                        "scene"
                    ]
                )
            except (
                KeyError,
                TypeError,
                ValueError
            ) as error:
                raise ValueError(
                    "Cada clip de vídeo debe declarar "
                    "un scene válido."
                ) from error

            if scene_number in seen_scenes:
                raise ValueError(
                    "El manifiesto de clips de vídeo "
                    f"contiene la escena duplicada {scene_number}."
                )

            seen_scenes.add(
                scene_number
            )

            clip_value = item.get(
                "output_clip"
            )

            if not clip_value:
                raise ValueError(
                    "Cada clip de vídeo debe declarar output_clip."
                )

            clip_path = Path(
                clip_value
            )

            if not clip_path.exists():
                raise FileNotFoundError(
                    "No existe el clip de vídeo "
                    f"de la escena {scene_number}: "
                    f"{clip_path}"
                )

            entries.append(
                (
                    scene_number,
                    clip_path,
                    self._clip_duration(
                        item
                    )
                )
            )

        if not entries:
            raise FileNotFoundError(
                "No se encontraron clips de vídeo válidos "
                "para montar el vídeo final."
            )

        return sorted(
                entries,
                key=lambda entry: entry[0]
        )

    def _clip_duration(
        self,
        item
    ):
        duration = item.get(
            "duration_seconds"
        )

        if duration is None:
            return None

        try:
            duration = float(
                duration
            )
        except (
            TypeError,
            ValueError
        ):
            return None

        if duration <= 0:
            return None

        return duration
