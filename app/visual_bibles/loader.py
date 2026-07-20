from pathlib import Path
from typing import Any

from app.visual_bibles.models import (
    InheritancePolicy,
    VisualBibleCompositionReference,
    VisualBibleDocument,
    VisualBibleMetadata,
    VisualBibleReference,
)


SUPPORTED_SCHEMA_VERSION = 1
VALID_TYPES = {
    "root",
    "series",
    "episode",
    "sequence",
    "genre",
    "campaign",
    "format",
    "platform",
    "editorial",
    "reference",
}
VALID_COMPOSITION_ROLES = {
    "genre",
    "campaign",
    "format",
    "platform",
    "editorial",
    "reference",
}
KNOWN_TOP_LEVEL_KEYS = {
    "schema_version",
    "id",
    "version",
    "type",
    "title",
    "extends",
    "composes",
    "metadata",
    "inheritance_policy",
    "visual_bible",
}


class VisualBibleLoader:
    def load_file(
        self,
        path: str | Path
    ) -> VisualBibleDocument:
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
                f"Visual Bible document is empty: {source_path}"
            )
        if not isinstance(
            data,
            dict
        ):
            raise ValueError(
                f"Visual Bible document root must be a mapping: {source_path}"
            )

        return self._document_from_mapping(
            data,
            source_path
        )

    def load_directory(
        self,
        directory: str | Path
    ) -> tuple[VisualBibleDocument, ...]:
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
    ) -> VisualBibleDocument:
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
                f"Invalid Visual Bible type in {source_path}: {document_type}"
            )

        visual_bible = data.get(
            "visual_bible"
        )
        if not isinstance(
            visual_bible,
            dict
        ):
            raise ValueError(
                f"visual_bible must be a mapping in {source_path}"
            )

        return VisualBibleDocument(
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
            composes=_parse_composes(
                data.get(
                    "composes",
                    []
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
            inheritance_policy=_parse_inheritance_policy(
                data.get(
                    "inheritance_policy",
                    {}
                ),
                source_path
            ),
            visual_bible=visual_bible,
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
) -> VisualBibleReference | None:
    if value is None:
        return None
    if isinstance(
        value,
        str
    ):
        if not value:
            return None
        return VisualBibleReference(
            id=value
        )
    if isinstance(
        value,
        dict
    ):
        reference_id = _required_text(
            value,
            "id",
            source_path
        )
        return VisualBibleReference(
            id=reference_id,
            version=str(
                value.get(
                    "version",
                    ""
                )
            )
        )
    raise ValueError(
        f"Invalid reference in {source_path}: {value!r}"
    )


def _parse_composes(
    value: Any,
    source_path: Path
) -> tuple[VisualBibleCompositionReference, ...]:
    if value is None:
        return ()
    if not isinstance(
        value,
        list
    ):
        raise ValueError(
            f"composes must be a list in {source_path}"
        )

    result = []
    for item in value:
        if not isinstance(
            item,
            dict
        ):
            raise ValueError(
                f"compose entry must be a mapping in {source_path}"
            )
        role = _required_text(
            item,
            "role",
            source_path
        )
        if role not in VALID_COMPOSITION_ROLES:
            raise ValueError(
                f"Invalid compose role in {source_path}: {role}"
            )
        reference = item.get(
            "reference"
        )
        parsed = _parse_reference(
            reference,
            source_path
        )
        if parsed is None:
            raise ValueError(
                f"Missing compose reference in {source_path}"
            )
        result.append(
            VisualBibleCompositionReference(
                reference=parsed,
                role=role
            )
        )
    return tuple(
        result
    )


def _parse_metadata(
    value: Any,
    source_path: Path
) -> VisualBibleMetadata:
    if value is None:
        value = {}
    if not isinstance(
        value,
        dict
    ):
        raise ValueError(
            f"metadata must be a mapping in {source_path}"
        )
    return VisualBibleMetadata(
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
        description=str(
            value.get(
                "description",
                ""
            )
        ),
    )


def _parse_inheritance_policy(
    value: Any,
    source_path: Path
) -> InheritancePolicy:
    if value is None:
        value = {}
    if not isinstance(
        value,
        dict
    ):
        raise ValueError(
            f"inheritance_policy must be a mapping in {source_path}"
        )
    return InheritancePolicy(
        locked=_parse_string_tuple(
            value.get(
                "locked",
                []
            ),
            source_path
        ),
        appendable=_parse_string_tuple(
            value.get(
                "appendable",
                []
            ),
            source_path
        ),
        overridable=_parse_string_tuple(
            value.get(
                "overridable",
                []
            ),
            source_path
        ),
    )


def _parse_string_tuple(
    value: Any,
    source_path: Path
) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(
        value,
        list
    ):
        raise ValueError(
            f"Expected a list of strings in {source_path}"
        )
    result = []
    for item in value:
        if not isinstance(
            item,
            str
        ):
            raise ValueError(
                f"Expected a list of strings in {source_path}"
            )
        result.append(
            item
        )
    return tuple(
        result
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
