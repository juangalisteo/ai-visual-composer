class StoryboardValidator:
    REQUIRED_VISUAL_TRUTH_FIELDS = (
        "visible_subject",
        "visible_action",
        "visible_environment",
        "filmable_interpretation",
    )

    SEQUENCE_FIELDS = (
        "key_objects",
        "spatial_relationships",
        "continuity_links",
        "visual_constraints",
    )

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
                f"Ollama devolvio "
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

            try:
                scene_number = int(
                    item["scene"]
                )

            except (
                TypeError,
                ValueError
            ) as error:
                raise ValueError(
                    "El numero de escena "
                    "no es valido."
                ) from error

            visual_truth = self._validate_visual_truth(
                item=item,
                scene_number=scene_number
            )

            visual_idea = self._clean(
                item.get(
                    "visual_idea",
                    ""
                )
            )

            if not visual_idea:
                visual_idea = visual_truth[
                    "filmable_interpretation"
                ]

            validated_scenes.append({
                "scene": scene_number,
                **visual_truth,
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
                "La numeracion de escenas devuelta "
                "por Ollama no coincide con la esperada."
            )

        return sorted(
            validated_scenes,
            key=lambda item: item["scene"]
        )

    def _validate_visual_truth(
        self,
        item,
        scene_number
    ):
        visual_truth = {}

        for field in self.REQUIRED_VISUAL_TRUTH_FIELDS:
            value = self._clean(
                item.get(
                    field,
                    ""
                )
            )
            if not value:
                raise ValueError(
                    f"La escena {scene_number} "
                    f"no contiene {field}."
                )
            visual_truth[field] = value

        visual_truth["time_context"] = self._clean(
            item.get(
                "time_context",
                ""
            )
        )

        for field in self.SEQUENCE_FIELDS:
            visual_truth[field] = self._clean_sequence(
                item.get(
                    field,
                    ()
                )
            )

        visual_truth["abstract_source"] = self._clean(
            item.get(
                "abstract_source",
                ""
            )
        )

        visual_truth["visual_truth_status"] = (
            self._clean(
                item.get(
                    "visual_truth_status",
                    ""
                )
            )
            or "structured"
        )

        return visual_truth

    def _clean(
        self,
        value
    ):
        if value is None:
            return ""
        return str(
            value
        ).strip()

    def _clean_sequence(
        self,
        value
    ):
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
                self._clean(
                    entry
                )
                for entry in values
            )
            if item
        )
