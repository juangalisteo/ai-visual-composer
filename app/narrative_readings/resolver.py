import hashlib
import json
from dataclasses import asdict, fields, is_dataclass
from enum import Enum
from typing import Any

from app.domain import (
    ExplicitSymbols,
    NarrativeChange,
    NarrativeConcepts,
    NarrativeConfidence,
    NarrativeConflict,
    NarrativeContext,
    NarrativeContinuity,
    NarrativeEntities,
    NarrativeEvent,
    NarrativeFacts,
    NarrativeFunction,
    NarrativeReading,
    NarrativeRelations,
)
from app.narrative_readings.loader import NarrativeReadingLoader
from app.narrative_readings.models import (
    EffectiveNarrativeReading,
    NarrativeFieldOrigin,
    NarrativeReadingDocument,
    NarrativeTrace,
)


SECTION_MODELS = {
    "facts": NarrativeFacts,
    "event": NarrativeEvent,
    "context": NarrativeContext,
    "change": NarrativeChange,
    "function": NarrativeFunction,
    "entities": NarrativeEntities,
    "relations": NarrativeRelations,
    "conflict": NarrativeConflict,
    "concepts": NarrativeConcepts,
    "explicit_symbols": ExplicitSymbols,
    "continuity": NarrativeContinuity,
}
CONTEXTUAL_SECTIONS = {
    "context",
    "function",
    "relations",
    "conflict",
    "concepts",
    "continuity",
}


class NarrativeReadingRegistry:
    def __init__(
        self,
        documents: tuple[NarrativeReadingDocument, ...]
    ):
        self._documents: dict[str, NarrativeReadingDocument] = {}
        for document in sorted(
            documents,
            key=lambda item: item.id
        ):
            if document.id in self._documents:
                raise ValueError(
                    f"Duplicate Narrative Reading id: {document.id}"
                )
            self._documents[document.id] = document

    @classmethod
    def from_directory(
        cls,
        directory: str
    ) -> "NarrativeReadingRegistry":
        loader = NarrativeReadingLoader()
        return cls(
            loader.load_directory(
                directory
            )
        )

    def resolve(
        self,
        document_id: str
    ) -> EffectiveNarrativeReading:
        if document_id not in self._documents:
            raise ValueError(
                f"Unknown Narrative Reading id: {document_id}"
            )
        chain = self._inheritance_chain(
            document_id,
            ()
        )
        merged: dict[str, Any] = {}
        origins: list[NarrativeFieldOrigin] = []

        for index, document in enumerate(
            chain
        ):
            is_source = index == len(
                chain
            ) - 1
            self._merge_document(
                merged,
                document,
                origins,
                include_local_sections=is_source
            )

        reading = _domain_narrative_reading(
            merged
        )
        inheritance_ids = tuple(
            document.id
            for document in chain
        )
        canonical = {
            "schema_version": chain[-1].schema_version,
            "source_id": chain[-1].id,
            "source_version": chain[-1].version,
            "inheritance_chain": inheritance_ids,
            "narrative_reading": _canonical_mapping(
                reading
            ),
        }
        fingerprint = hashlib.sha256(
            json.dumps(
                canonical,
                sort_keys=True,
                separators=(
                    ",",
                    ":"
                )
            ).encode(
                "utf-8"
            )
        ).hexdigest()
        trace = NarrativeTrace(
            inheritance_chain=inheritance_ids,
            references=tuple(
                document.extends.id
                for document in chain
                if document.extends is not None
            ),
            field_origins=tuple(
                origins
            ),
        )
        source = chain[-1]
        return EffectiveNarrativeReading(
            narrative_reading=reading,
            source_id=source.id,
            source_version=source.version,
            schema_version=source.schema_version,
            inheritance_chain=inheritance_ids,
            trace=trace,
            fingerprint=fingerprint,
        )

    def _inheritance_chain(
        self,
        document_id: str,
        stack: tuple[str, ...]
    ) -> tuple[NarrativeReadingDocument, ...]:
        if document_id in stack:
            raise ValueError(
                f"Narrative Reading cycle detected: {' -> '.join(stack + (document_id,))}"
            )
        document = self._documents.get(
            document_id
        )
        if document is None:
            raise ValueError(
                f"Unknown Narrative Reading id: {document_id}"
            )
        if document.extends is None:
            return (
                document,
            )
        return self._inheritance_chain(
            document.extends.id,
            stack + (
                document_id,
            )
        ) + (
            document,
        )

    def _merge_document(
        self,
        base: dict[str, Any],
        document: NarrativeReadingDocument,
        origins: list[NarrativeFieldOrigin],
        include_local_sections: bool
    ) -> None:
        for section, value in document.narrative_reading.items():
            if value is None:
                continue
            if not include_local_sections and section not in CONTEXTUAL_SECTIONS:
                continue
            if not isinstance(
                value,
                dict
            ):
                raise ValueError(
                    f"Narrative Reading section must be a mapping: {document.id}.{section}"
                )
            target = base.setdefault(
                section,
                {}
            )
            _merge_mapping(
                target,
                value,
                section,
                document,
                origins,
                inherited=not include_local_sections
            )


def _merge_mapping(
    base: dict[str, Any],
    incoming: dict[str, Any],
    prefix: str,
    document: NarrativeReadingDocument,
    origins: list[NarrativeFieldOrigin],
    inherited: bool
) -> None:
    for key, value in incoming.items():
        path = f"{prefix}.{key}"
        if isinstance(
            value,
            dict
        ):
            child = base.setdefault(
                key,
                {}
            )
            if not isinstance(
                child,
                dict
            ):
                raise ValueError(
                    f"Cannot merge mapping into non-mapping field: {path}"
                )
            _merge_mapping(
                child,
                value,
                path,
                document,
                origins,
                inherited
            )
            continue

        normalized = _normalize_value(
            value
        )
        current = base.get(
            key
        )
        if current in (
            None,
            "",
            (),
            []
        ):
            base[key] = normalized
            origins.append(
                _origin(
                    path,
                    document,
                    "inherited" if inherited else "set",
                    normalized
                )
            )
            continue
        if isinstance(
            current,
            tuple
        ) and isinstance(
            normalized,
            tuple
        ):
            merged = _dedupe(
                current + normalized
            )
            if merged != current:
                base[key] = merged
                origins.append(
                    _origin(
                        path,
                        document,
                        "contextualized" if inherited else "set",
                        normalized
                    )
                )
            continue
        if current != normalized:
            base[key] = normalized
            origins.append(
                _origin(
                    path,
                    document,
                    "contextualized" if inherited else "set",
                    normalized
                )
            )


def _domain_narrative_reading(
    data: dict[str, Any]
) -> NarrativeReading:
    sections = {
        name: _section(
            name,
            data.get(
                name,
                {}
            )
        )
        for name in SECTION_MODELS
    }
    return NarrativeReading(
        facts=sections[
            "facts"
        ],
        event=sections[
            "event"
        ],
        context=sections[
            "context"
        ],
        change=sections[
            "change"
        ],
        function=sections[
            "function"
        ],
        entities=sections[
            "entities"
        ],
        relations=sections[
            "relations"
        ],
        conflict=sections[
            "conflict"
        ],
        concepts=sections[
            "concepts"
        ],
        explicit_symbols=sections[
            "explicit_symbols"
        ],
        continuity=sections[
            "continuity"
        ],
    )


def _section(
    name: str,
    data: dict[str, Any]
) -> Any:
    if not isinstance(
        data,
        dict
    ):
        raise ValueError(
            f"Narrative Reading section must be a mapping: {name}"
        )
    model = SECTION_MODELS[
        name
    ]
    allowed = {
        field.name
        for field in fields(
            model
        )
    }
    unknown = set(
        data
    ) - allowed
    if unknown:
        raise ValueError(
            f"Unknown fields in {name}: {sorted(unknown)}"
        )
    values = {
        key: _normalize_domain_value(
            key,
            value
        )
        for key, value in data.items()
    }
    return model(
        **values
    )


def _normalize_domain_value(
    key: str,
    value: Any
) -> Any:
    if key == "confidence":
        return NarrativeConfidence(
            value
        )
    return _normalize_value(
        value
    )


def _normalize_value(
    value: Any
) -> Any:
    if isinstance(
        value,
        list
    ):
        return tuple(
            _normalize_value(
                item
            )
            for item in value
        )
    if isinstance(
        value,
        dict
    ):
        return {
            key: _normalize_value(
                item
            )
            for key, item in value.items()
        }
    return value


def _canonical_mapping(
    value: Any
) -> Any:
    if isinstance(
        value,
        Enum
    ):
        return value.value
    if is_dataclass(
        value
    ):
        return {
            key: _canonical_mapping(
                item
            )
            for key, item in asdict(
                value
            ).items()
        }
    if isinstance(
        value,
        dict
    ):
        return {
            key: _canonical_mapping(
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
        )
    ):
        return [
            _canonical_mapping(
                item
            )
            for item in value
        ]
    return value


def _origin(
    path: str,
    document: NarrativeReadingDocument,
    action: str,
    value: Any
) -> NarrativeFieldOrigin:
    return NarrativeFieldOrigin(
        path=path,
        source_id=document.id,
        source_version=document.version,
        confidence=str(
            value
        ) if path.endswith(
            ".confidence"
        ) else "",
        action=action,
    )


def _dedupe(
    values: tuple[str, ...]
) -> tuple[str, ...]:
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(
                value
            )
            result.append(
                value
            )
    return tuple(
        result
    )
