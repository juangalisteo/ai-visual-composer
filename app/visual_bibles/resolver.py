import hashlib
import json
from dataclasses import asdict, fields, is_dataclass
from typing import Any

from app.domain import (
    CinematicLanguage,
    ColorSystem,
    CompositionPrinciples,
    ContinuityPrinciples,
    CreativeLimits,
    Identity,
    LightingPrinciples,
    PhotographyPrinciples,
    QualityCriteria,
    RealismAndAbstraction,
    SymbolicSystem,
    TextureAndMateriality,
    VisualBible,
    VisualPhilosophy,
)
from app.visual_bibles.loader import VALID_COMPOSITION_ROLES, VisualBibleLoader
from app.visual_bibles.models import (
    EffectiveVisualBible,
    InheritancePolicy,
    VisualBibleCompositionReference,
    VisualBibleDocument,
    VisualBibleFieldOrigin,
    VisualBibleTrace,
)


ROLE_PRECEDENCE = {
    "genre": 5,
    "campaign": 6,
    "format": 7,
    "platform": 8,
    "editorial": 9,
    "reference": 10,
}

SECTION_MODELS = {
    "philosophy": VisualPhilosophy,
    "identity": Identity,
    "cinematic_language": CinematicLanguage,
    "realism_and_abstraction": RealismAndAbstraction,
    "symbolic_system": SymbolicSystem,
    "composition": CompositionPrinciples,
    "photography": PhotographyPrinciples,
    "lighting": LightingPrinciples,
    "color": ColorSystem,
    "texture_and_materiality": TextureAndMateriality,
    "continuity": ContinuityPrinciples,
    "creative_limits": CreativeLimits,
    "quality": QualityCriteria,
}


class VisualBibleRegistry:
    def __init__(
        self,
        documents: tuple[VisualBibleDocument, ...]
    ):
        self._documents: dict[str, VisualBibleDocument] = {}
        for document in sorted(
            documents,
            key=lambda item: item.id
        ):
            if document.id in self._documents:
                raise ValueError(
                    f"Duplicate Visual Bible id: {document.id}"
                )
            self._documents[document.id] = document

    @classmethod
    def from_directory(
        cls,
        directory: str
    ) -> "VisualBibleRegistry":
        loader = VisualBibleLoader()
        return cls(
            loader.load_directory(
                directory
            )
        )

    def resolve(
        self,
        document_id: str
    ) -> EffectiveVisualBible:
        if document_id not in self._documents:
            raise ValueError(
                f"Unknown Visual Bible id: {document_id}"
            )
        chain = self._inheritance_chain(
            document_id,
            ()
        )
        policy = self._combined_policy(
            chain
        )
        merged: dict[str, Any] = {}
        origins: list[VisualBibleFieldOrigin] = []

        for document in chain:
            self._merge_visual_bible(
                merged,
                document.visual_bible,
                document,
                policy,
                origins
            )

        composed_layers = self._composition_layers(
            chain
        )
        for composition in composed_layers:
            document = self._documents.get(
                composition.reference.id
            )
            if document is None:
                raise ValueError(
                    f"Unknown composed Visual Bible id: {composition.reference.id}"
                )
            if document.type not in VALID_COMPOSITION_ROLES:
                raise ValueError(
                    f"Composed Visual Bible has invalid layer type: {document.id}"
                )
            self._ensure_no_cycle(
                document.id,
                document.id,
                set()
            )
            self._merge_visual_bible(
                merged,
                self._resolve_partial_visual_bible(
                    document.id
                ),
                document,
                policy,
                origins,
                composed=True
            )

        visual_bible = self._domain_visual_bible(
            merged
        )
        canonical = _canonical_mapping(
            visual_bible
        )
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
        inheritance_ids = tuple(
            document.id
            for document in chain
        )
        composed_ids = tuple(
            item.reference.id
            for item in composed_layers
        )
        trace = VisualBibleTrace(
            inheritance_chain=inheritance_ids,
            composed_layers=composed_ids,
            field_origins=tuple(
                origins
            )
        )
        source = chain[-1]
        return EffectiveVisualBible(
            visual_bible=visual_bible,
            source_id=source.id,
            source_version=source.version,
            schema_version=source.schema_version,
            inheritance_chain=inheritance_ids,
            composed_layers=composed_ids,
            trace=trace,
            fingerprint=fingerprint,
        )

    def _resolve_partial_visual_bible(
        self,
        document_id: str
    ) -> dict[str, Any]:
        chain = self._inheritance_chain(
            document_id,
            ()
        )
        policy = self._combined_policy(
            chain
        )
        merged: dict[str, Any] = {}
        origins: list[VisualBibleFieldOrigin] = []
        for document in chain:
            self._merge_visual_bible(
                merged,
                document.visual_bible,
                document,
                policy,
                origins
            )
        return merged

    def _inheritance_chain(
        self,
        document_id: str,
        stack: tuple[str, ...]
    ) -> tuple[VisualBibleDocument, ...]:
        if document_id in stack:
            raise ValueError(
                f"Visual Bible inheritance cycle detected: {' -> '.join(stack + (document_id,))}"
            )
        document = self._documents.get(
            document_id
        )
        if document is None:
            raise ValueError(
                f"Unknown Visual Bible id: {document_id}"
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

    def _ensure_no_cycle(
        self,
        start_id: str,
        current_id: str,
        visited: set[str]
    ) -> None:
        if current_id in visited:
            raise ValueError(
                f"Visual Bible composition cycle detected: {start_id}"
            )
        visited.add(
            current_id
        )
        document = self._documents[
            current_id
        ]
        for composition in document.composes:
            if composition.reference.id == start_id:
                raise ValueError(
                    f"Visual Bible composition cycle detected: {start_id}"
                )
            if composition.reference.id in self._documents:
                self._ensure_no_cycle(
                    start_id,
                    composition.reference.id,
                    visited.copy()
                )

    def _composition_layers(
        self,
        chain: tuple[VisualBibleDocument, ...]
    ) -> tuple[VisualBibleCompositionReference, ...]:
        layers = []
        for document in chain:
            for composition in document.composes:
                if composition.reference.id not in self._documents:
                    raise ValueError(
                        f"Unknown composed Visual Bible id: {composition.reference.id}"
                    )
                layers.append(
                    composition
                )
        return tuple(
            sorted(
                layers,
                key=lambda item: (
                    ROLE_PRECEDENCE[item.role],
                    item.reference.id
                )
            )
        )

    def _combined_policy(
        self,
        chain: tuple[VisualBibleDocument, ...]
    ) -> InheritancePolicy:
        locked: list[str] = []
        appendable: list[str] = []
        overridable: list[str] = []
        for document in chain:
            locked.extend(
                document.inheritance_policy.locked
            )
            appendable.extend(
                document.inheritance_policy.appendable
            )
            overridable.extend(
                document.inheritance_policy.overridable
            )
        return InheritancePolicy(
            locked=_dedupe(
                locked
            ),
            appendable=_dedupe(
                appendable
            ),
            overridable=_dedupe(
                overridable
            ),
        )

    def _merge_visual_bible(
        self,
        base: dict[str, Any],
        incoming: dict[str, Any],
        document: VisualBibleDocument,
        policy: InheritancePolicy,
        origins: list[VisualBibleFieldOrigin],
        composed: bool = False
    ) -> None:
        unknown_sections = set(
            incoming
        ) - set(
            SECTION_MODELS
        )
        if unknown_sections:
            raise ValueError(
                f"Unknown Visual Bible sections in {document.id}: {sorted(unknown_sections)}"
            )
        for section, value in incoming.items():
            if value is None:
                continue
            if not isinstance(
                value,
                dict
            ):
                raise ValueError(
                    f"Visual Bible section must be a mapping: {document.id}.{section}"
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
                policy,
                origins,
                composed
            )

    def _domain_visual_bible(
        self,
        data: dict[str, Any]
    ) -> VisualBible:
        missing = set(
            SECTION_MODELS
        ) - set(
            data
        )
        if missing:
            raise ValueError(
                f"Missing Visual Bible sections: {sorted(missing)}"
            )
        return VisualBible(
            philosophy=_section(
                "philosophy",
                data
            ),
            identity=_section(
                "identity",
                data
            ),
            cinematic_language=_section(
                "cinematic_language",
                data
            ),
            realism_and_abstraction=_section(
                "realism_and_abstraction",
                data
            ),
            symbolic_system=_section(
                "symbolic_system",
                data
            ),
            composition=_section(
                "composition",
                data
            ),
            photography=_section(
                "photography",
                data
            ),
            lighting=_section(
                "lighting",
                data
            ),
            color=_section(
                "color",
                data
            ),
            texture_and_materiality=_section(
                "texture_and_materiality",
                data
            ),
            continuity=_section(
                "continuity",
                data
            ),
            creative_limits=_section(
                "creative_limits",
                data
            ),
            quality=_section(
                "quality",
                data
            ),
        )


def _merge_mapping(
    base: dict[str, Any],
    incoming: dict[str, Any],
    prefix: str,
    document: VisualBibleDocument,
    policy: InheritancePolicy,
    origins: list[VisualBibleFieldOrigin],
    composed: bool
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
                policy,
                origins,
                composed
            )
            continue

        current = base.get(
            key
        )
        if current in (
            None,
            "",
            (),
            []
        ):
            base[key] = _normalize_value(
                value
            )
            origins.append(
                _origin(
                    path,
                    document,
                    "composed" if composed else "set"
                )
            )
            continue

        normalized = _normalize_value(
            value
        )
        if current == normalized:
            continue
        if isinstance(
            current,
            tuple
        ) and isinstance(
            normalized,
            tuple
        ):
            if _is_policy_path(
                path,
                policy.appendable
            ):
                base[key] = _dedupe(
                    current + normalized
                )
                origins.append(
                    _origin(
                        path,
                        document,
                        "appended" if not composed else "composed_appended"
                    )
                )
                continue
            raise ValueError(
                f"Field is not appendable: {path}"
            )
        if _is_policy_path(
            path,
            policy.overridable
        ):
            base[key] = normalized
            origins.append(
                _origin(
                    path,
                    document,
                    "overridden" if not composed else "composed_overridden"
                )
            )
            continue
        if _is_policy_path(
            path,
            policy.locked
        ):
            raise ValueError(
                f"Field is locked: {path}"
            )
        raise ValueError(
            f"Field is not authorized for change: {path}"
        )


def _section(
    name: str,
    data: dict[str, Any]
) -> Any:
    model = SECTION_MODELS[
        name
    ]
    allowed = {
        field.name
        for field in fields(
            model
        )
    }
    values = data[
        name
    ]
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


def _is_policy_path(
    path: str,
    policy_paths: tuple[str, ...]
) -> bool:
    return any(
        path == item or path.startswith(
            f"{item}."
        )
        for item in policy_paths
    )


def _origin(
    path: str,
    document: VisualBibleDocument,
    action: str
) -> VisualBibleFieldOrigin:
    return VisualBibleFieldOrigin(
        path=path,
        source_id=document.id,
        source_version=document.version,
        action=action,
    )


def _dedupe(
    values: tuple[str, ...] | list[str]
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
