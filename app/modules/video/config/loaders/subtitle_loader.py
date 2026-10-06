import math
import re

from app.modules.video.config.subtitle_config import (
    CueEffectConfig,
    SubtitleConfig,
    WordEffectConfig,
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
    EFFECT_FIELDS = {
        "fade": {"enabled", "in_ms", "out_ms"},
        "pop": {"enabled", "in_ms", "from_scale"},
        "zoom": {"enabled", "in_ms", "from_scale", "to_scale"},
        "slide": {"enabled", "direction", "duration_ms"},
    }
    DIRECT_CUE_EFFECTS = {"gravity_drop"}
    WORD_EFFECT_FIELDS = {
        "karaoke": {"enabled"},
        "highlight": {"enabled", "active_colour"},
        "progressive_reveal": {"enabled", "reveal_ms"},
    }
    IN_SENTENCE_WORD_EFFECTS = {
        "highlight_in_sentence",
        "active_pill",
        "pop_in_sentence",
        "continuous_karaoke",
        "typewriter",
        "alpha_fade",
    }

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

        dynamic = self._optional_bool(
            render_style,
            "dynamic",
            profile_path=profile_path,
        ) or False
        cue_effect = self._load_cue_effect(
            render_style,
            profile_path=profile_path,
        )
        word_effect = self._load_word_effect(
            render_style,
            profile_path=profile_path,
        )
        if (cue_effect is not None or word_effect is not None) and not dynamic:
            raise ValueError(
                f"{self._context(profile_path)}un efecto dinamico requiere "
                "render_style.dynamic=true."
            )
        if cue_effect is not None and word_effect is not None:
            raise ValueError(
                f"{self._context(profile_path)}effects y word_effects no pueden "
                "combinarse en la misma representacion."
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

            dynamic=dynamic,

            cue_effect=cue_effect,

            word_effect=word_effect,

            scroll_duration_ms=self._optional_positive_int(
                render_style,
                "scroll_duration_ms",
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

    def _optional_positive_int(self, render_style, field, *, profile_path):
        value = self._optional_nonnegative_int(
            render_style,
            field,
            profile_path=profile_path,
        )
        if value == 0:
            raise ValueError(
                f"{self._context(profile_path)}render_style.{field} debe ser > 0. "
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

    def _load_cue_effect(self, render_style, *, profile_path):
        declared_effect = self._load_declared_cue_effect(
            render_style,
            profile_path=profile_path,
        )
        if "effects" not in render_style:
            return declared_effect
        if declared_effect is not None:
            raise ValueError(
                f"{self._context(profile_path)}cue_effect y effects no pueden "
                "combinarse en la misma representacion."
            )
        effects = render_style["effects"]
        if not isinstance(effects, dict):
            raise TypeError(
                f"{self._context(profile_path)}render_style.effects debe ser "
                "un diccionario."
            )
        unknown = set(effects) - set(self.EFFECT_FIELDS)
        if unknown:
            raise ValueError(
                f"{self._context(profile_path)}efecto de subtitulos no "
                f"soportado: {sorted(unknown)[0]!r}."
            )
        enabled = []
        for name, values in effects.items():
            if not isinstance(values, dict):
                raise TypeError(
                    f"{self._context(profile_path)}render_style.effects.{name} "
                    "debe ser un diccionario."
                )
            extra = set(values) - self.EFFECT_FIELDS[name]
            if extra:
                raise ValueError(
                    f"{self._context(profile_path)}parametro no soportado para "
                    f"{name}: {sorted(extra)[0]!r}."
                )
            if "enabled" not in values or not isinstance(values["enabled"], bool):
                raise TypeError(
                    f"{self._context(profile_path)}render_style.effects.{name}.enabled "
                    "debe ser booleano."
                )
            if values["enabled"]:
                enabled.append((name, values))
        if len(enabled) > 1:
            raise ValueError(
                f"{self._context(profile_path)}solo se permite un efecto por cue."
            )
        if not enabled:
            return None
        name, values = enabled[0]
        parameters = self._effect_parameters(name, values, profile_path)
        return CueEffectConfig(name=name, parameters=parameters)

    def _load_declared_cue_effect(self, render_style, *, profile_path):
        declared_effect = render_style.get("cue_effect")
        if declared_effect is None:
            return None
        if not isinstance(declared_effect, str):
            raise TypeError(
                f"{self._context(profile_path)}render_style.cue_effect "
                "debe ser texto."
            )
        declared_effect = declared_effect.strip().lower()
        if declared_effect == "none":
            return None
        if declared_effect not in self.DIRECT_CUE_EFFECTS:
            raise ValueError(
                f"{self._context(profile_path)}cue effect no soportado: "
                f"{declared_effect!r}."
            )
        return CueEffectConfig(
            name=declared_effect,
            parameters=self._declared_cue_effect_parameters(
                declared_effect,
                render_style,
                profile_path,
            ),
        )

    def _declared_cue_effect_parameters(self, name, render_style, profile_path):
        if name != "gravity_drop":
            raise ValueError(f"Cue effect no soportado: {name!r}.")
        height = render_style.get("drop_height_px", 100)
        if isinstance(height, bool) or not isinstance(height, int) or height <= 0:
            raise ValueError(
                f"{self._context(profile_path)}render_style.drop_height_px "
                "debe ser un entero > 0."
            )
        elasticity = render_style.get("bounce_elasticity", 0.30)
        if (
            isinstance(elasticity, bool)
            or not isinstance(elasticity, (int, float))
            or not math.isfinite(elasticity)
            or not 0.0 <= elasticity <= 1.0
        ):
            raise ValueError(
                f"{self._context(profile_path)}render_style.bounce_elasticity "
                "debe ser un numero entre 0.0 y 1.0."
            )
        return {
            "drop_height_px": height,
            "bounce_elasticity": float(elasticity),
        }

    def _effect_parameters(self, name, values, profile_path):
        required = self.EFFECT_FIELDS[name] - {"enabled"}
        missing = required - set(values)
        if missing:
            raise ValueError(
                f"{self._context(profile_path)}efecto {name} requiere "
                f"{sorted(missing)[0]}."
            )
        if name == "fade":
            return {
                "in_ms": self._nonnegative_ms(values["in_ms"], name, "in_ms", profile_path),
                "out_ms": self._nonnegative_ms(values["out_ms"], name, "out_ms", profile_path),
            }
        if name in ("pop", "zoom"):
            parameters = {
                "in_ms": self._positive_ms(values["in_ms"], name, "in_ms", profile_path),
                "from_scale": self._scale(values["from_scale"], name, "from_scale", profile_path),
            }
            if name == "zoom":
                parameters["to_scale"] = self._scale(
                    values["to_scale"], name, "to_scale", profile_path
                )
            return parameters
        direction = values["direction"]
        if direction not in ("left", "right", "up", "down"):
            raise ValueError(
                f"{self._context(profile_path)}efecto slide.direction debe ser "
                "left, right, up o down."
            )
        return {
            "direction": direction,
            "duration_ms": self._positive_ms(
                values["duration_ms"], name, "duration_ms", profile_path
            ),
        }

    def _load_word_effect(self, render_style, *, profile_path):
        declared_effect = render_style.get("word_effect")
        if declared_effect is not None:
            if not isinstance(declared_effect, str):
                raise TypeError(
                    f"{self._context(profile_path)}render_style.word_effect "
                    "debe ser texto."
                )
            declared_effect = declared_effect.strip().lower()
            if declared_effect == "none":
                declared_effect = None
            elif declared_effect not in self.IN_SENTENCE_WORD_EFFECTS:
                raise ValueError(
                    f"{self._context(profile_path)}word effect no soportado: "
                    f"{declared_effect!r}."
                )

        if "word_effects" not in render_style:
            return (
                WordEffectConfig(
                    name=declared_effect,
                    parameters=self._in_sentence_parameters(
                        declared_effect,
                        render_style,
                        profile_path,
                    ),
                )
                if declared_effect is not None
                else None
            )
        if declared_effect is not None:
            raise ValueError(
                f"{self._context(profile_path)}word_effect y word_effects no "
                "pueden combinarse en la misma representacion."
            )
        effects = render_style["word_effects"]
        if not isinstance(effects, dict):
            raise TypeError(
                f"{self._context(profile_path)}render_style.word_effects debe ser "
                "un diccionario."
            )
        unknown = set(effects) - set(self.WORD_EFFECT_FIELDS)
        if unknown:
            raise ValueError(
                f"{self._context(profile_path)}word effect no soportado: "
                f"{sorted(unknown)[0]!r}."
            )
        enabled = []
        for name, values in effects.items():
            if not isinstance(values, dict):
                raise TypeError(
                    f"{self._context(profile_path)}render_style.word_effects.{name} "
                    "debe ser un diccionario."
                )
            extra = set(values) - self.WORD_EFFECT_FIELDS[name]
            if extra:
                raise ValueError(
                    f"{self._context(profile_path)}parametro no soportado para "
                    f"word effect {name}: {sorted(extra)[0]!r}."
                )
            if "enabled" not in values or not isinstance(values["enabled"], bool):
                raise TypeError(
                    f"{self._context(profile_path)}render_style.word_effects.{name}.enabled "
                    "debe ser booleano."
                )
            if values["enabled"]:
                enabled.append((name, values))
        if len(enabled) > 1:
            raise ValueError(
                f"{self._context(profile_path)}solo se permite un word effect por cue."
            )
        if not enabled:
            return None
        name, values = enabled[0]
        required = self.WORD_EFFECT_FIELDS[name] - {"enabled"}
        missing = required - set(values)
        if missing:
            raise ValueError(
                f"{self._context(profile_path)}word effect {name} requiere "
                f"{sorted(missing)[0]}."
            )
        if name == "karaoke":
            parameters = {}
        elif name == "highlight":
            colour = values["active_colour"]
            if not isinstance(colour, str) or not self.ASS_COLOUR_PATTERN.fullmatch(colour):
                raise ValueError(
                    f"{self._context(profile_path)}word effect highlight.active_colour "
                    "debe usar el formato ASS &HAABBGGRR."
                )
            parameters = {"active_colour": colour}
        else:
            parameters = {
                "reveal_ms": self._positive_ms(
                    values["reveal_ms"], name, "reveal_ms", profile_path
                )
            }
        return WordEffectConfig(name=name, parameters=parameters)

    def _in_sentence_parameters(self, name, render_style, profile_path):
        if name == "alpha_fade":
            value = render_style.get("fade_duration_ms", 150)
            return {
                "fade_duration_ms": self._positive_ms(
                    value,
                    name,
                    "fade_duration_ms",
                    profile_path,
                ),
            }
        if name == "typewriter":
            cursor = self._optional_bool(
                render_style,
                "typewriter_cursor",
                profile_path=profile_path,
            )
            cursor_char = render_style.get("cursor_char", "_")
            if not isinstance(cursor_char, str) or len(cursor_char) != 1:
                raise ValueError(
                    f"{self._context(profile_path)}render_style.cursor_char "
                    "debe contener un unico caracter."
                )
            return {
                "typewriter_cursor": bool(cursor),
                "cursor_char": cursor_char,
            }
        if name == "pop_in_sentence":
            value = render_style.get("word_pop_scale", 125)
            if isinstance(value, bool) or not isinstance(value, int) or not 100 <= value <= 300:
                raise ValueError(
                    f"{self._context(profile_path)}render_style.word_pop_scale "
                    "debe ser un entero entre 100 y 300."
                )
            return {"word_pop_scale": value}
        if name != "active_pill":
            return {}
        colour = render_style.get("pill_colour")
        if not isinstance(colour, str) or not self.ASS_COLOUR_PATTERN.fullmatch(colour):
            raise ValueError(
                f"{self._context(profile_path)}render_style.pill_colour "
                "debe usar el formato ASS &HAABBGGRR."
            )
        return {
            "pill_colour": colour,
            "pill_padding": self._optional_nonnegative_int(
                render_style,
                "pill_padding",
                profile_path=profile_path,
            ) if "pill_padding" in render_style else 6,
            "pill_radius": self._optional_nonnegative_int(
                render_style,
                "pill_radius",
                profile_path=profile_path,
            ) if "pill_radius" in render_style else 4,
        }

    def _nonnegative_ms(self, value, effect, field, profile_path):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(
                f"{self._context(profile_path)}efecto {effect}.{field} debe ser "
                "un entero >= 0."
            )
        return value

    def _positive_ms(self, value, effect, field, profile_path):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(
                f"{self._context(profile_path)}efecto {effect}.{field} debe ser "
                "un entero > 0."
            )
        return value

    def _scale(self, value, effect, field, profile_path):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(
                f"{self._context(profile_path)}efecto {effect}.{field} debe ser numerico."
            )
        value = float(value)
        if not math.isfinite(value) or not 1 <= value <= 400:
            raise ValueError(
                f"{self._context(profile_path)}efecto {effect}.{field} debe estar entre 1 y 400."
            )
        return value

    @staticmethod
    def _context(profile_path):
        if profile_path is None:
            return ""
        return f"Perfil de subtitulos {profile_path}: "
