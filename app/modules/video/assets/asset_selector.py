from pathlib import Path
import random


class AssetSelector:

    def __init__(
        self,
        config,
        missing_directory_message,
        invalid_directory_message,
        invalid_scene_count_message,
        invalid_scene_index_message
    ):
        self.config = config
        self.previous_asset = None
        self.missing_directory_message = (
            missing_directory_message
        )
        self.invalid_directory_message = (
            invalid_directory_message
        )
        self.invalid_scene_count_message = (
            invalid_scene_count_message
        )
        self.invalid_scene_index_message = (
            invalid_scene_index_message
        )

    def select(
        self,
        scene_index,
        scene_count
    ):
        if scene_count <= 0:
            raise ValueError(
                self.invalid_scene_count_message
            )

        if scene_index < 0:
            raise ValueError(
                self.invalid_scene_index_message
            )

        root_directory = Path(
            self.config.directory
        )

        if not root_directory.exists():
            raise FileNotFoundError(
                self.missing_directory_message
                + f"{root_directory}"
            )

        if not root_directory.is_dir():
            raise NotADirectoryError(
                self.invalid_directory_message
                + f"{root_directory}"
            )

        folders = self._load_folders(
            root_directory
        )

        if not folders:
            return None

        candidates_by_folder = {
            folder: self._load_assets(
                root_directory=root_directory,
                folder=folder
            )
            for folder in folders
        }

        candidates_by_folder = {
            folder: assets
            for folder, assets in (
                candidates_by_folder.items()
            )
            if assets
        }

        if not candidates_by_folder:
            return None

        candidates_by_folder = (
            self._remove_previous_asset(
                candidates_by_folder
            )
        )

        selected_folder = self._select_folder(
            folders=tuple(
                candidates_by_folder.keys()
            ),
            scene_index=scene_index
        )

        available_assets = (
            candidates_by_folder[
                selected_folder
            ]
        )

        selected_asset = self._select_file(
            assets=available_assets,
            scene_index=scene_index
        )

        self.previous_asset = (
            selected_asset
        )

        return selected_asset

    def _load_folders(
        self,
        root_directory
    ):
        if self.config.folders:
            folders = []

            for folder_name in (
                self.config.folders
            ):
                folder_path = (
                    root_directory
                    / folder_name
                )

                if (
                    folder_path.exists()
                    and folder_path.is_dir()
                ):
                    folders.append(
                        folder_path
                    )

            return tuple(
                folders
            )

        folders = tuple(
            sorted(
                (
                    path
                    for path in (
                        root_directory.iterdir()
                    )
                    if path.is_dir()
                ),
                key=lambda path: (
                    path.name.lower()
                )
            )
        )

        if folders:
            return folders

        return (
            root_directory,
        )

    def _load_assets(
        self,
        root_directory,
        folder
    ):
        allowed_extensions = {
            extension.lower()
            for extension in (
                self.config.extensions
            )
        }

        assets = [
            path
            for path in folder.iterdir()
            if (
                path.is_file()
                and path.suffix.lower()
                in allowed_extensions
            )
        ]

        if self.config.types:
            allowed_types = {
                item.lower()
                for item in self.config.types
            }

            assets = [
                path
                for path in assets
                if (
                    path.name.lower()
                    in allowed_types
                    or path.relative_to(
                        root_directory
                    ).as_posix().lower()
                    in allowed_types
                )
            ]

        return tuple(
            sorted(
                assets,
                key=lambda path: (
                    path.name.lower()
                )
            )
        )

    def _remove_previous_asset(
        self,
        candidates_by_folder
    ):
        if (
            not self.config.avoid_repeats
            or self.previous_asset is None
        ):
            return candidates_by_folder

        total_assets = sum(
            len(assets)
            for assets in (
                candidates_by_folder.values()
            )
        )

        if total_assets <= 1:
            return candidates_by_folder

        filtered_candidates = {}

        for folder, assets in (
            candidates_by_folder.items()
        ):
            filtered_assets = tuple(
                asset
                for asset in assets
                if asset
                != self.previous_asset
            )

            if filtered_assets:
                filtered_candidates[
                    folder
                ] = filtered_assets

        return (
            filtered_candidates
            or candidates_by_folder
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
            return folders[
                scene_index
                % len(folders)
            ]

        weights = [
            self.config.folder_weights.get(
                folder.name,
                1.0
            )
            for folder in folders
        ]

        return random.choices(
            population=folders,
            weights=weights,
            k=1
        )[0]

    def _select_file(
        self,
        assets,
        scene_index
    ):
        if (
            self.config.file_selection
            == "sequence"
        ):
            return assets[
                scene_index
                % len(assets)
            ]

        weights = [
            self._get_file_weight(
                asset
            )
            for asset in assets
        ]

        return random.choices(
            population=assets,
            weights=weights,
            k=1
        )[0]

    def _get_file_weight(
        self,
        asset
    ):
        relative_name = (
            f"{asset.parent.name}/"
            f"{asset.name}"
        )

        return self.config.file_weights.get(
            relative_name,
            self.config.file_weights.get(
                asset.name,
                1.0
            )
        )
