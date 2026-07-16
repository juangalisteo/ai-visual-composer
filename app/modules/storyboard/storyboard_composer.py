class StoryboardComposer:

    def compose(
        self,
        base_scenes,
        visual_scenes,
        scene_duration
    ):
        visual_ideas_by_scene = {
            item["scene"]: item["visual_idea"]
            for item in visual_scenes
        }

        final_scenes = []

        for base_scene in base_scenes:
            scene_number = (
                base_scene["scene"]
            )

            if scene_number not in visual_ideas_by_scene:
                raise ValueError(
                    f"Falta la idea visual "
                    f"de la escena {scene_number}."
                )

            final_scenes.append({
                "scene": scene_number,
                "text": base_scene["text"],
                "duration": round(
                    scene_duration,
                    3
                ),
                "visual_idea": (
                    visual_ideas_by_scene[
                        scene_number
                    ]
                )
            })

        return final_scenes