from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


OUTPUT_FILE = "project_tree.txt"

EXCLUDED_DIRECTORIES = {
    ".venv",
    "cache",
    "data",
    "models",
    "node_modules",
    "temp",
    "venv",
}

OMITTED_DIRECTORIES = {
    ".agents",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    "AGENT_AI",
    "CODEX",
    "ComfyUI",
    "input",
    "logs",
    "output",
}

ARCHITECTURAL_ASSET_DIRECTORIES = {
    ("assets", "music"),
    ("assets", "videos"),
}

MEDIA_EXTENSIONS = {
    ".aac",
    ".avi",
    ".bmp",
    ".flac",
    ".otf",
    ".gif",
    ".jpeg",
    ".jpg",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".ogg",
    ".png",
    ".tif",
    ".tiff",
    ".ttf",
    ".wav",
    ".webm",
    ".webp",
    ".woff",
    ".woff2",
}

# A directory is a dict of children; a file is None.
_Node = dict[str, "_Node | None"]


@dataclass(frozen=True)
class TreeStats:
    traversed_directories: int
    excluded_directories: int
    documented_files: int
    hidden_files: int


@dataclass(frozen=True)
class TreeResult:
    lines: tuple[str, ...]
    stats: TreeStats


def main() -> None:
    root = Path.cwd()
    try:
        tracked_files = list_tracked_files(root)
    except RuntimeError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    result = build_project_tree(root.name, tracked_files)
    output_path = root / OUTPUT_FILE
    output_path.write_text(
        "\n".join(result.lines) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"archivo generado: {output_path.name}")
    print(f"carpetas recorridas: {result.stats.traversed_directories}")
    print(f"carpetas excluidas: {result.stats.excluded_directories}")
    print(f"archivos documentados: {result.stats.documented_files}")
    print(f"archivos versionados no listados: {result.stats.hidden_files}")


def list_tracked_files(root: Path) -> tuple[str, ...]:
    try:
        completed = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=root,
            capture_output=True,
            check=True,
        )
    except FileNotFoundError as error:
        raise RuntimeError(
            "no se encontró Git en el PATH; instálalo para generar el árbol."
        ) from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(
            "no se pudo obtener la lista de archivos versionados con "
            f"'git ls-files' (¿es esta carpeta un repositorio Git?): {detail}"
        ) from error
    return tuple(
        entry
        for entry in completed.stdout.decode("utf-8").split("\0")
        if entry
    )


def build_project_tree(
    root_name: str,
    tracked_files: tuple[str, ...] | list[str],
) -> TreeResult:
    stats = _MutableStats()
    tree: _Node = {}
    for tracked_file in tracked_files:
        node = tree
        *directories, file_name = tracked_file.split("/")
        for directory in directories:
            child = node.setdefault(directory, {})
            assert child is not None
            node = child
        node[file_name] = None

    lines = [root_name]
    lines.extend(
        _render_children(
            tree,
            parents=(),
            prefix="",
            stats=stats,
        )
    )
    return TreeResult(
        lines=tuple(lines),
        stats=TreeStats(
            traversed_directories=stats.traversed_directories,
            excluded_directories=stats.excluded_directories,
            documented_files=stats.documented_files,
            hidden_files=stats.hidden_files,
        ),
    )


def _render_children(
    node: _Node,
    *,
    parents: tuple[str, ...],
    prefix: str,
    stats: "_MutableStats",
) -> list[str]:
    for name, child in node.items():
        if child is not None and _is_omitted_directory(name):
            stats.hidden_files += _count_files(child)
    children = _visible_children(node)
    rendered = []
    last_index = len(children) - 1

    for index, (name, child) in enumerate(children):
        is_last = index == last_index
        connector = "└── " if is_last else "├── "
        rendered.append(f"{prefix}{connector}{name}")

        if child is None:
            stats.documented_files += 1
            continue

        path = (*parents, name)
        if _is_excluded_directory(path) or _is_media_only_directory(child):
            stats.excluded_directories += 1
            stats.hidden_files += _count_files(child)
            continue

        stats.traversed_directories += 1
        child_prefix = f"{prefix}    " if is_last else f"{prefix}│   "
        rendered.extend(
            _render_children(
                child,
                parents=path,
                prefix=child_prefix,
                stats=stats,
            )
        )

    return rendered


def _visible_children(node: _Node) -> list[tuple[str, "_Node | None"]]:
    children = [
        (name, child)
        for name, child in node.items()
        if child is None or not _is_omitted_directory(name)
    ]
    directories = sorted(
        (item for item in children if item[1] is not None),
        key=_sort_key,
    )
    files = sorted(
        (item for item in children if item[1] is None),
        key=_sort_key,
    )
    return directories + files


def _is_excluded_directory(path: tuple[str, ...]) -> bool:
    name = path[-1]
    return (
        name in EXCLUDED_DIRECTORIES
        or name.startswith("backup_")
        or _is_architectural_asset_directory(path)
    )


def _is_omitted_directory(name: str) -> bool:
    return (
        name in OMITTED_DIRECTORIES
        or name.startswith("backup_")
        or "pycache" in name.casefold()
    )


def _is_architectural_asset_directory(path: tuple[str, ...]) -> bool:
    if len(path) < 2:
        return False
    relative_tail = tuple(part.casefold() for part in path[-2:])
    return relative_tail in {
        tuple(part.casefold() for part in directory)
        for directory in ARCHITECTURAL_ASSET_DIRECTORIES
    }


def _is_media_only_directory(node: _Node) -> bool:
    children = _visible_children(node)
    if not children:
        return False
    return all(
        child is None and Path(name).suffix.casefold() in MEDIA_EXTENSIONS
        for name, child in children
    )


def _count_files(node: "_Node | None") -> int:
    if node is None:
        return 1
    return sum(_count_files(child) for child in node.values())


def _sort_key(item: tuple[str, "_Node | None"]) -> str:
    return item[0].casefold()


class _MutableStats:
    def __init__(self) -> None:
        self.traversed_directories = 0
        self.excluded_directories = 0
        self.documented_files = 0
        self.hidden_files = 0


if __name__ == "__main__":
    main()
