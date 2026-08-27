from app.modules.images.image_design_models import PreparedImageDesign


class ImageDesignVisualTruthAdapter:

    def adapt(
        self,
        prepared_design: PreparedImageDesign
    ) -> list[dict]:
        if prepared_design.expected_images != 1:
            raise ValueError(
                "El diseño visual manual debe generar "
                "exactamente una imagen."
            )

        text = prepared_design.text.strip()

        if not text:
            raise ValueError(
                "El diseño visual manual está vacío."
            )

        visual_truth = dict(
            prepared_design.visual_truth
        )
        visual_truth["scene"] = 1
        visual_truth["text"] = text
        visual_truth["duration"] = None
        visual_truth["narrative_role"] = (
            visual_truth.get(
                "narrative_role",
                ""
            )
        )
        visual_truth["narrative_moment"] = (
            visual_truth.get(
                "narrative_moment",
                ""
            )
        )
        visual_truth["notes"] = (
            visual_truth.get(
                "notes",
                ""
            )
        )
        visual_truth["abstract_source"] = text
        visual_truth["visual_constraints"] = tuple(
            visual_truth.get(
                "visual_constraints",
                ()
            )
        ) + (
            "single image",
            "manual visual design",
        )
        visual_truth["visual_truth_status"] = (
            visual_truth.get(
                "visual_truth_status",
                ""
            )
            or "manual_design_interpreted"
        )

        return [
            visual_truth
        ]
