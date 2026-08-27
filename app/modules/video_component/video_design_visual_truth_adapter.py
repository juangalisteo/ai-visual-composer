from app.modules.video_component.video_design_models import (
    PreparedVideoDesign,
)


class VideoDesignVisualTruthAdapter:

    def adapt(
        self,
        prepared_design: PreparedVideoDesign
    ) -> list[dict]:
        if prepared_design.expected_clips != 1:
            raise ValueError(
                "El diseño visual de vídeo debe generar "
                "exactamente un clip."
            )

        text = prepared_design.text.strip()

        if not text:
            raise ValueError(
                "El diseño visual de vídeo está vacío."
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
            "single video clip",
            "manual visual video design",
            "preserve subject identity",
            "subtle contextual motion",
            "stable image-to-video composition",
        )
        visual_truth["visual_truth_status"] = (
            visual_truth.get(
                "visual_truth_status",
                ""
            )
            or "manual_video_design_interpreted"
        )

        return [
            visual_truth
        ]
