import math
import re

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

    ASS_COLOUR_PATTERN = re.compile(
        r"&H[0-9A-Fa-f]{8}"
    )
    SUPPORTED_BORDER_STYLES = (1, 3)

    def load_render_style(
        self,
        render_style,
        profile_path=None,
    ):
        if not isinstance(
            render_style,
            dict
        ):
            raise TypeError(
                "render_style debe ser un diccionario."
            )

        subtitle_config = SubtitleConfig(

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
            ),

            italic=self._optional_bool(
                render_style,
                "italic",
                profile_path=profile_path,
            ),

            underline=self._optional_bool(
                render_style,
                "underline",
                profile_path=profile_path,
            ),

            strikeout=self._optional_bool(
                render_style,
                "strikeout",
                profile_path=profile_path,
            ),

            secondary_colour=self._optional_ass_colour(
                render_style,
                "secondary_colour",
                profile_path=profile_path,
            ),

            margin_l=self._optional_nonnegative_int(
                render_style,
                "margin_l",
                profile_path=profile_path,
            ),

            margin_r=self._optional_nonnegative_int(
                render_style,
                "margin_r",
                profile_path=profile_path,
            ),

            scale_x=self._optional_finite_number(
                render_style,
                "scale_x",
                profile_path=profile_path,
            ),

            scale_y=self._optional_finite_number(
                render_style,
                "scale_y",
                profile_path=profile_path,
            ),

            spacing=self._optional_finite_number(
                render_style,
                "spacing",
                profile_path=profile_path,
            ),
        )
        self._validate_render_style(
            subtitle_config,
            profile_path=profile_path,
        )
        return subtitle_config

    def _validate_render_style(
        self,
        subtitle_config,
        *,
        profile_path,
    ):
        context = (
            f"Perfil de subtitulos {profile_path}: "
            if profile_path is not None
            else ""
        )

        for field in (
            "primary_colour",
            "outline_colour",
            "back_colour",
        ):
            value = getattr(subtitle_config, field)
            if not self.ASS_COLOUR_PATTERN.fullmatch(value):
                raise ValueError(
                    f"{context}render_style.{field} debe usar el formato "
                    "ASS &HAABBGGRR. "
                    f"Valor recibido: {value!r}."
                )

        if subtitle_config.font_size <= 0:
            raise ValueError(
                f"{context}render_style.font_size debe ser > 0. "
                f"Valor recibido: {subtitle_config.font_size!r}."
            )

        if subtitle_config.border_style not in self.SUPPORTED_BORDER_STYLES:
            raise ValueError(
                f"{context}render_style.border_style debe ser uno de "
                f"{self.SUPPORTED_BORDER_STYLES}. "
                f"Valor recibido: {subtitle_config.border_style!r}."
            )

        for field in ("outline", "shadow", "margin_v"):
            value = getattr(subtitle_config, field)
            if value < 0:
                raise ValueError(
                    f"{context}render_style.{field} debe ser >= 0. "
                    f"Valor recibido: {value!r}."
                )

        if not 1 <= subtitle_config.alignment <= 9:
            raise ValueError(
                f"{context}render_style.alignment debe estar entre 1 y 9. "
                f"Valor recibido: {subtitle_config.alignment!r}."
            )

        if not math.isfinite(subtitle_config.offset):
            raise ValueError(
                f"{context}render_style.offset debe ser un numero finito "
                "de segundos. "
                f"Valor recibido: {subtitle_config.offset!r}."
            )

    def _optional_bool(self, render_style, field, *, profile_path):
        if field not in render_style:
            return None
        value = render_style[field]
        if not isinstance(value, bool):
            raise TypeError(
                f"{self._context(profile_path)}render_style.{field} "
                "debe ser booleano. "
                f"Valor recibido: {value!r}."
            )
        return value

    def _optional_ass_colour(self, render_style, field, *, profile_path):
        if field not in render_style:
            return None
        value = render_style[field]
        if not isinstance(value, str) or not self.ASS_COLOUR_PATTERN.fullmatch(value):
            raise ValueError(
                f"{self._context(profile_path)}render_style.{field} debe usar "
                "el formato ASS &HAABBGGRR. "
                f"Valor recibido: {value!r}."
            )
        return value

    def _optional_nonnegative_int(self, render_style, field, *, profile_path):
        if field not in render_style:
            return None
        value = render_style[field]
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(
                f"{self._context(profile_path)}render_style.{field} "
                "debe ser un entero. "
                f"Valor recibido: {value!r}."
            )
        if value < 0:
            raise ValueError(
                f"{self._context(profile_path)}render_style.{field} debe ser >= 0. "
                f"Valor recibido: {value!r}."
            )
        return value

    def _optional_finite_number(self, render_style, field, *, profile_path):
        if field not in render_style:
            return None
        value = render_style[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(
                f"{self._context(profile_path)}render_style.{field} "
                "debe ser numerico. "
                f"Valor recibido: {value!r}."
            )
        if not math.isfinite(value):
            raise ValueError(
                f"{self._context(profile_path)}render_style.{field} debe ser "
                "numerico finito. "
                f"Valor recibido: {value!r}."
            )
        return float(value)

    @staticmethod
    def _context(profile_path):
        if profile_path is None:
            return ""
        return f"Perfil de subtitulos {profile_path}: "
