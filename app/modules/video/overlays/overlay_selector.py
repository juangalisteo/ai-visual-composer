from app.modules.video.assets.asset_selector import (
    AssetSelector
)


class OverlaySelector(
    AssetSelector
):

    def __init__(
        self,
        config
    ):
        super().__init__(
            config=config,
            missing_directory_message=(
                "No existe la carpeta de overlays: "
            ),
            invalid_directory_message=(
                "La ruta de overlays no es "
                "una carpeta: "
            ),
            invalid_scene_count_message=(
                "El numero de escenas debe ser "
                "superior a cero."
            ),
            invalid_scene_index_message=(
                "El indice de escena no puede ser "
                "negativo."
            )
        )

    @property
    def previous_overlay(
        self
    ):
        return self.previous_asset

    @previous_overlay.setter
    def previous_overlay(
        self,
        value
    ):
        self.previous_asset = value

    def _load_overlays(
        self,
        root_directory,
        folder
    ):
        return self._load_assets(
            root_directory=root_directory,
            folder=folder
        )

    def _remove_previous_overlay(
        self,
        candidates_by_folder
    ):
        return self._remove_previous_asset(
            candidates_by_folder
        )
