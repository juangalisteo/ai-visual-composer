"""Transformaciones de presentación para valores técnicos."""

from app.shared.format_catalog import fallback_label


def label(value):
    return fallback_label(value)


def voice_label(value):
    return label(value)


def family_label(family):
    return {
        "design": "MODO CONCIENCIA",
        "estandar": "ESTILO ESTÁNDAR",
        "minimalista": "MODO MINIMALISTA",
        "karaoke": "ESTILO KARAOKE",
        "primado_negativo": "PRIMADO NEGATIVO",
    }.get(family, family.replace("_", " ").upper())


def presentation_families(families):
    """Ordena conocidas y conserva el orden relativo de desconocidas."""
    presentation_order = {
        "design": 0,
        "estandar": 1,
        "minimalista": 2,
        "karaoke": 3,
        "primado_negativo": 4,
    }
    return tuple(
        family
        for _, family in sorted(
            enumerate(families),
            key=lambda item: (
                presentation_order.get(item[1], len(presentation_order)),
                item[0],
            ),
        )
    )
