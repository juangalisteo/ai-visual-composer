class StoryboardComposer:

    def compose(
        self,
        base_scenes,
        visual_scenes,
        scene_duration
    ):
        visual_truth_by_scene = {
            item["scene"]: item
            for item in visual_scenes
        }

        final_scenes = []

        for base_scene in base_scenes:
            scene_number = (
                base_scene["scene"]
            )

            if scene_number not in visual_truth_by_scene:
                raise ValueError(
                    f"Falta Visual Truth "
                    f"de la escena {scene_number}."
                )

            visual_truth = visual_truth_by_scene[
                scene_number
            ]

            final_scenes.append({
                "scene": scene_number,
                "text": base_scene["text"],
                "duration": round(
                    scene_duration,
                    3
                ),
                "visible_subject": visual_truth["visible_subject"],
                "visible_action": visual_truth["visible_action"],
                "visible_environment": (
                    visual_truth["visible_environment"]
                ),
                "time_context": visual_truth["time_context"],
                "key_objects": visual_truth["key_objects"],
                "spatial_relationships": (
                    visual_truth["spatial_relationships"]
                ),
                "continuity_links": visual_truth["continuity_links"],
                "abstract_source": visual_truth["abstract_source"],
                "filmable_interpretation": (
                    visual_truth["filmable_interpretation"]
                ),
                "visual_constraints": visual_truth["visual_constraints"],
                "visual_truth_status": visual_truth["visual_truth_status"],
                "visual_idea": visual_truth["visual_idea"]
            })

        return final_scenes
