import hashlib
import json
from dataclasses import asdict, fields, is_dataclass
from enum import Enum
from typing import Any

from app.domain import (
    AttentionalIntention,
    CognitiveIntention,
    CommunicativeIntention,
    EmotionalIntention,
    Intention,
    IntentionLevel,
    NarrativeIntention,
    NegativeIntention,
    SymbolicIntention,
    TransformativeIntention,
)
from app.intentions.loader import IntentionLoader
from app.intentions.models import (
    EffectiveIntention,
    IntentionConflict,
    IntentionDocument,
    IntentionFieldOrigin,
    IntentionTrace,
)


SECTION_MODELS = {
    "communicative": CommunicativeIntention,
    "emotional": EmotionalIntention,
    "cognitive": CognitiveIntention,
    "narrative": NarrativeIntention,
    "symbolic": SymbolicIntention,
    "transformative": TransformativeIntention,
    "attentional": AttentionalIntention,
    "negative": NegativeIntention,
}
LEVEL_ORDER = {
    IntentionLevel.WORK.value: 0,
    IntentionLevel.SEQUENCE.value: 1,
    IntentionLevel.SCENE.value: 2,
    IntentionLevel.BEAT.value: 3,
}
VALID_RELATIONSHIPS = {
    "",
    "aligned",
    "specialization",
    "contrast",
    "destructive_contradiction",
    "unjustified_deviation",
}


class IntentionRegistry:
    def __init__(
        self,
        documents: tuple[IntentionDocument, ...]
    ):
        self._documents: dict[str, IntentionDocument] = {}
        for document in sorted(
            documents,
            key=lambda item: item.id
        ):
            if document.id in self._documents:
                raise ValueError(
                    f"Duplicate Intention id: {document.id}"
                )
            self._documents[document.id] = document

    @classmethod
    def from_directory(
        cls,
        directory: str
    ) -> "IntentionRegistry":
        loader = IntentionLoader()
        return cls(
            loader.load_directory(
                directory
            )
        )

    def resolve(
        self,
        document_id: str
    ) -> EffectiveIntention:
        if document_id not in self._documents:
            raise ValueError(
                f"Unknown Intention id: {document_id}"
            )
        chain = self._inheritance_chain(
            document_id,
            ()
        )
        self._validate_level_chain(
            chain
        )
        merged: dict[str, Any] = {}
        origins: list[IntentionFieldOrigin] = []
        conflicts: list[IntentionConflict] = []

        for index, document in enumerate(
            chain
        ):
            inherited = index != len(
                chain
            ) - 1
            self._collect_relationship_conflicts(
                document,
                conflicts
            )
            self._merge_intention(
                merged,
                document,
                origins,
                inherited=inherited
            )

        intention = _domain_intention(
            merged
        )
        inheritance_ids = tuple(
            document.id
            for document in chain
        )
        active_exclusions = _active_exclusions(
            intention
        )
        canonical = {
            "schema_version": chain[-1].schema_version,
            "source_id": chain[-1].id,
            "source_version": chain[-1].version,
            "level": chain[-1].type,
            "inheritance_chain": inheritance_ids,
            "intention": _canonical_mapping(
                intention
            ),
            "conflicts": _canonical_mapping(
                tuple(
                    conflicts
                )
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
        trace = IntentionTrace(
            inheritance_chain=inheritance_ids,
            references=tuple(
                document.extends.id
                for document in chain
                if document.extends is not None
            ),
            field_origins=tuple(
                origins
            ),
            active_exclusions=active_exclusions,
        )
        source = chain[-1]
        return EffectiveIntention(
            intention=intention,
            source_id=source.id,
            source_version=source.version,
            schema_version=source.schema_version,
            level=IntentionLevel(
                source.type
            ),
            inheritance_chain=inheritance_ids,
            trace=trace,
            conflicts=tuple(
                conflicts
            ),
            fingerprint=fingerprint,
        )

    def _inheritance_chain(
        self,
        document_id: str,
        stack: tuple[str, ...]
    ) -> tuple[IntentionDocument, ...]:
        if document_id in stack:
            raise ValueError(
                f"Intention cycle detected: {' -> '.join(stack + (document_id,))}"
            )
        document = self._documents.get(
            document_id
        )
        if document is None:
            raise ValueError(
                f"Unknown Intention id: {document_id}"
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

    def _validate_level_chain(
        self,
        chain: tuple[IntentionDocument, ...]
    ) -> None:
        previous = -1
        for document in chain:
            current = LEVEL_ORDER[
                document.type
            ]
            if current != previous + 1:
                raise ValueError(
                    f"Invalid Intention hierarchy near: {document.id}"
                )
            previous = current

    def _collect_relationship_conflicts(
        self,
        document: IntentionDocument,
        conflicts: list[IntentionConflict]
    ) -> None:
        relationship = str(
            document.trace.get(
                "relationship_to_parent",
                ""
            )
        )
        if relationship not in VALID_RELATIONSHIPS:
            raise ValueError(
                f"Invalid relationship_to_parent in {document.id}: {relationship}"
            )
        if relationship == "destructive_contradiction":
            conflicts.append(
                IntentionConflict(
                    source_id=document.id,
                    conflict_type=relationship,
                    description=str(
                        document.trace.get(
                            "conflict_description",
                            "Destructive contradiction with parent intention."
                        )
                    ),
                    requires_review=True,
                )
            )
        elif relationship == "unjustified_deviation":
            conflicts.append(
                IntentionConflict(
                    source_id=document.id,
                    conflict_type=relationship,
                    description=str(
                        document.trace.get(
                            "conflict_description",
                            "Unjustified deviation from parent intention."
                        )
                    ),
                    requires_review=True,
                )
            )
        elif relationship == "contrast" and not document.trace.get(
            "justification"
        ):
            conflicts.append(
                IntentionConflict(
                    source_id=document.id,
                    conflict_type="unjustified_deviation",
                    description="Contrast requires justification.",
                    requires_review=True,
                )
            )

    def _merge_intention(
        self,
        base: dict[str, Any],
        document: IntentionDocument,
        origins: list[IntentionFieldOrigin],
        inherited: bool
    ) -> None:
        for section, value in document.intention.items():
            if value is None:
                continue
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
                inherited
            )


def _merge_mapping(
    base: dict[str, Any],
    incoming: dict[str, Any],
    prefix: str,
    document: IntentionDocument,
    origins: list[IntentionFieldOrigin],
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
                    "inherited" if inherited else "set"
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
                        "inherited" if inherited else "specialized"
                    )
                )
            continue
        if current != normalized:
            base[key] = normalized
            origins.append(
                _origin(
                    path,
                    document,
                    "inherited" if inherited else "replaced"
                )
            )


def _domain_intention(
    data: dict[str, Any]
) -> Intention:
    return Intention(
        communicative=_optional_section(
            "communicative",
            data
        ),
        emotional=_optional_section(
            "emotional",
            data
        ),
        cognitive=_optional_section(
            "cognitive",
            data
        ),
        narrative=_optional_section(
            "narrative",
            data
        ),
        symbolic=_optional_section(
            "symbolic",
            data
        ),
        transformative=_optional_section(
            "transformative",
            data
        ),
        attentional=_optional_section(
            "attentional",
            data
        ),
        negative=_optional_section(
            "negative",
            data
        ),
    )


def _optional_section(
    name: str,
    data: dict[str, Any]
) -> Any:
    values = data.get(
        name
    )
    if values is None:
        return None
    if not isinstance(
        values,
        dict
    ):
        raise ValueError(
            f"Intention section must be a mapping: {name}"
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
        values
    ) - allowed
    if unknown:
        raise ValueError(
            f"Unknown fields in {name}: {sorted(unknown)}"
        )
    normalized = {
        key: _normalize_value(
            value
        )
        for key, value in values.items()
    }
    return model(
        **normalized
    )


def _active_exclusions(
    intention: Intention
) -> tuple[str, ...]:
    if intention.negative is None:
        return ()
    return _dedupe(
        intention.negative.avoid_interpretations
        + intention.negative.avoid_effects
        + intention.negative.avoid_meaning_drift
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
    document: IntentionDocument,
    action: str
) -> IntentionFieldOrigin:
    return IntentionFieldOrigin(
        path=path,
        source_id=document.id,
        source_version=document.version,
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
