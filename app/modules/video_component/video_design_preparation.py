from pathlib import Path

from app.modules.video_component.video_design_models import (
    PreparedVideoDesign,
)
from app.modules.visual_design import VisualDesignInterpreter


class VideoDesignPreparationService:

    def __init__(
        self,
        visual_interpreter=None
    ):
        self.visual_interpreter = (
            visual_interpreter
            or VisualDesignInterpreter()
        )

    def prepare(
        self,
        input_path=None
    ) -> PreparedVideoDesign:
        design_path = Path(
            input_path
            or "input/guion_video.txt"
        )

        if not design_path.exists():
            raise FileNotFoundError(
                "No existe el diseño visual de vídeo: "
                f"{design_path}"
            )

        text = design_path.read_text(
            encoding="utf-8"
        ).strip()

        if not text:
            raise ValueError(
                "El diseño visual de vídeo está vacío."
            )

        return PreparedVideoDesign(
            text=text,
            source_path=design_path,
            visual_truth=self.visual_interpreter.interpret(
                text
            )
        )
