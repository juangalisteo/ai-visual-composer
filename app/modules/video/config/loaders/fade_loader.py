from app.modules.video.config.fade_config import (
    FadeConfig
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

        video_style = profile.get(
            "video_style",
            {}
        )

        fade_data = video_style.get(
            "fade",
            {}
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

        enabled = bool(
            fade_data.get(
                "enabled",
                True
            )
        )

        fade_in = bool(
            fade_data.get(
                "fade_in",
                False
            )
        )

        fade_out = bool(
            fade_data.get(
                "fade_out",
                True
            )
        )

        duration = float(
            fade_data.get(
                "duration",
                0.50
            )
        )

        return FadeConfig(
            enabled=enabled,
            fade_in=fade_in,
            fade_out=fade_out,
            duration=duration
        )