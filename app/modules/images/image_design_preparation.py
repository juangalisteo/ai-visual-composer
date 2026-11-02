from pathlib import Path

from app.modules.images.image_design_models import PreparedImageDesign
from app.modules.visual_design import VisualDesignInterpreter
from app.shared.operational_error import create_operational_error


class ImageDesignPreparationService:

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
    ) -> PreparedImageDesign:
        design_path = Path(
            input_path
            or "input/guion_imagen.txt"
        )

        if not design_path.exists():
            raise create_operational_error(
                family="FILESYSTEM",
                user_message=(
                    "No existe el diseño visual manual: "
                    f"{design_path.as_posix()}."
                ),
                recommended_action=(
                    f"Crea {design_path.as_posix()} con el diseño de la imagen "
                    "y vuelve a intentarlo."
                ),
                operation="Preparar el diseño de imagen",
            )

        text = design_path.read_text(
            encoding="utf-8"
        ).strip()

        if not text:
            raise create_operational_error(
                family="VALIDATION",
                user_message=(
                    "El diseño visual manual está vacío: "
                    f"{design_path.as_posix()}."
                ),
                recommended_action=(
                    f"Escribe el diseño de la imagen en {design_path.as_posix()} "
                    "y vuelve a intentarlo."
                ),
                operation="Preparar el diseño de imagen",
            )

        return PreparedImageDesign(
            text=text,
            source_path=design_path,
            visual_truth=self.visual_interpreter.interpret(
                text
            )
        )
