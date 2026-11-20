"""Whisper settings declared in ``config/whisper.json``.

- ``word_overlap_tolerance_seconds``: Whisper writes some word times with a
  float rounding error, such as a word that ends at 28.080000000000002 s
  while the next one starts at 28.08 s. An overlap between two consecutive
  words up to this many seconds is that rounding, and the later word starts
  where the earlier one ends; a larger overlap is real and the whole
  transcription is rejected (see ``WhisperTimingParser``).

Every key is required: the code never invents a value.
"""

import json
import math
from pathlib import Path

from app.shared.operational_error import create_operational_error


WHISPER_SETTINGS_PATH = Path("config/whisper.json")


def whisper_word_overlap_tolerance(path=WHISPER_SETTINGS_PATH) -> float:
    """Largest overlap, in seconds, between two words treated as rounding."""
    path = Path(path)
    key = "word_overlap_tolerance_seconds"
    value = _require_key(_load(path), key, path)
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise _config_error(
            f"En «{_display(path)}», «{key}» debe ser un número de "
            "segundos mayor o igual que 0.",
            f"Escriba en «{key}» un número, por ejemplo 0.001 (1 ms).",
            path,
            key=key,
        )
    return float(value)


def _load(path):
    if not path.is_file():
        raise _config_error(
            "Falta el archivo de configuración de Whisper "
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


def _require_key(document, key, path):
    if key not in document:
        raise _config_error(
            f"«{_display(path)}» no declara «{key}».",
            f"Añada «{key}» al archivo.",
            path,
            key=key,
        )
    return document[key]


def _display(path):
    return Path(path).as_posix()


def _config_error(user_message, recommended_action, path, *, key=None):
    return create_operational_error(
        family="CONFIG",
        user_message=user_message,
        recommended_action=recommended_action,
        operation="Cargar configuración de Whisper",
        resource=_display(path),
        technical_metadata=(
            {"key": key}
            if key is not None
            else None
        ),
    )
