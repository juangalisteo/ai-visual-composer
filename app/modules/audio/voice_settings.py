"""Settings shared by every voice, declared in ``config/voice.json``.

- ``workspace_dir``: folder where ``VoiceBuilder`` creates the private working
  folder of each synthesis (every voice, Piper included), relative to the
  project folder and inside it. Each synthesis uses a new subfolder that is
  removed when it ends. In the project it is ``tmp/voice``, ignored by Git, so
  nothing is written to the system ``%TEMP%``.

Every key is required: the code never invents a value.
"""

import json
import os
from pathlib import Path

from app.modules.audio.tts_backend_runtime import DEFAULT_TTS_PROJECT_ROOT
from app.shared.operational_error import create_operational_error


VOICE_SETTINGS_PATH = Path("config/voice.json")
_WORKSPACE_KEY = "workspace_dir"


def voice_workspace_dir(
    path=VOICE_SETTINGS_PATH,
    project_root=DEFAULT_TTS_PROJECT_ROOT,
) -> Path:
    """Absolute folder declared in ``workspace_dir``, inside the project."""
    path = Path(path)
    document = _load(path)
    if _WORKSPACE_KEY not in document:
        raise _config_error(
            f"«{_display(path)}» no declara «{_WORKSPACE_KEY}», la carpeta de "
            "trabajo de la voz.",
            f"Añada «{_WORKSPACE_KEY}» con una ruta relativa dentro de la "
            "carpeta del proyecto, por ejemplo «tmp/voice».",
            path,
        )
    value = document[_WORKSPACE_KEY]
    if not isinstance(value, str) or not value.strip():
        raise _config_error(
            f"En «{_display(path)}», «{_WORKSPACE_KEY}» debe ser una ruta "
            f"relativa a la carpeta del proyecto; se recibió {value!r}.",
            f"Escriba en «{_WORKSPACE_KEY}» una ruta como «tmp/voice».",
            path,
        )
    declared = Path(value.strip())
    root = Path(os.path.abspath(project_root))
    folder = Path(os.path.normpath(root / declared))
    if declared.is_absolute() or not folder.is_relative_to(root) or folder == root:
        raise _config_error(
            f"En «{_display(path)}», «{_WORKSPACE_KEY}» debe ser una carpeta "
            "dentro de la carpeta del proyecto; se recibió "
            f"«{declared.as_posix()}».",
            f"Escriba en «{_WORKSPACE_KEY}» una ruta relativa como "
            "«tmp/voice» (nunca absoluta ni con «..» hacia fuera).",
            path,
        )
    return folder


def _load(path):
    if not path.is_file():
        raise _config_error(
            "Falta el archivo de configuración de la voz "
            f"«{_display(path)}».",
            "Restaure el archivo en la carpeta config/.",
            path,
        )
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise _config_error(
            f"«{_display(path)}» no es un JSON válido (línea {error.lineno}).",
            "Corrija el JSON del archivo.",
            path,
        ) from error
    if not isinstance(document, dict):
        raise _config_error(
            f"«{_display(path)}» debe ser un objeto JSON.",
            "Escriba el contenido entre llaves { }.",
            path,
        )
    return document


def _display(path):
    return Path(path).as_posix()


def _config_error(user_message, recommended_action, path):
    return create_operational_error(
        family="CONFIG",
        user_message=user_message,
        recommended_action=recommended_action,
        operation="Cargar configuración de la voz",
        resource=_display(path),
        technical_metadata={"key": _WORKSPACE_KEY},
    )
