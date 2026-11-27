"""Small JSON settings documents under ``config/`` (A1).

Each document is one JSON object whose keys are all required: the code never
invents a value. Every problem is a CONFIG error that names the file by the
path it was given (relative to the project folder in the program).
"""

import json
import re
from pathlib import Path

from app.shared.operational_error import create_operational_error


_TOKEN = re.compile(r"[A-Za-z0-9_+]+")


def load_settings_document(path, *, operation):
    """The JSON object stored in ``path``."""
    path = Path(path)
    if not path.is_file():
        raise settings_error(
            path,
            f"Falta el archivo de configuración «{display_path(path)}».",
            "Restaure el archivo en la carpeta config/.",
            operation=operation,
        )
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise settings_error(
            path,
            f"«{display_path(path)}» no es un JSON válido (línea {error.lineno}).",
            "Corrija el JSON del archivo.",
            operation=operation,
        ) from error
    if not isinstance(document, dict):
        raise settings_error(
            path,
            f"«{display_path(path)}» debe ser un objeto JSON.",
            "Escriba el contenido entre llaves { }.",
            operation=operation,
        )
    return document


def require_setting(document, keys, path, *, operation, example):
    """Value at ``keys`` (a path of nested keys) inside ``document``."""
    value = document
    for depth, key in enumerate(keys):
        if not isinstance(value, dict) or key not in value:
            name = ".".join(keys[: depth + 1])
            raise settings_error(
                path,
                f"«{display_path(path)}» no declara «{name}».",
                f"Añada «{'.'.join(keys)}», por ejemplo {example}.",
                operation=operation,
                key=".".join(keys),
            )
        value = value[key]
    return value


def require_token(document, keys, path, *, operation, example):
    """Non-empty text made only of letters, digits, «_» and «+».

    Values that end up inside an FFmpeg filter must not carry «:», «,»,
    «;» or brackets, which would change the filter graph.
    """
    value = require_setting(
        document, keys, path, operation=operation, example=example
    )
    if not isinstance(value, str) or _TOKEN.fullmatch(value) is None:
        name = ".".join(keys)
        raise settings_error(
            path,
            f"En «{display_path(path)}», «{name}» debe ser un texto de letras, "
            f"números, «_» o «+»; se recibió {value!r}.",
            f"Escriba en «{name}» un valor como {example}.",
            operation=operation,
            key=name,
        )
    return value


def require_seconds(document, keys, path, *, operation, example):
    """A number of seconds, zero or more."""
    value = require_setting(
        document, keys, path, operation=operation, example=example
    )
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not 0 <= value < float("inf")
    ):
        name = ".".join(keys)
        raise settings_error(
            path,
            f"En «{display_path(path)}», «{name}» debe ser un número de "
            f"segundos mayor o igual que 0; se recibió {value!r}.",
            f"Escriba en «{name}» un número como {example}.",
            operation=operation,
            key=name,
        )
    return float(value)


def display_path(path):
    return Path(path).as_posix()


def settings_error(path, user_message, recommended_action, *, operation, key=None):
    return create_operational_error(
        family="CONFIG",
        user_message=user_message,
        recommended_action=recommended_action,
        operation=operation,
        resource=display_path(path),
        technical_metadata={"key": key} if key is not None else None,
    )
