from pathlib import Path

from app.modules.video_component.video_design_models import (
    PreparedVideoDesign,
)
from app.modules.visual_design import VisualDesignInterpreter
from app.shared.operational_error import create_operational_error


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
            raise create_operational_error(
                family="FILESYSTEM",
                user_message=(
                    "No existe el diseño visual de vídeo: "
                    f"{design_path.as_posix()}."
                ),
                recommended_action=(
                    f"Crea {design_path.as_posix()} con el diseño del clip "
                    "y vuelve a intentarlo."
                ),
                operation="Preparar el diseño de vídeo",
            )

        text = design_path.read_text(
            encoding="utf-8"
        ).strip()

        if not text:
            raise create_operational_error(
                family="VALIDATION",
                user_message=(
                    "El diseño visual de vídeo está vacío: "
                    f"{design_path.as_posix()}."
                ),
                recommended_action=(
                    f"Escribe el diseño del clip en {design_path.as_posix()} "
                    "y vuelve a intentarlo."
                ),
                operation="Preparar el diseño de vídeo",
            )

        return PreparedVideoDesign(
            text=text,
            source_path=design_path,
            visual_truth=self.visual_interpreter.interpret(
                text
            )
        )
