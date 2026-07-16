class StoryboardValidator:

    def validate(
        self,
        visual_scenes,
        expected_scene_count
    ):
        if not isinstance(
            visual_scenes,
            list
        ):
            raise ValueError(
                "Las escenas visuales deben "
                "estar contenidas en una lista."
            )

        if len(
            visual_scenes
        ) != expected_scene_count:
            raise ValueError(
                f"Ollama devolvió "
                f"{len(visual_scenes)} escenas, "
                f"pero se esperaban "
                f"{expected_scene_count}."
            )

        validated_scenes = []

        for item in visual_scenes:
            if not isinstance(
                item,
                dict
            ):
                raise ValueError(
                    "Cada escena debe ser "
                    "un objeto JSON."
                )

            if "scene" not in item:
                raise ValueError(
                    "Una escena no contiene "
                    "el campo 'scene'."
                )

            if "visual_idea" not in item:
                raise ValueError(
                    "Una escena no contiene "
                    "el campo 'visual_idea'."
                )

            try:
                scene_number = int(
                    item["scene"]
                )

            except (
                TypeError,
                ValueError
            ) as error:
                raise ValueError(
                    "El número de escena "
                    "no es válido."
                ) from error

            visual_idea = str(
                item["visual_idea"]
            ).strip()

            if not visual_idea:
                raise ValueError(
                    f"La escena {scene_number} "
                    f"no contiene una idea visual."
                )

            validated_scenes.append({
                "scene": scene_number,
                "visual_idea": visual_idea
            })

        expected_numbers = set(
            range(
                1,
                expected_scene_count + 1
            )
        )

        received_numbers = {
            item["scene"]
            for item in validated_scenes
        }

        if received_numbers != expected_numbers:
            raise ValueError(
                "La numeración de escenas devuelta "
                "por Ollama no coincide con la esperada."
            )

        return sorted(
            validated_scenes,
            key=lambda item: item["scene"]
        )