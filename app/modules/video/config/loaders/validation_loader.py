from app.modules.video.config.validation_config import (
    ValidationConfig
)
from app.shared.config_contract import (
    require_float,
    require_mapping,
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

        validation_data = require_mapping(
            profile,
            "validation",
            "validation"
        )

        if not isinstance(
            validation_data,
            dict
        ):
            raise TypeError(
                "La configuración validation "
                "debe ser un diccionario."
            )

        max_duration_difference = require_float(
            validation_data,
            "max_duration_difference",
            "validation.max_duration_difference"
        )

        return ValidationConfig(
            max_duration_difference=max_duration_difference
        )
