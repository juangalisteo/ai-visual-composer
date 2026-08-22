from pathlib import Path

from app.modules.images.image_design_models import PreparedImageDesign


class ImageDesignPreparationService:

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
                "No existe el diseno visual manual: "
                f"{design_path}"
            )

        text = design_path.read_text(
            encoding="utf-8"
        ).strip()

        if not text:
            raise ValueError(
                "El diseno visual manual esta vacio."
            )

        return PreparedImageDesign(
            text=text,
            source_path=design_path
        )
