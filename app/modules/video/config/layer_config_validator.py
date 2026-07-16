class LayerConfigValidator:

    allowed_selection_modes = {
        "sequence",
        "random"
    }

    allowed_repeat_modes = {
        "full_video",
        "interval",
        "scene"
    }

    allowed_blend_modes = {
        "normal",
        "screen",
        "add",
        "overlay",
        "lighten"
    }

    def validate(
        self,
        config,
        min_seconds_message,
        max_seconds_message,
        max_less_than_min_message
    ):
        if (
            config.folder_selection
            not in self.allowed_selection_modes
        ):
            raise ValueError(
                "La selecciÃ³n de carpetas debe ser "
                "'sequence' o 'random'."
            )

        if (
            config.file_selection
            not in self.allowed_selection_modes
        ):
            raise ValueError(
                "La selecciÃ³n de archivos debe ser "
                "'sequence' o 'random'."
            )

        if (
            config.repeat_mode
            not in self.allowed_repeat_modes
        ):
            raise ValueError(
                "El modo de repeticiÃ³n debe ser "
                "'full_video', 'interval' o 'scene'."
            )

        if (
            config.blend_mode
            not in self.allowed_blend_modes
        ):
            raise ValueError(
                "El modo de mezcla no es vÃ¡lido."
            )

        if config.min_seconds <= 0:
            raise ValueError(
                min_seconds_message
            )

        if config.max_seconds <= 0:
            raise ValueError(
                max_seconds_message
            )

        if (
            config.max_seconds
            < config.min_seconds
        ):
            raise ValueError(
                max_less_than_min_message
            )

        if not (
            0.0
            <= config.opacity
            <= 1.0
        ):
            raise ValueError(
                "La opacidad debe estar "
                "entre 0 y 1."
            )

        if not (
            0.0
            <= config.probability
            <= 1.0
        ):
            raise ValueError(
                "La probabilidad debe estar "
                "entre 0 y 1."
            )

        if not config.extensions:
            raise ValueError(
                "Debe existir al menos "
                "una extensiÃ³n permitida."
            )

        for extension in config.extensions:
            if not extension.startswith(
                "."
            ):
                raise ValueError(
                    "Las extensiones deben comenzar "
                    "por un punto."
                )

        if not isinstance(
            config.folder_weights,
            dict
        ):
            raise TypeError(
                "Los pesos de las carpetas deben "
                "ser un diccionario."
            )

        if not isinstance(
            config.file_weights,
            dict
        ):
            raise TypeError(
                "Los pesos de los archivos deben "
                "ser un diccionario."
            )

        for weight in (
            config.folder_weights.values()
        ):
            if float(weight) <= 0:
                raise ValueError(
                    "El peso de cada carpeta "
                    "debe ser superior a cero."
                )

        for weight in (
            config.file_weights.values()
        ):
            if float(weight) <= 0:
                raise ValueError(
                    "El peso de cada archivo "
                    "debe ser superior a cero."
                )
