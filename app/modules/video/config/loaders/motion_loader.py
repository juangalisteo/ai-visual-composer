from app.modules.video.config.motion_config import MotionConfig


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

        video_style = profile.get(
            "video_style",
            {}
        )

        motion_data = video_style.get(
            "motion",
            {}
        )

        if not isinstance(
            motion_data,
            dict
        ):
            raise TypeError(
                "La configuración video_style.motion "
                "debe ser un diccionario."
            )

        enabled = bool(
            motion_data.get(
                "enabled",
                True
            )
        )

        internal_scale = int(
            motion_data.get(
                "internal_scale",
                2
            )
        )

        base_zoom = float(
            motion_data.get(
                "base_zoom",
                0.00
            )
        )

        zoom_amount = float(
            motion_data.get(
                "zoom_amount",
                0.10
            )
        )

        pan_zoom_enabled = bool(
            motion_data.get(
                "pan_zoom_enabled",
                False
            )
        )

        pan_zoom_start = float(
            motion_data.get(
                "pan_zoom_start",
                0.00
            )
        )

        selection = str(
            motion_data.get(
                "selection",
                "sequence"
            )
        ).strip().lower()

        avoid_repeats = bool(
            motion_data.get(
                "avoid_repeats",
                False
            )
        )

        types = tuple(
            str(
                motion_type
            ).strip()
            for motion_type in motion_data.get(
                "types",
                [
                    "zoom_in",
                    "pan_left",
                    "zoom_out",
                    "pan_right",
                    "pan_up",
                    "pan_down"
                ]
            )
            if str(
                motion_type
            ).strip()
        )

        weights = {
            str(key).strip(): float(value)
            for key, value in motion_data.get(
                "weights",
                {}
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