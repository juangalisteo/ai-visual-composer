from app.domain import StoryboardScene


class StoryboardSceneAdapter:

    @staticmethod
    def from_dict(
        scene,
        default_scene_number: int
    ) -> StoryboardScene:
        if not isinstance(
            scene,
            dict
        ):
            raise ValueError(
                "Cada escena del storyboard debe ser "
                "un diccionario."
            )

        scene_number = scene.get(
            "scene",
            default_scene_number
        )

        try:
            scene_number = int(
                scene_number
            )
        except (
            TypeError,
            ValueError
        ) as error:
            raise ValueError(
                "El numero de escena no es valido."
            ) from error

        duration = scene.get(
            "duration"
        )

        return StoryboardScene(
            scene_number=scene_number,
            text=str(
                scene.get(
                    "text",
                    ""
                )
            ).strip(),
            duration=duration,
            source_index=default_scene_number
        )

    @staticmethod
    def visual_idea(
        scene
    ) -> str:
        return str(
            scene.get(
                "visual_idea",
                ""
            )
        ).strip()
