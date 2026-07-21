from typing import Any


def parse_safe_yaml(
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
