from app.domain import (
    FindingSeverity,
    ResolutionStatus,
    VisualIntelligenceFinding,
)


VISUAL_TRUTH_FIELDS = (
    "visible_subject",
    "visible_action",
    "visible_environment",
    "time_context",
    "key_objects",
    "spatial_relationships",
    "continuity_links",
    "abstract_source",
    "filmable_interpretation",
    "visual_constraints",
    "visual_truth_status",
)

REQUIRED_VISUAL_TRUTH_FIELDS = (
    "visible_subject",
    "visible_action",
    "visible_environment",
    "filmable_interpretation",
)

SEQUENCE_FIELDS = (
    "key_objects",
    "spatial_relationships",
    "continuity_links",
    "visual_constraints",
)

AMBIGUOUS_TERMS = (
    "algo",
    "alguien",
    "cosa",
    "entorno",
    "escena",
    "habitacion",
    "lugar",
    "objeto",
    "persona",
    "room",
    "scene",
    "someone",
    "something",
    "thing",
    "object",
    "person",
    "place",
)


def clean(
    value
) -> str:
    if value is None:
        return ""
    return " ".join(
        str(
            value
        ).strip().split()
    )


def tuple_values(
    values
) -> tuple[str, ...]:
    if not values:
        return ()
    return tuple(
        item
        for item in (
            clean(
                value
            )
            for value in values
        )
        if item
    )


def dedupe(
    values
) -> tuple[str, ...]:
    seen = set()
    result = []
    for value in values:
        cleaned = clean(
            value
        )
        if cleaned and cleaned not in seen:
            seen.add(
                cleaned
            )
            result.append(
                cleaned
            )
    return tuple(
        result
    )


def visual_truth_value(
    scene,
    field_name: str
):
    return getattr(
        scene,
        field_name
    )


def visual_truth_values(
    scene
) -> tuple[str, ...]:
    values = []
    for field_name in VISUAL_TRUTH_FIELDS:
        if field_name == "visual_truth_status":
            continue
        value = visual_truth_value(
            scene,
            field_name
        )
        if isinstance(
            value,
            tuple
        ):
            values.extend(
                tuple_values(
                    value
                )
            )
        else:
            cleaned = clean(
                value
            )
            if cleaned:
                values.append(
                    cleaned
                )
    return tuple(
        values
    )


def is_ambiguous(
    value: str
) -> bool:
    cleaned = clean(
        value
    ).lower()
    return cleaned in AMBIGUOUS_TERMS


def status_from_findings(
    findings: tuple[VisualIntelligenceFinding, ...]
) -> ResolutionStatus:
    severities = tuple(
        finding.severity
        for finding in findings
    )
    if FindingSeverity.BLOCKING in severities:
        return ResolutionStatus.BLOCKED
    if FindingSeverity.ERROR in severities:
        return ResolutionStatus.ERROR
    if FindingSeverity.WARNING in severities:
        return ResolutionStatus.WARNING
    return ResolutionStatus.READY
