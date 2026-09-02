import unicodedata

from app.modules.video.assets.asset_selector import (
    AssetSelector
)
from app.modules.video.overlays.overlay_category_distribution_policy import (
    OverlayCategoryDistributionPolicy
)


class OverlaySelector(
    AssetSelector
):

    neutral_folder = "Light Leaks"
    electricity_folder = "Electricity"
    visual_truth_fields = (
        "visible_subject",
        "visible_action",
        "visible_environment",
        "key_objects",
        "visual_constraints"
    )
    electricity_terms = (
        "electric",
        "lightning",
        "thunderbolt",
        "thunderstorm",
        "electrical storm",
        "spark",
        "rayo",
        "relampago",
        "chispa"
    )

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

    def select(
        self,
        scene_index,
        scene_count,
        scene_metadata=None
    ):
        return super().select(
            scene_index=scene_index,
            scene_count=scene_count,
            allowed_folders=self._allowed_folders(
                scene_index=scene_index,
                scene_metadata=scene_metadata
            )
        )

    def _allowed_folders(
        self,
        scene_index,
        scene_metadata
    ):
        if (
            self.neutral_folder
            not in self.config.folders
        ):
            return None

        scene_number = scene_index + 1

        if scene_number % 2:
            return (
                self.neutral_folder,
            )

        if self._has_electricity_evidence(
            scene_metadata
        ):
            return (
                self.electricity_folder,
            )

        return (
            self.neutral_folder,
        )

    def _has_electricity_evidence(
        self,
        scene_metadata
    ):
        if not isinstance(
            scene_metadata,
            dict
        ):
            return False

        values = (
            self._metadata_text(
                scene_metadata.get(
                    field_name
                )
            )
            for field_name in (
                self.visual_truth_fields
            )
        )
        scene_text = " ".join(
            value
            for value in values
            if value
        )
        scene_text = (
            unicodedata.normalize(
                "NFKD",
                scene_text
            )
            .encode(
                "ascii",
                "ignore"
            )
            .decode(
                "ascii"
            )
            .lower()
        )

        return any(
            term in scene_text
            for term in (
                self.electricity_terms
            )
        )

    def _metadata_text(
        self,
        value
    ):
        if isinstance(
            value,
            (tuple, list)
        ):
            return " ".join(
                self._metadata_text(
                    item
                )
                for item in value
            )

        return str(
            value or ""
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
