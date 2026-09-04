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

        return self.load_render_style(
            video_style.get(
                "subtitles",
                {}
            )
        )

    def load_render_style(
        self,
        render_style
    ):
        if not isinstance(
            render_style,
            dict
        ):
            raise TypeError(
                "render_style debe ser un diccionario."
            )

        return SubtitleConfig(

            font=render_style.get(
                "font",
                "Arial"
            ),

            font_size=int(
                render_style.get(
                    "font_size",
                    20
                )
            ),

            bold=bool(
                render_style.get(
                    "bold",
                    True
                )
            ),

            primary_colour=render_style.get(
                "primary_colour",
                "&H00FFFFFF"
            ),

            outline_colour=render_style.get(
                "outline_colour",
                "&H00000000"
            ),

            back_colour=render_style.get(
                "back_colour",
                "&H00000000"
            ),

            border_style=int(
                render_style.get(
                    "border_style",
                    1
                )
            ),

            outline=int(
                render_style.get(
                    "outline",
                    0
                )
            ),

            shadow=int(
                render_style.get(
                    "shadow",
                    1
                )
            ),

            alignment=int(
                render_style.get(
                    "alignment",
                    2
                )
            ),

            margin_v=int(
                render_style.get(
                    "margin_v",
                    25
                )
            ),

            offset=float(
                render_style.get(
                    "offset",
                    0.0
                )
            )
        )
