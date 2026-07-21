from pathlib import Path
from typing import Any

from app.domain import IntentionLevel
from app.intentions.models import (
    IntentionDocument,
    IntentionMetadata,
    IntentionReference,
)
from app.shared.simple_yaml import parse_safe_yaml


SUPPORTED_SCHEMA_VERSION = 1
VALID_TYPES = {
    item.value
    for item in IntentionLevel
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
    "intention",
}
KNOWN_DIMENSIONS = {
    "communicative",
    "emotional",
    "cognitive",
    "narrative",
    "symbolic",
    "transformative",
    "attentional",
    "negative",
}
KNOWN_TRACE_KEYS = {
    "source_document",
    "source_sequence",
    "source_scene",
    "source_beat",
    "related_narrative_reading",
    "relationship_to_parent",
    "justification",
    "conflict_description",
}


class IntentionLoader:
    def load_file(
        self,
        path: str | Path
    ) -> IntentionDocument:
        source_path = Path(
            path
        )
        raw = source_path.read_text(
            encoding="utf-8"
        )
        data = parse_safe_yaml(
            raw
        )

        if data is None:
            raise ValueError(
                f"Intention document is empty: {source_path}"
            )
        if not isinstance(
            data,
            dict
        ):
            raise ValueError(
                f"Intention document root must be a mapping: {source_path}"
            )
        return self._document_from_mapping(
            data,
            source_path
        )

    def load_directory(
        self,
        directory: str | Path
    ) -> tuple[IntentionDocument, ...]:
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
    ) -> IntentionDocument:
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
                f"Invalid Intention type in {source_path}: {document_type}"
            )

        intention = data.get(
            "intention"
        )
        if not isinstance(
            intention,
            dict
        ):
            raise ValueError(
                f"intention must be a mapping in {source_path}"
            )
        unknown_dimensions = set(
            intention
        ) - KNOWN_DIMENSIONS
        if unknown_dimensions:
            raise ValueError(
                f"Unknown Intention dimensions in {source_path}: {sorted(unknown_dimensions)}"
            )
        for dimension, value in intention.items():
            if value is not None and not isinstance(
                value,
                dict
            ):
                raise ValueError(
                    f"Intention dimension must be a mapping in {source_path}: {dimension}"
                )

        return IntentionDocument(
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
            intention=intention,
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
) -> IntentionReference | None:
    if value is None:
        return None
    if isinstance(
        value,
        str
    ):
        if not value:
            return None
        return IntentionReference(
            id=value
        )
    if isinstance(
        value,
        dict
    ):
        return IntentionReference(
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
) -> IntentionMetadata:
    if value is None:
        value = {}
    if not isinstance(
        value,
        dict
    ):
        raise ValueError(
            f"metadata must be a mapping in {source_path}"
        )
    return IntentionMetadata(
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
    unknown = set(
        value
    ) - KNOWN_TRACE_KEYS
    if unknown:
        raise ValueError(
            f"Unknown trace keys in {source_path}: {sorted(unknown)}"
        )
    return value
