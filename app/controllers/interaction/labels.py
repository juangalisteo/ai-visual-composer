"""Transformaciones de presentación para valores técnicos."""


def label(value):
    return value.replace("_", " ").title()


def voice_label(value):
    return label(value)


def family_label(family):
    return {
        "design": "MODO CONCIENCIA",
        "estandar": "FORMATO ESTÁNDAR",
        "minimalista": "MODO MINIMALISTA",
        "karaoke": "FORMATO KARAOKE",
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
