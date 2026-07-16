from app.modules.video.assets.asset_selector import (
    AssetSelector
)


class VisualEffectSelector(
    AssetSelector
):

    def __init__(
        self,
        config
    ):
        super().__init__(
            config=config,
            missing_directory_message=(
                "No existe la carpeta de efectos "
                "visuales: "
            ),
            invalid_directory_message=(
                "La ruta de efectos visuales no es "
                "una carpeta: "
            ),
            invalid_scene_count_message=(
                "El número de escenas debe ser "
                "superior a cero."
            ),
            invalid_scene_index_message=(
                "El índice de escena no puede ser "
                "negativo."
            )
        )

    @property
    def previous_effect(
        self
    ):
        return self.previous_asset

    @previous_effect.setter
    def previous_effect(
        self,
        value
    ):
        self.previous_asset = value

    def _load_effects(
        self,
        root_directory,
        folder
    ):
        return self._load_assets(
            root_directory=root_directory,
            folder=folder
        )

    def _remove_previous_effect(
        self,
        candidates_by_folder
    ):
        return self._remove_previous_asset(
            candidates_by_folder
        )
