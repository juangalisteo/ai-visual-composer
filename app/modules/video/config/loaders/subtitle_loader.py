from app.modules.video.config.subtitle_config import (
    SubtitleConfig
)


class SubtitleConfigLoader:

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

        subtitle_data = video_style.get(
            "subtitles",
            {}
        )

        if not isinstance(
            subtitle_data,
            dict
        ):
            raise TypeError(
                "La configuración "
                "video_style.subtitles "
                "debe ser un diccionario."
            )

        return SubtitleConfig(

            font=subtitle_data.get(
                "font",
                "Arial"
            ),

            font_size=int(
                subtitle_data.get(
                    "font_size",
                    20
                )
            ),

            bold=bool(
                subtitle_data.get(
                    "bold",
                    True
                )
            ),

            primary_colour=subtitle_data.get(
                "primary_colour",
                "&H00FFFFFF"
            ),

            outline_colour=subtitle_data.get(
                "outline_colour",
                "&H00000000"
            ),

            back_colour=subtitle_data.get(
                "back_colour",
                "&H00000000"
            ),

            border_style=int(
                subtitle_data.get(
                    "border_style",
                    1
                )
            ),

            outline=int(
                subtitle_data.get(
                    "outline",
                    0
                )
            ),

            shadow=int(
                subtitle_data.get(
                    "shadow",
                    1
                )
            ),

            alignment=int(
                subtitle_data.get(
                    "alignment",
                    2
                )
            ),

            margin_v=int(
                subtitle_data.get(
                    "margin_v",
                    25
                )
            ),

            offset=float(
                subtitle_data.get(
                    "offset",
                    0.0
                )
            )
        )