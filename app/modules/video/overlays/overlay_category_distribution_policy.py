import random


class OverlayCategoryDistributionPolicy:

    def __init__(
        self
    ):
        self.previous_category = None

    def select_folder(
        self,
        folders,
        folder_weights
    ):
        available_folders = tuple(
            folders
        )

        if not available_folders:
            return None

        weighted_folders = self._apply_cooldown(
            available_folders
        )

        weights = [
            folder_weights.get(
                folder.name,
                1.0
            )
            for folder in weighted_folders
        ]

        selected_folder = random.choices(
            population=weighted_folders,
            weights=weights,
            k=1
        )[0]

        self.previous_category = (
            selected_folder.name
        )

        return selected_folder

    def reset(
        self
    ):
        self.previous_category = None

    def _apply_cooldown(
        self,
        folders
    ):
        if (
            self.previous_category is None
            or len(folders) <= 1
        ):
            return folders

        cooled_folders = tuple(
            folder
            for folder in folders
            if folder.name != self.previous_category
        )

        return cooled_folders or folders
