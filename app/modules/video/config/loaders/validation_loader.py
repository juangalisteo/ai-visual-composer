from app.modules.video.config.validation_config import (
    ValidationConfig
)


class ValidationConfigLoader:

    def load(
        self,
        profile
    ):
        if not isinstance(
            profile,
            dict
        ):
            raise TypeError(
                "El perfil debe ser un diccionario."
            )

        validation_data = profile.get(
            "validation",
            {}
        )

        if not isinstance(
            validation_data,
            dict
        ):
            raise TypeError(
                "La configuración validation "
                "debe ser un diccionario."
            )

        max_duration_difference = float(
            validation_data.get(
                "max_duration_difference",
                0.20
            )
        )

        return ValidationConfig(
            max_duration_difference=max_duration_difference
        )