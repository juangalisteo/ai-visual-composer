from app.modules.video.config.transition_config import (
    TransitionConfig
)
from app.shared.config_contract import (
    require_bool,
    require_float,
    require_mapping,
    require_sequence,
    require_text,
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

        video_style = require_mapping(
            profile,
            "video_style",
            "video_style"
        )

        transition_data = require_mapping(
            video_style,
            "transitions",
            "video_style.transitions"
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

        enabled = require_bool(
            transition_data,
            "enabled",
            "video_style.transitions.enabled"
        )

        duration = require_float(
            transition_data,
            "duration",
            "video_style.transitions.duration"
        )

        selection = require_text(
            transition_data,
            "selection",
            "video_style.transitions.selection"
        ).lower()

        avoid_repeats = require_bool(
            transition_data,
            "avoid_repeats",
            "video_style.transitions.avoid_repeats"
        )

        types = tuple(
            str(
                transition_type
            ).strip()
            for transition_type in require_sequence(
                transition_data,
                "types",
                "video_style.transitions.types"
            )
            if str(
                transition_type
            ).strip()
        )

        weights = {
            str(key).strip(): float(value)
            for key, value in require_mapping(
                transition_data,
                "weights",
                "video_style.transitions.weights"
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
