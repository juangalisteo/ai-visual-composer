from app.controllers.interaction import labels
from app.controllers.run_controller import RunController


def test_labels_keep_known_values_and_technical_fallbacks():
    assert labels.label("mi_valor") == "Mi Valor"
    assert labels.voice_label("femenina") == "Femenina"
    assert labels.voice_label("voz_neutra") == "Voz Neutra"
    assert labels.subtitle_label("single_line") == "Línea única"
    assert labels.subtitle_label("other_mode") == "Other Mode"
    assert labels.family_label("minimalista") == "MODO MINIMALISTA"
    assert labels.family_label("future_family") == "FUTURE FAMILY"


def test_presentation_families_keep_unknown_relative_order():
    families = ("future_b", "karaoke", "future_a", "design", "estandar")

    assert labels.presentation_families(families) == (
        "design",
        "estandar",
        "karaoke",
        "future_b",
        "future_a",
    )


def test_run_controller_label_wrappers_keep_the_existing_public_surface():
    assert RunController._family_label("karaoke") == "FORMATO KARAOKE"
    assert RunController._presentation_families(("karaoke", "design")) == (
        "design",
        "karaoke",
    )
    controller = RunController()
    assert controller._label("mi_valor") == "Mi Valor"
    assert controller._voice_label("masculina") == "Masculina"
    assert controller._subtitle_label("word_by_word") == "Palabra por palabra"
