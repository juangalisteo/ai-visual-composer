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
            narrative_role=StoryboardSceneAdapter._clean(
                scene.get(
                    "narrative_role",
                    ""
                )
            ),
            narrative_moment=StoryboardSceneAdapter._clean(
                scene.get(
                    "narrative_moment",
                    ""
                )
            ),
            subject=StoryboardSceneAdapter._clean(
                scene.get(
                    "subject",
                    ""
                )
            ),
            action=StoryboardSceneAdapter._clean(
                scene.get(
                    "action",
                    ""
                )
            ),
            setting=StoryboardSceneAdapter._clean(
                scene.get(
                    "setting",
                    ""
                )
            ),
            duration=duration,
            source_index=default_scene_number,
            notes=StoryboardSceneAdapter._clean(
                scene.get(
                    "notes",
                    ""
                )
            ),
            visible_subject=StoryboardSceneAdapter._clean(
                scene.get(
                    "visible_subject",
                    ""
                )
            ),
            visible_action=StoryboardSceneAdapter._clean(
                scene.get(
                    "visible_action",
                    ""
                )
            ),
            time_context=StoryboardSceneAdapter._clean(
                scene.get(
                    "time_context",
                    ""
                )
            ),
            key_objects=StoryboardSceneAdapter._clean_sequence(
                scene.get(
                    "key_objects",
                    ()
                )
            ),
            spatial_relationships=StoryboardSceneAdapter._clean_sequence(
                scene.get(
                    "spatial_relationships",
                    ()
                )
            ),
            continuity_links=StoryboardSceneAdapter._clean_sequence(
                scene.get(
                    "continuity_links",
                    ()
                )
            ),
            abstract_source=StoryboardSceneAdapter._clean(
                scene.get(
                    "abstract_source",
                    ""
                )
            ),
            filmable_interpretation=StoryboardSceneAdapter._clean(
                scene.get(
                    "filmable_interpretation",
                    ""
                )
            ),
            visual_constraints=StoryboardSceneAdapter._clean_sequence(
                scene.get(
                    "visual_constraints",
                    ()
                )
            ),
            visual_truth_status=(
                StoryboardSceneAdapter._clean(
                    scene.get(
                        "visual_truth_status",
                        ""
                    )
                )
                or "legacy"
            )
        )

    @staticmethod
    def visual_idea(
        scene
    ) -> str:
        return StoryboardSceneAdapter._clean(
            scene.get(
                "visual_idea",
                ""
            )
        )

    @staticmethod
    def _clean(
        value
    ) -> str:
        if value is None:
            return ""
        return str(
            value
        ).strip()

    @staticmethod
    def _clean_sequence(
        value
    ) -> tuple[str, ...]:
        if value is None:
            return ()

        if isinstance(
            value,
            str
        ):
            values = (
                value,
            )
        else:
            try:
                values = tuple(
                    value
                )
            except TypeError:
                values = (
                    value,
                )

        return tuple(
            item
            for item in (
                StoryboardSceneAdapter._clean(
                    entry
                )
                for entry in values
            )
            if item
        )
