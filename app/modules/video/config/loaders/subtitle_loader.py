from app.modules.video.config.subtitle_config import (
    SubtitleConfig
)
from app.shared.config_contract import (
    require_bool,
    require_float,
    require_int,
    require_text,
)


class SubtitleConfigLoader:

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

            font=require_text(
                render_style,
                "font",
                "render_style.font"
            ),

            font_size=require_int(
                render_style,
                "font_size",
                "render_style.font_size"
            ),

            bold=require_bool(
                render_style,
                "bold",
                "render_style.bold"
            ),

            primary_colour=require_text(
                render_style,
                "primary_colour",
                "render_style.primary_colour"
            ),

            outline_colour=require_text(
                render_style,
                "outline_colour",
                "render_style.outline_colour"
            ),

            back_colour=require_text(
                render_style,
                "back_colour",
                "render_style.back_colour"
            ),

            border_style=require_int(
                render_style,
                "border_style",
                "render_style.border_style"
            ),

            outline=require_int(
                render_style,
                "outline",
                "render_style.outline"
            ),

            shadow=require_int(
                render_style,
                "shadow",
                "render_style.shadow"
            ),

            alignment=require_int(
                render_style,
                "alignment",
                "render_style.alignment"
            ),

            margin_v=require_int(
                render_style,
                "margin_v",
                "render_style.margin_v"
            ),

            offset=require_float(
                render_style,
                "offset",
                "render_style.offset"
            )
        )
