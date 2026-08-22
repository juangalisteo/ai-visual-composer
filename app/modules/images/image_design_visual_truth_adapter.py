from app.modules.images.image_design_models import PreparedImageDesign


class ImageDesignVisualTruthAdapter:

    def adapt(
        self,
        prepared_design: PreparedImageDesign
    ) -> list[dict]:
        if prepared_design.expected_images != 1:
            raise ValueError(
                "El diseno visual manual debe generar "
                "exactamente una imagen."
            )

        text = prepared_design.text.strip()

        if not text:
            raise ValueError(
                "El diseno visual manual esta vacio."
            )

        return [
            {
                "scene": 1,
                "text": text,
                "duration": None,
                "narrative_role": "",
                "narrative_moment": "",
                "notes": "",
                "visible_subject": text,
                "visible_action": text,
                "visible_environment": text,
                "time_context": "",
                "key_objects": [],
                "spatial_relationships": [],
                "continuity_links": [],
                "abstract_source": text,
                "filmable_interpretation": text,
                "visual_constraints": [
                    "single image",
                    "manual visual design"
                ],
                "visual_truth_status": "manual_design"
            }
        ]
