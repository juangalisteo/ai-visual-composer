from pathlib import Path

from app.modules.images.image_design_models import PreparedImageDesign
from app.modules.visual_design import VisualDesignInterpreter


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
            raise FileNotFoundError(
                "No existe el diseño visual manual: "
                f"{design_path}"
            )

        text = design_path.read_text(
            encoding="utf-8"
        ).strip()

        if not text:
            raise ValueError(
                "El diseño visual manual está vacío."
            )

        return PreparedImageDesign(
            text=text,
            source_path=design_path,
            visual_truth=self.visual_interpreter.interpret(
                text
            )
        )
