"""Normalize SRT script-grid visual units for generated ASS documents."""

from dataclasses import replace

from app.modules.video.config.subtitle_config import (
    CueEffectConfig,
    WordEffectConfig,
)


class AssVisualScaleNormalizer:
    """Translate declarative subtitle units into the ASS PlayRes space.

    Static SRT subtitles use libass' 384x288 script grid when no script
    resolution is declared. Dynamic subtitles generate an ASS document whose
    PlayRes is the actual output resolution. This adapter preserves the visual
    meaning of declarative values while keeping the dynamic geometry in the
    real output coordinate system.
    """

    REFERENCE_PLAY_RES_X = 384
    REFERENCE_PLAY_RES_Y = 288

    def normalize(self, style, width, height):
        if width <= 0 or height <= 0:
            raise ValueError("La resolución ASS debe ser positiva.")

        horizontal_scale = width / self.REFERENCE_PLAY_RES_X
        vertical_scale = height / self.REFERENCE_PLAY_RES_Y

        return replace(
            style,
            font_size=self._scaled_positive_int(
                style.font_size,
                vertical_scale,
            ),
            outline=self._scaled_nonnegative_int(
                style.outline,
                vertical_scale,
            ),
            shadow=self._scaled_nonnegative_int(
                style.shadow,
                vertical_scale,
            ),
            margin_v=self._scaled_nonnegative_int(
                style.margin_v,
                vertical_scale,
            ),
            margin_l=self._scaled_optional_nonnegative_int(
                style.margin_l,
                horizontal_scale,
            ),
            margin_r=self._scaled_optional_nonnegative_int(
                style.margin_r,
                horizontal_scale,
            ),
            spacing=self._scaled_optional_number(
                style.spacing,
                vertical_scale,
            ),
            cue_effect=self._normalize_cue_effect(
                style.cue_effect,
                vertical_scale,
            ),
            word_effect=self._normalize_word_effect(
                style.word_effect,
                vertical_scale,
            ),
        )

    @staticmethod
    def _scaled_positive_int(value, scale):
        return max(1, round(value * scale))

    @staticmethod
    def _scaled_nonnegative_int(value, scale):
        return max(0, round(value * scale))

    @classmethod
    def _scaled_optional_nonnegative_int(cls, value, scale):
        if value is None:
            return None
        return cls._scaled_nonnegative_int(value, scale)

    @staticmethod
    def _scaled_optional_number(value, scale):
        if value is None:
            return None
        return value * scale

    @classmethod
    def _normalize_cue_effect(cls, effect, vertical_scale):
        if effect is None or effect.name != "gravity_drop":
            return effect
        parameters = dict(effect.parameters)
        parameters["drop_height_px"] = cls._scaled_positive_int(
            parameters["drop_height_px"],
            vertical_scale,
        )
        return CueEffectConfig(name=effect.name, parameters=parameters)

    @classmethod
    def _normalize_word_effect(cls, effect, vertical_scale):
        if effect is None or effect.name != "active_pill":
            return effect
        parameters = dict(effect.parameters)
        parameters["pill_padding"] = cls._scaled_nonnegative_int(
            parameters["pill_padding"],
            vertical_scale,
        )
        parameters["pill_radius"] = cls._scaled_nonnegative_int(
            parameters["pill_radius"],
            vertical_scale,
        )
        return WordEffectConfig(name=effect.name, parameters=parameters)
