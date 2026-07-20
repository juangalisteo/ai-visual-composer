from pathlib import Path
from typing import Any

from app.domain import NarrativeConfidence
from app.narrative_readings.models import (
    NarrativeReadingDocument,
    NarrativeReadingMetadata,
    NarrativeReadingReference,
)


SUPPORTED_SCHEMA_VERSION = 1
VALID_TYPES = {
    "work",
    "sequence",
    "scene",
}
KNOWN_TOP_LEVEL_KEYS = {
    "schema_version",
    "id",
    "version",
    "type",
    "title",
    "extends",
    "metadata",
    "trace",
    "narrative_reading",
}
KNOWN_SECTIONS = {
    "facts",
    "event",
    "context",
    "change",
    "function",
    "entities",
    "relations",
    "conflict",
    "concepts",
    "explicit_symbols",
    "continuity",
}


class NarrativeReadingLoader:
    def load_file(
        self,
        path: str | Path
    ) -> NarrativeReadingDocument:
        source_path = Path(
            path
        )
        raw = source_path.read_text(
            encoding="utf-8"
        )
        data = _parse_safe_yaml(
            raw
        )

        if data is None:
            raise ValueError(
                f"Narrative Reading document is empty: {source_path}"
            )
        if not isinstance(
            data,
            dict
        ):
            raise ValueError(
                f"Narrative Reading document root must be a mapping: {source_path}"
            )

        return self._document_from_mapping(
            data,
            source_path
        )

    def load_directory(
        self,
        directory: str | Path
    ) -> tuple[NarrativeReadingDocument, ...]:
        base = Path(
            directory
        )
        paths = sorted(
            base.rglob(
                "*.yaml"
            ),
            key=lambda item: item.as_posix()
        )
        return tuple(
            self.load_file(
                path
            )
            for path in paths
        )

    def _document_from_mapping(
        self,
        data: dict[str, Any],
        source_path: Path
    ) -> NarrativeReadingDocument:
        unknown = set(
            data
        ) - KNOWN_TOP_LEVEL_KEYS
        if unknown:
            raise ValueError(
                f"Unknown top-level keys in {source_path}: {sorted(unknown)}"
            )

        schema_version = data.get(
            "schema_version"
        )
        if schema_version != SUPPORTED_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported schema_version in {source_path}: {schema_version}"
            )

        document_id = _required_text(
            data,
            "id",
            source_path
        )
        version = _required_text(
            data,
            "version",
            source_path
        )
        document_type = _required_text(
            data,
            "type",
            source_path
        )
        if document_type not in VALID_TYPES:
            raise ValueError(
                f"Invalid Narrative Reading type in {source_path}: {document_type}"
            )

        narrative_reading = data.get(
            "narrative_reading"
        )
        if not isinstance(
            narrative_reading,
            dict
        ):
            raise ValueError(
                f"narrative_reading must be a mapping in {source_path}"
            )
        unknown_sections = set(
            narrative_reading
        ) - KNOWN_SECTIONS
        if unknown_sections:
            raise ValueError(
                f"Unknown Narrative Reading sections in {source_path}: {sorted(unknown_sections)}"
            )
        _validate_confidence_values(
            narrative_reading,
            source_path
        )

        return NarrativeReadingDocument(
            schema_version=schema_version,
            id=document_id,
            version=version,
            type=document_type,
            title=str(
                data.get(
                    "title",
                    ""
                )
            ),
            extends=_parse_reference(
                data.get(
                    "extends"
                ),
                source_path
            ),
            metadata=_parse_metadata(
                data.get(
                    "metadata",
                    {}
                ),
                source_path
            ),
            trace=_parse_trace(
                data.get(
                    "trace",
                    {}
                ),
                source_path
            ),
            narrative_reading=narrative_reading,
            source_path=source_path,
        )


def _required_text(
    data: dict[str, Any],
    key: str,
    source_path: Path
) -> str:
    value = data.get(
        key
    )
    if not isinstance(
        value,
        str
    ) or not value:
        raise ValueError(
            f"Missing or empty {key} in {source_path}"
        )
    return value


def _parse_reference(
    value: Any,
    source_path: Path
) -> NarrativeReadingReference | None:
    if value is None:
        return None
    if isinstance(
        value,
        str
    ):
        if not value:
            return None
        return NarrativeReadingReference(
            id=value
        )
    if isinstance(
        value,
        dict
    ):
        return NarrativeReadingReference(
            id=_required_text(
                value,
                "id",
                source_path
            ),
            version=str(
                value.get(
                    "version",
                    ""
                )
            ),
        )
    raise ValueError(
        f"Invalid reference in {source_path}: {value!r}"
    )


def _parse_metadata(
    value: Any,
    source_path: Path
) -> NarrativeReadingMetadata:
    if value is None:
        value = {}
    if not isinstance(
        value,
        dict
    ):
        raise ValueError(
            f"metadata must be a mapping in {source_path}"
        )
    return NarrativeReadingMetadata(
        owner=str(
            value.get(
                "owner",
                ""
            )
        ),
        status=str(
            value.get(
                "status",
                ""
            )
        ),
        source=str(
            value.get(
                "source",
                ""
            )
        ),
        description=str(
            value.get(
                "description",
                ""
            )
        ),
    )


def _parse_trace(
    value: Any,
    source_path: Path
) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(
        value,
        dict
    ):
        raise ValueError(
            f"trace must be a mapping in {source_path}"
        )
    return value


def _validate_confidence_values(
    value: Any,
    source_path: Path
) -> None:
    if isinstance(
        value,
        dict
    ):
        for key, item in value.items():
            if key == "confidence":
                try:
                    NarrativeConfidence(
                        item
                    )
                except ValueError as exc:
                    raise ValueError(
                        f"Invalid NarrativeConfidence in {source_path}: {item}"
                    ) from exc
            _validate_confidence_values(
                item,
                source_path
            )
        return
    if isinstance(
        value,
        list
    ):
        for item in value:
            _validate_confidence_values(
                item,
                source_path
            )


def _parse_safe_yaml(
    text: str
) -> Any:
    lines = _prepare_lines(
        text
    )
    if not lines:
        return None
    parsed, index = _parse_block(
        lines,
        0,
        lines[0][0]
    )
    if index != len(
        lines
    ):
        raise ValueError(
            "Invalid YAML structure"
        )
    return parsed


def _prepare_lines(
    text: str
) -> list[tuple[int, str]]:
    result = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith(
            "#"
        ):
            continue
        indent = len(
            line
        ) - len(
            line.lstrip(
                " "
            )
        )
        result.append(
            (
                indent,
                _strip_inline_comment(
                    line.strip()
                )
            )
        )
    return result


def _strip_inline_comment(
    value: str
) -> str:
    in_single = False
    in_double = False
    for index, char in enumerate(
        value
    ):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double:
            if index == 0 or value[index - 1].isspace():
                return value[:index].rstrip()
    return value


def _parse_block(
    lines: list[tuple[int, str]],
    index: int,
    indent: int
) -> tuple[Any, int]:
    if lines[index][1].startswith(
        "- "
    ):
        return _parse_list(
            lines,
            index,
            indent
        )
    return _parse_map(
        lines,
        index,
        indent
    )


def _parse_map(
    lines: list[tuple[int, str]],
    index: int,
    indent: int
) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}
    while index < len(
        lines
    ):
        current_indent, content = lines[index]
        if current_indent < indent:
            break
        if current_indent > indent:
            raise ValueError(
                f"Unexpected indentation near: {content}"
            )
        if content.startswith(
            "- "
        ):
            break
        key, value = _split_key_value(
            content
        )
        index += 1
        if value == "":
            if index < len(
                lines
            ) and lines[index][0] > current_indent:
                child, index = _parse_block(
                    lines,
                    index,
                    lines[index][0]
                )
                result[key] = child
            else:
                result[key] = None
        else:
            result[key] = _parse_scalar(
                value
            )
    return result, index


def _parse_list(
    lines: list[tuple[int, str]],
    index: int,
    indent: int
) -> tuple[list[Any], int]:
    result = []
    while index < len(
        lines
    ):
        current_indent, content = lines[index]
        if current_indent < indent:
            break
        if current_indent > indent:
            raise ValueError(
                f"Unexpected indentation near: {content}"
            )
        if not content.startswith(
            "- "
        ):
            break

        item = content[2:].strip()
        index += 1
        if item == "":
            if index < len(
                lines
            ) and lines[index][0] > current_indent:
                child, index = _parse_block(
                    lines,
                    index,
                    lines[index][0]
                )
                result.append(
                    child
                )
            else:
                result.append(
                    None
                )
        elif _looks_like_key_value(
            item
        ):
            key, value = _split_key_value(
                item
            )
            mapping = {
                key: _parse_scalar(
                    value
                ) if value else None
            }
            if index < len(
                lines
            ) and lines[index][0] > current_indent:
                child, index = _parse_map(
                    lines,
                    index,
                    lines[index][0]
                )
                mapping.update(
                    child
                )
            result.append(
                mapping
            )
        else:
            result.append(
                _parse_scalar(
                    item
                )
            )
    return result, index


def _looks_like_key_value(
    value: str
) -> bool:
    return ":" in value and not value.startswith(
        '"'
    ) and not value.startswith(
        "'"
    )


def _split_key_value(
    content: str
) -> tuple[str, str]:
    if ":" not in content:
        raise ValueError(
            f"Expected key/value mapping: {content}"
        )
    key, value = content.split(
        ":",
        1
    )
    key = key.strip()
    if not key:
        raise ValueError(
            f"Empty key in mapping: {content}"
        )
    return key, value.strip()


def _parse_scalar(
    value: str
) -> Any:
    if value in {
        "null",
        "None",
        "~",
    }:
        return None
    if value == "true":
        return True
    if value == "false":
        return False
    if (
        value.startswith(
            '"'
        )
        and value.endswith(
            '"'
        )
    ) or (
        value.startswith(
            "'"
        )
        and value.endswith(
            "'"
        )
    ):
        return value[1:-1]
    try:
        return int(
            value
        )
    except ValueError:
        pass
    try:
        return float(
            value
        )
    except ValueError:
        return value
