from app.modules.video.config.transition_config import (
    TransitionConfig
)


class TransitionConfigLoader:

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

        transition_data = video_style.get(
            "transitions",
            {}
        )

        if not isinstance(
            transition_data,
            dict
        ):
            raise TypeError(
                "La configuración "
                "video_style.transitions "
                "debe ser un diccionario."
            )

        enabled = bool(
            transition_data.get(
                "enabled",
                True
            )
        )

        duration = float(
            transition_data.get(
                "duration",
                0.50
            )
        )

        selection = str(
            transition_data.get(
                "selection",
                "sequence"
            )
        ).strip().lower()

        avoid_repeats = bool(
            transition_data.get(
                "avoid_repeats",
                False
            )
        )

        types = tuple(
            str(
                transition_type
            ).strip()
            for transition_type in transition_data.get(
                "types",
                [
                    "fade",
                    "smoothleft",
                    "fadeblack"
                ]
            )
            if str(
                transition_type
            ).strip()
        )

        weights = {
            str(key).strip(): float(value)
            for key, value in transition_data.get(
                "weights",
                {}
            ).items()
        }

        if not weights:
            weights = {
                transition_type: 1.0
                for transition_type in types
            }

        return TransitionConfig(
            enabled=enabled,
            duration=duration,
            selection=selection,
            avoid_repeats=avoid_repeats,
            types=types,
            weights=weights
        )