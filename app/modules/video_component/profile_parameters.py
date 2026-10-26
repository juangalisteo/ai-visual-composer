"""Declarative WAN profile loading and BackendVideoPrompt parameters."""

import secrets

from app.shared.profile_identity import (
    OperationalProfileKey,
    ProfileComponent,
)
from app.shared.profile_resolver import ProfileResolver


def load_video_component_parameters(profile_key, resolver=None):
    """Load one declarative WAN document for an explicit VIDEO identity."""
    if not isinstance(profile_key, OperationalProfileKey):
        raise TypeError(
            "La configuracion Wan requiere una identidad operacional "
            "VIDEO explicito."
        )

    if profile_key.component is not ProfileComponent.VIDEO:
        raise ValueError(
            "La configuracion Wan requiere identidad del "
            "componente video."
        )

    return (resolver or ProfileResolver()).load_video_component(profile_key)


def build_video_backend_overrides(profile):
    """Translate the declared ``video_component`` block without inference."""
    video_component = profile.get(
        "video_component",
        {}
    )

    if not video_component:
        raise ValueError(
            "El perfil de Video debe definir video_component."
        )

    generation = video_component.get(
        "generation",
        {}
    )
    sampling = video_component.get(
        "sampling",
        {}
    )
    delivery = video_component.get(
        "delivery",
        {}
    )

    return {
        "profile_name": str(
            video_component.get(
                "profile",
                profile.get(
                    "format",
                    ""
                )
            )
        ),
        "generation_width": _required_int(
            generation,
            "width",
            "generation.width"
        ),
        "generation_height": _required_int(
            generation,
            "height",
            "generation.height"
        ),
        "frames": _required_int(
            video_component,
            "frames",
            "frames"
        ),
        "fps": _required_float(
            video_component,
            "fps",
            "fps"
        ),
        "seed": _resolve_video_seed(
            video_component
        ),
        "steps": _required_int(
            sampling,
            "steps",
            "sampling.steps"
        ),
        "cfg": _required_float(
            sampling,
            "cfg",
            "sampling.cfg"
        ),
        "sampler": _required_text(
            sampling,
            "sampler",
            "sampling.sampler"
        ),
        "scheduler": _required_text(
            sampling,
            "scheduler",
            "sampling.scheduler"
        ),
        "intermediate_output": delivery.get(
            "intermediate_output",
            "savevideo_h264",
        ),
    }


def _resolve_video_seed(video_component):
    seed_mode = str(
        video_component.get(
            "seed_mode",
            ""
        )
    ).strip().lower()

    if seed_mode == "random":
        return _random_video_seed()

    if seed_mode == "fixed":
        return _required_seed(video_component)

    raise ValueError(
        "Parámetro de vídeo inválido: seed_mode."
    )


def _random_video_seed():
    return secrets.randbelow(2 ** 63)


def _required_seed(video_component):
    try:
        seed = int(video_component["seed"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            "Parámetro de vídeo inválido: seed."
        ) from error

    if seed < 0:
        raise ValueError(
            "Parámetro de vídeo inválido: seed."
        )

    return seed


def _required_int(data, key, label):
    try:
        value = int(data[key])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            f"Parámetro de vídeo inválido: {label}."
        ) from error

    if value <= 0:
        raise ValueError(
            f"Parámetro de vídeo inválido: {label}."
        )

    return value


def _required_float(data, key, label):
    try:
        value = float(data[key])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            f"Parámetro de vídeo inválido: {label}."
        ) from error

    if value <= 0:
        raise ValueError(
            f"Parámetro de vídeo inválido: {label}."
        )

    return value


def _required_text(data, key, label):
    value = str(data.get(key, "")).strip()
    if not value:
        raise ValueError(
            f"Parámetro de vídeo inválido: {label}."
        )
    return value
