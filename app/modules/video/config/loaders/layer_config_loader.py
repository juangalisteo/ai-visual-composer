class LayerConfigLoader:

    def load_section(
        self,
        profile,
        section_name,
        section_error_message
    ):
        if not isinstance(
            profile,
            dict
        ):
            raise TypeError(
                "El perfil debe ser un diccionario."
            )

        video_style = profile.get(
            "video_style",
            {}
        )

        section_data = video_style.get(
            section_name,
            {}
        )

        if not isinstance(
            section_data,
            dict
        ):
            raise TypeError(
                section_error_message
            )

        return section_data

    def load_common(
        self,
        data,
        default_directory,
        use_legacy_selection,
        use_legacy_weights
    ):
        enabled = bool(
            data.get(
                "enabled",
                False
            )
        )

        directory = str(
            data.get(
                "directory",
                default_directory
            )
        ).strip()

        legacy_selection = str(
            data.get(
                "selection",
                "random"
            )
        ).strip().lower()

        default_selection = (
            legacy_selection
            if use_legacy_selection
            else "random"
        )

        folder_selection = str(
            data.get(
                "folder_selection",
                default_selection
            )
        ).strip().lower()

        file_selection = str(
            data.get(
                "file_selection",
                default_selection
            )
        ).strip().lower()

        avoid_repeats = bool(
            data.get(
                "avoid_repeats",
                True
            )
        )

        repeat_mode = str(
            data.get(
                "repeat_mode",
                "interval"
            )
        ).strip().lower()

        min_seconds = float(
            data.get(
                "min_seconds",
                6.0
            )
        )

        max_seconds = float(
            data.get(
                "max_seconds",
                12.0
            )
        )

        loop_file = bool(
            data.get(
                "loop_file",
                True
            )
        )

        opacity = float(
            data.get(
                "opacity",
                0.15
            )
        )

        blend_mode = str(
            data.get(
                "blend_mode",
                "screen"
            )
        ).strip().lower()

        probability = float(
            data.get(
                "probability",
                1.0
            )
        )

        folders = tuple(
            str(item).strip()
            for item in data.get(
                "folders",
                ()
            )
            if str(item).strip()
        )

        types = tuple(
            str(item).strip()
            for item in data.get(
                "types",
                ()
            )
            if str(item).strip()
        )

        extensions = tuple(
            str(item).strip().lower()
            for item in data.get(
                "extensions",
                (
                    ".mov",
                    ".mp4"
                )
            )
            if str(item).strip()
        )

        folder_weights = {
            str(key).strip(): float(value)
            for key, value in data.get(
                "folder_weights",
                {}
            ).items()
        }

        default_file_weights = (
            data.get(
                "weights",
                {}
            )
            if use_legacy_weights
            else {}
        )

        file_weights = {
            str(key).strip(): float(value)
            for key, value in data.get(
                "file_weights",
                default_file_weights
            ).items()
        }

        return {
            "enabled": enabled,
            "directory": directory,
            "folder_selection": folder_selection,
            "file_selection": file_selection,
            "avoid_repeats": avoid_repeats,
            "repeat_mode": repeat_mode,
            "min_seconds": min_seconds,
            "max_seconds": max_seconds,
            "loop_file": loop_file,
            "opacity": opacity,
            "blend_mode": blend_mode,
            "probability": probability,
            "folders": folders,
            "types": types,
            "extensions": extensions,
            "folder_weights": folder_weights,
            "file_weights": file_weights
        }
