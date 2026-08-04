import hashlib
import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any


def canonical_data(
    value: Any
) -> Any:
    if isinstance(
        value,
        Enum,
    ):
        return value.value
    if is_dataclass(
        value
    ):
        return canonical_data(
            asdict(
                value
            )
        )
    if isinstance(
        value,
        Path,
    ):
        return value.as_posix()
    if isinstance(
        value,
        dict,
    ):
        return {
            key: canonical_data(
                item
            )
            for key, item in sorted(
                value.items()
            )
        }
    if isinstance(
        value,
        (
            tuple,
            list,
        ),
    ):
        return [
            canonical_data(
                item
            )
            for item in value
        ]
    return value


def fingerprint(
    label: str,
    value: Any,
) -> str:
    return hashlib.sha256(
        json.dumps(
            {
                "label": label,
                "value": canonical_data(
                    value
                ),
            },
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
            ensure_ascii=False,
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def write_json(
    path: Path,
    value: Any,
) -> str:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    path.write_text(
        json.dumps(
            canonical_data(
                value
            ),
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return fingerprint(
        path.name,
        value,
    )


def read_json(
    path: Path,
) -> Any:
    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )
