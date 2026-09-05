from app.modules.video.config.fade_config import (
    FadeConfig
)
from app.shared.config_contract import (
    require_bool,
    require_float,
    require_mapping,
)


class FadeConfigLoader:

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

        video_style = require_mapping(
            profile,
            "video_style",
            "video_style"
        )

        fade_data = require_mapping(
            video_style,
            "fade",
            "video_style.fade"
        )

        if not isinstance(
            fade_data,
            dict
        ):
            raise TypeError(
                "La configuración "
                "video_style.fade "
                "debe ser un diccionario."
            )

        enabled = require_bool(
            fade_data,
            "enabled",
            "video_style.fade.enabled"
        )

        fade_in = require_bool(
            fade_data,
            "fade_in",
            "video_style.fade.fade_in"
        )

        fade_out = require_bool(
            fade_data,
            "fade_out",
            "video_style.fade.fade_out"
        )

        duration = require_float(
            fade_data,
            "duration",
            "video_style.fade.duration"
        )

        return FadeConfig(
            enabled=enabled,
            fade_in=fade_in,
            fade_out=fade_out,
            duration=duration
        )
