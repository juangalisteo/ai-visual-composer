from app.modules.video.assets.asset_selector import (
    AssetSelector
)
from app.modules.video.overlays.overlay_category_distribution_policy import (
    OverlayCategoryDistributionPolicy
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
                "El número de escenas debe ser "
                "superior a cero."
            ),
            invalid_scene_index_message=(
                "El indice de escena no puede ser "
                "negativo."
            )
        )
        self.category_distribution_policy = (
            OverlayCategoryDistributionPolicy()
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

    def _select_folder(
        self,
        folders,
        scene_index
    ):
        if (
            self.config.folder_selection
            == "sequence"
        ):
            return super()._select_folder(
                folders=folders,
                scene_index=scene_index
            )

        return (
            self.category_distribution_policy
            .select_folder(
                folders=folders,
                folder_weights=(
                    self.config.folder_weights
                )
            )
        )

    def reset_category_distribution(
        self
    ):
        self.category_distribution_policy.reset()

    def _remove_previous_overlay(
        self,
        candidates_by_folder
    ):
        return self._remove_previous_asset(
            candidates_by_folder
        )
