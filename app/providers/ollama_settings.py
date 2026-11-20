"""Ollama call settings declared in ``config/ai.json``.

Only ``model`` is required. Whatever is not declared is not sent, so Ollama
applies its own default; the code never invents a value.

- ``keep_alive`` (top level): how long Ollama keeps the model loaded after
  each answer, in seconds or as a duration text such as ``"5m"``. ``0``
  unloads it as soon as it answers, which frees the GPU for Whisper and
  ComfyUI.
- One section per task (the caller names its own, e.g. ``script`` or
  ``storyboard``) may override ``model`` and declare ``think`` (true/false)
  and ``options``: Ollama options passed as they are, such as ``num_ctx``
  (context size in tokens).
"""

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Mapping

from app.shared.operational_error import create_operational_error


_RESOURCE = "config/ai.json"


@dataclass(frozen=True)
class OllamaCallSettings:
    """What one kind of Ollama call sends besides its prompt."""

    model: str
    keep_alive: int | float | str | None = None
    think: bool | None = None
    options: Mapping[str, object] | None = None

    def __post_init__(self):
        if self.options is not None:
            object.__setattr__(
                self,
                "options",
                MappingProxyType(dict(self.options)),
            )


def ollama_call_settings(ai_config, task=None) -> OllamaCallSettings:
    """Settings of the calls of ``task`` (or of any call, without a task)."""
    if not isinstance(ai_config, Mapping):
        raise _config_error("La configuración de IA debe ser un objeto JSON.")

    section = {}
    if task is not None:
        section = ai_config.get(task)
        if section is None:
            section = {}
        elif not isinstance(section, Mapping):
            raise _config_error(
                f"La sección «{task}» debe ser un objeto JSON.",
                key=task,
            )

    model_key = f"{task}.model" if "model" in section else "model"
    model = section.get("model", ai_config.get("model"))
    if not isinstance(model, str) or not model.strip():
        raise _config_error(
            "Falta el modelo de Ollama o está vacío.",
            key=model_key,
        )

    return OllamaCallSettings(
        model=model.strip(),
        keep_alive=_keep_alive(ai_config.get("keep_alive")),
        think=_think(section.get("think"), key=f"{task}.think"),
        options=_options(section.get("options"), key=f"{task}.options"),
    )


def _keep_alive(value):
    if value is None:
        return None
    if isinstance(value, bool):
        raise _keep_alive_error()
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            raise _keep_alive_error()
        return value
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise _keep_alive_error()


def _keep_alive_error():
    return _config_error(
        "«keep_alive» debe ser un número de segundos (0 libera la GPU al "
        "responder) o una duración como «5m».",
        key="keep_alive",
    )


def _think(value, *, key):
    if value is None or isinstance(value, bool):
        return value
    raise _config_error(
        f"«{key}» debe ser true, false o null.",
        key=key,
    )


def _options(value, *, key):
    if value is None:
        return None
    if not isinstance(value, Mapping) or not all(
        isinstance(name, str) and name for name in value
    ):
        raise _config_error(
            f"«{key}» debe ser un objeto con opciones de Ollama.",
            key=key,
        )
    if "num_ctx" in value:
        num_ctx = value["num_ctx"]
        if (
            isinstance(num_ctx, bool)
            or not isinstance(num_ctx, int)
            or num_ctx <= 0
        ):
            raise _config_error(
                f"«{key}.num_ctx» debe ser un número entero de tokens mayor "
                "que cero.",
                key=f"{key}.num_ctx",
            )
    return dict(value)


def _config_error(message, *, key=None):
    return create_operational_error(
        family="CONFIG",
        user_message=f"Configuración de Ollama no válida: {message}",
        recommended_action=f"Corrige {_RESOURCE} y vuelve a intentarlo.",
        operation="Cargar configuración de Ollama",
        resource=_RESOURCE,
        technical_metadata=(
            {"key": key}
            if key is not None
            else None
        ),
    )
