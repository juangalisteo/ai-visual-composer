"""Folders of the local ComfyUI and the files this program leaves in them.

``config/comfyui.json`` declares:

- ``input_directory`` and ``output_directory``: the ``input/`` and
  ``output/`` folders of the local ComfyUI. The program copies into the input
  folder the source image of each WAN clip, and ComfyUI saves into the output
  folder every image and clip it generates.
- ``cleanup_after_copy``: true to delete, as soon as each image or clip has
  been copied into the project, the files this program left in those folders;
  false to keep them there.

Every key is required: the code never invents a value.

Each image or clip leaves its files in a folder of its own job (a new
technical name), so the cleanup only ever deletes what that job created: the
job folder with what is inside and the empty folders above it that did not
exist before the job. A failed deletion is a warning: the run goes on.
"""

import json
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from app.shared.operational_error import create_operational_error
from app.shared.progress_logger import ProgressLogger


COMFYUI_SETTINGS_PATH = Path("config/comfyui.json")

# Folder keys, with what each one names (for the user, in the CONFIG error).
_DIRECTORY_KEYS = (
    ("input_directory", "la carpeta input/ de ComfyUI"),
    ("output_directory", "la carpeta output/ de ComfyUI"),
)
_CLEANUP_KEY = "cleanup_after_copy"


@dataclass(frozen=True)
class ComfyUISettings:
    input_directory: Path
    output_directory: Path
    cleanup_after_copy: bool


def load_comfyui_settings(path=COMFYUI_SETTINGS_PATH) -> ComfyUISettings:
    """ComfyUI folders and cleanup setting declared in ``config/comfyui.json``."""
    path = Path(path)
    document = _load(path)
    directories = {}
    for key, meaning in _DIRECTORY_KEYS:
        value = _require_key(document, key, path)
        if not isinstance(value, str) or not value.strip():
            raise _config_error(
                f"En «{_display(path)}», «{key}» debe ser un texto no vacío.",
                f"Escriba en «{key}» la ruta de {meaning}.",
                path,
                key=key,
            )
        directories[key] = Path(value.strip())
    cleanup = _require_key(document, _CLEANUP_KEY, path)
    if not isinstance(cleanup, bool):
        raise _config_error(
            f"En «{_display(path)}», «{_CLEANUP_KEY}» debe ser true o false.",
            f"Escriba true en «{_CLEANUP_KEY}» para borrar de ComfyUI lo que "
            "deja el programa una vez copiado al proyecto, o false para "
            "conservarlo.",
            path,
            key=_CLEANUP_KEY,
        )
    return ComfyUISettings(
        cleanup_after_copy=cleanup,
        **directories,
    )


@dataclass(frozen=True)
class ComfyUIJobFolder:
    """Folder of one job inside a ComfyUI folder.

    ``path`` is the job folder (with a new technical name, so this execution
    creates it) and ``existing`` the closest folder above it that already
    existed before the job (or the ComfyUI folder itself).
    """

    path: Path
    existing: Path

    @classmethod
    def before_creating(cls, root, relative_path):
        """Job folder ``root/relative_path``, read before anything is created."""
        relative = PurePosixPath(Path(relative_path).as_posix())
        if (
            not relative.parts
            or relative.is_absolute()
            or ".." in relative.parts
        ):
            raise ValueError(
                "La carpeta del trabajo debe quedar dentro de la carpeta de "
                f"ComfyUI: {relative_path}"
            )
        root = Path(root)
        path = root.joinpath(*relative.parts)
        existing = path.parent
        while existing != root and not existing.is_dir():
            existing = existing.parent
        return cls(path=path, existing=existing)

    def contains(self, path) -> bool:
        path = Path(path).resolve()
        return self.path.resolve() in (path, *path.parents)

    def remove(self):
        """Delete the job folder and the empty folders the job created above it.

        Never ``existing`` nor anything above it, and never a folder that is
        not empty. A failed deletion is a warning and the run goes on.
        """
        if self.path.exists():
            try:
                shutil.rmtree(self.path)
            except OSError as error:
                _warn_not_deleted(self.path, error)
                return
        current = self.path.parent
        while current != self.existing and self.existing in current.parents:
            if current.is_dir():
                try:
                    if any(current.iterdir()):
                        return
                    current.rmdir()
                except OSError as error:
                    _warn_not_deleted(current, error)
                    return
            current = current.parent


def _warn_not_deleted(path, error):
    reason = getattr(error, "strerror", None) or str(error)
    ProgressLogger.warning(
        f"No se pudo borrar de ComfyUI «{Path(path).as_posix()}» ({reason}). "
        "La ejecución sigue; puede borrarlo a mano."
    )


def _load(path):
    if not path.is_file():
        raise _config_error(
            "Falta el archivo de configuración de ComfyUI "
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
        operation="Cargar configuración de ComfyUI",
        resource=_display(path),
        technical_metadata=(
            {"key": key}
            if key is not None
            else None
        ),
    )
