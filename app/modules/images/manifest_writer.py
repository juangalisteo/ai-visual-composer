import json


class ImageManifestWriter:

    def build_entry(
        self,
        generation_result,
        prompt,
        prompt_metadata,
        image_path
    ):
        return {
            "scene": generation_result.scene_number,
            "prompt": prompt,
            "positive_prompt": (
                prompt_metadata[
                    "positive_prompt"
                ]
            ),
            "negative_prompt": (
                prompt_metadata[
                    "negative_prompt"
                ]
            ),
            "visual_director": (
                prompt_metadata[
                    "visual_director"
                ]
            ),
            "image": str(
                image_path
            ),
            "width": generation_result.width,
            "height": generation_result.height,
            "duration": generation_result.duration
        }

    def write(
        self,
        manifest_path,
        entries
    ):
        manifest_path.write_text(
            json.dumps(
                entries,
                ensure_ascii=False,
                indent=4
            ),
            encoding="utf-8"
        )

        if not manifest_path.exists():
            raise FileNotFoundError(
                "No se encontró el manifiesto "
                "de imágenes esperado: "
                f"{manifest_path}"
            )

        if manifest_path.stat().st_size <= 0:
            raise RuntimeError(
                "El manifiesto de imágenes "
                "está vacío."
            )

        return manifest_path
