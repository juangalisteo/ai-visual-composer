from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


OUTPUT_FILE = "project_tree.txt"

EXCLUDED_DIRECTORIES = {
    ".agents",
    ".git",
    ".venv",
    "ComfyUI",
    "cache",
    "data",
    "logs",
    "models",
    "node_modules",
    "output",
    "temp",
    "venv",
}

OMITTED_DIRECTORIES = {
    ".mypy_cache",
    ".pytest_cache",
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


@dataclass(frozen=True)
class TreeStats:
    traversed_directories: int
    excluded_directories: int
    documented_files: int


@dataclass(frozen=True)
class TreeResult:
    lines: tuple[str, ...]
    stats: TreeStats


def main() -> None:
    root = Path.cwd()
    result = build_project_tree(root)
    output_path = root / OUTPUT_FILE
    output_path.write_text(
        "\n".join(result.lines) + "\n",
        encoding="utf-8",
    )
    print(f"archivo generado: {output_path.name}")
    print(f"carpetas recorridas: {result.stats.traversed_directories}")
    print(f"carpetas excluidas: {result.stats.excluded_directories}")
    print(f"archivos documentados: {result.stats.documented_files}")


def build_project_tree(root: Path) -> TreeResult:
    stats = _MutableStats()
    lines = [
        root.name
    ]
    lines.extend(
        _render_children(
            _visible_children(root),
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
        ),
    )


def _render_children(
    children: tuple[Path, ...],
    *,
    prefix: str,
    stats: "_MutableStats",
) -> list[str]:
    rendered = []
    last_index = len(children) - 1

    for index, child in enumerate(children):
        is_last = index == last_index
        connector = "└── " if is_last else "├── "
        rendered.append(
            f"{prefix}{connector}{child.name}"
        )

        if child.is_file():
            stats.documented_files += 1
            continue

        if _is_excluded_directory(child):
            stats.excluded_directories += 1
            continue

        if _is_media_only_directory(child):
            stats.excluded_directories += 1
            continue

        stats.traversed_directories += 1
        child_prefix = (
            f"{prefix}    "
            if is_last
            else f"{prefix}│   "
        )
        rendered.extend(
            _render_children(
                _visible_children(child),
                prefix=child_prefix,
                stats=stats,
            )
        )

    return rendered


def _visible_children(path: Path) -> tuple[Path, ...]:
    children = tuple(
        child
        for child in path.iterdir()
        if not _is_omitted_directory(child)
    )
    directories = sorted(
        (
            child
            for child in children
            if child.is_dir()
        ),
        key=_sort_key,
    )
    files = sorted(
        (
            child
            for child in children
            if child.is_file()
        ),
        key=_sort_key,
    )
    return tuple(directories + files)


def _is_excluded_directory(path: Path) -> bool:
    name = path.name
    return (
        name in EXCLUDED_DIRECTORIES
        or name.startswith("backup_")
        or _is_architectural_asset_directory(path)
    )


def _is_omitted_directory(path: Path) -> bool:
    if not path.is_dir():
        return False
    name = path.name
    return (
        name in OMITTED_DIRECTORIES
        or "pycache" in name.casefold()
    )


def _is_architectural_asset_directory(path: Path) -> bool:
    if len(path.parts) < 2:
        return False
    relative_tail = tuple(
        part.casefold()
        for part in path.parts[-2:]
    )
    return relative_tail in {
        tuple(
            part.casefold()
            for part in directory
        )
        for directory in ARCHITECTURAL_ASSET_DIRECTORIES
    }


def _is_media_only_directory(path: Path) -> bool:
    children = _visible_children(path)
    if not children:
        return False
    return all(
        child.is_file()
        and child.suffix.casefold() in MEDIA_EXTENSIONS
        for child in children
    )


def _sort_key(path: Path) -> str:
    return path.name.casefold()


class _MutableStats:
    def __init__(self) -> None:
        self.traversed_directories = 0
        self.excluded_directories = 0
        self.documented_files = 0


if __name__ == "__main__":
    main()
