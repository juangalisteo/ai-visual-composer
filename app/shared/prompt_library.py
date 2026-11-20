"""Texts of prompts/ sent to the models, with {markers} for the data.

Every text the program sends to Ollama, Flux or WAN lives in ``prompts/``.
A template marks with ``{name}`` each piece of data the program fills in;
the program declares which markers each template needs, so a missing or
unknown marker is a CONFIG error, never a silently broken prompt.

A text that depends on the tone lives in its own folder: ``<tone>.txt`` for
one tone and ``default.txt`` (or ``.json``) shared by every other tone.
"""

import json
import re
from pathlib import Path, PurePosixPath

from app.shared.operational_error import create_operational_error


PROMPTS_ROOT = Path("prompts")

# File of a per-tone folder used by every tone without its own file.
DEFAULT_TONE_NAME = "default"

_MARKER = re.compile(r"\{([a-z_][a-z0-9_]*)\}")


class PromptLibrary:
    """Reads the files of one prompts/ folder (``prompts`` by default)."""

    def __init__(self, root=PROMPTS_ROOT):
        self.root = Path(root)

    def text(self, relative_path) -> str:
        """Content of one file, without surrounding blank space."""
        path = self.root / relative_path
        if not path.is_file():
            raise _config_error(
                f"Falta el archivo de prompt «{self.display(relative_path)}».",
                "Restaure el archivo en la carpeta prompts/.",
                self.display(relative_path),
            )
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            raise _config_error(
                f"El archivo de prompt «{self.display(relative_path)}» "
                "está vacío.",
                "Escriba en él el texto del prompt.",
                self.display(relative_path),
            )
        return content

    def render(self, relative_path, **values) -> str:
        """Template with each ``{marker}`` replaced by its value.

        Every value must have its marker in the template and every marker
        must have a value; values are inserted as they are, never re-read.
        """
        template = self.text(relative_path)
        found = set(_MARKER.findall(template))
        missing = [name for name in values if name not in found]
        if missing:
            marker = "{" + missing[0] + "}"
            raise _config_error(
                f"Al archivo de prompt «{self.display(relative_path)}» "
                f"le falta el marcador {marker}.",
                f"Escriba {marker} donde deba ir ese dato.",
                self.display(relative_path),
            )
        unknown = sorted(found - set(values))
        if unknown:
            raise _config_error(
                f"El archivo de prompt «{self.display(relative_path)}» "
                f"tiene un marcador desconocido: {{{unknown[0]}}}.",
                "Quítelo o use solo estos marcadores: "
                + ", ".join("{" + name + "}" for name in values)
                + ".",
                self.display(relative_path),
            )
        return _MARKER.sub(
            lambda match: str(values[match.group(1)]),
            template,
        )

    def template(self, relative_path, allowed_markers) -> str:
        """Template filled later, whose markers are any of ``allowed_markers``.

        At least one marker is needed; an unknown one is a CONFIG error.
        """
        template = self.text(relative_path)
        found = tuple(dict.fromkeys(_MARKER.findall(template)))
        allowed = ", ".join("{" + name + "}" for name in allowed_markers)
        unknown = [name for name in found if name not in allowed_markers]
        if unknown:
            raise _config_error(
                f"El archivo de prompt «{self.display(relative_path)}» "
                f"tiene un marcador desconocido: {{{unknown[0]}}}.",
                f"Quítelo o use solo estos marcadores: {allowed}.",
                self.display(relative_path),
            )
        if not found:
            raise _config_error(
                f"El archivo de prompt «{self.display(relative_path)}» "
                "no tiene ningún marcador.",
                f"Escriba al menos uno de estos marcadores: {allowed}.",
                self.display(relative_path),
            )
        return template

    def mapping(self, relative_path) -> dict:
        """JSON object of one file."""
        content = self.text(relative_path)
        try:
            document = json.loads(content)
        except json.JSONDecodeError as error:
            raise _config_error(
                f"El archivo de prompt «{self.display(relative_path)}» "
                f"no es un JSON válido (línea {error.lineno}).",
                "Corrija el JSON del archivo.",
                self.display(relative_path),
            ) from error
        if not isinstance(document, dict):
            raise _config_error(
                f"El archivo de prompt «{self.display(relative_path)}» "
                "debe ser un objeto JSON.",
                "Escriba el contenido entre llaves { }.",
                self.display(relative_path),
            )
        return document

    def tone_file(self, folder, tone, suffix=".txt") -> str:
        """``<folder>/<tone><suffix>`` if it exists, else the shared default."""
        if tone:
            own = PurePosixPath(folder) / f"{tone}{suffix}"
            if (self.root / own).is_file():
                return str(own)
        return str(PurePosixPath(folder) / f"{DEFAULT_TONE_NAME}{suffix}")

    def display(self, relative_path) -> str:
        """Path shown to the user, as written from the project root."""
        return (PurePosixPath(self.root.as_posix()) / relative_path).as_posix()


def require_prompt_text(document, key, library, relative_path) -> str:
    """Non-empty text declared under ``key`` in a JSON prompt file."""
    value = document.get(key)
    if not isinstance(value, str) or not value.strip():
        raise _config_error(
            f"El archivo de prompt «{library.display(relative_path)}» "
            f"no declara el texto «{key}».",
            f"Añada «{key}» con su texto.",
            library.display(relative_path),
        )
    return value


def require_prompt_texts(document, key, library, relative_path) -> tuple:
    """Non-empty list of texts declared under ``key`` in a JSON prompt file."""
    value = document.get(key)
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item.strip() for item in value)
    ):
        raise _config_error(
            f"El archivo de prompt «{library.display(relative_path)}» "
            f"no declara la lista de textos «{key}».",
            f"Añada «{key}» como lista de textos.",
            library.display(relative_path),
        )
    return tuple(value)


def require_prompt_replacements(document, library, relative_path) -> tuple:
    """``(phrase, replacement)`` pairs of a JSON object of texts, in order."""
    pairs = []
    for phrase, replacement in document.items():
        if (
            not phrase.strip()
            or not isinstance(replacement, str)
            or not replacement.strip()
        ):
            raise _config_error(
                f"El archivo de prompt «{library.display(relative_path)}» "
                f"no declara con qué se sustituye «{phrase}».",
                "Escriba cada objeto con su sustituto como texto.",
                library.display(relative_path),
            )
        pairs.append((phrase.strip(), replacement.strip()))
    return tuple(pairs)


def _config_error(user_message, recommended_action, resource):
    return create_operational_error(
        family="CONFIG",
        user_message=user_message,
        recommended_action=recommended_action,
        operation="Leer prompts",
        resource=resource,
    )
