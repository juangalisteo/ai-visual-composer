from app.modules.video.config.motion_config import MotionConfig
from app.shared.config_contract import (
    require_bool,
    require_float,
    require_int,
    require_mapping,
    require_sequence,
    require_text,
)


class MotionConfigLoader:

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

        motion_data = require_mapping(
            video_style,
            "motion",
            "video_style.motion"
        )

        if not isinstance(
            motion_data,
            dict
        ):
            raise TypeError(
                "La configuración video_style.motion "
                "debe ser un diccionario."
            )

        enabled = require_bool(
            motion_data,
            "enabled",
            "video_style.motion.enabled"
        )

        internal_scale = require_int(
            motion_data,
            "internal_scale",
            "video_style.motion.internal_scale"
        )

        base_zoom = require_float(
            motion_data,
            "base_zoom",
            "video_style.motion.base_zoom"
        )

        zoom_amount = require_float(
            motion_data,
            "zoom_amount",
            "video_style.motion.zoom_amount"
        )

        pan_zoom_enabled = require_bool(
            motion_data,
            "pan_zoom_enabled",
            "video_style.motion.pan_zoom_enabled"
        )

        pan_zoom_start = require_float(
            motion_data,
            "pan_zoom_start",
            "video_style.motion.pan_zoom_start"
        )

        selection = require_text(
            motion_data,
            "selection",
            "video_style.motion.selection"
        ).lower()

        avoid_repeats = require_bool(
            motion_data,
            "avoid_repeats",
            "video_style.motion.avoid_repeats"
        )

        types = tuple(
            str(
                motion_type
            ).strip()
            for motion_type in require_sequence(
                motion_data,
                "types",
                "video_style.motion.types"
            )
            if str(
                motion_type
            ).strip()
        )

        weights = {
            str(key).strip(): float(value)
            for key, value in require_mapping(
                motion_data,
                "weights",
                "video_style.motion.weights"
            ).items()
        }

        if not weights:
            weights = {
                motion_type: 1.0
                for motion_type in types
            }

        return MotionConfig(
            enabled=enabled,
            internal_scale=internal_scale,
            base_zoom=base_zoom,
            zoom_amount=zoom_amount,
            pan_zoom_enabled=pan_zoom_enabled,
            pan_zoom_start=pan_zoom_start,
            selection=selection,
            avoid_repeats=avoid_repeats,
            types=types,
            weights=weights
        )
