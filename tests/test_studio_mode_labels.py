"""Visible names of the STUDIO modes (A2-G, PRUEBA-GS fallo 15)."""

from app.modules.studio import StudioInputMode


def test_exportar_srt_is_named_without_video_and_keeps_its_internal_value():
    assert StudioInputMode.EXPORTAR_SRT.label == "EXPORTAR SRT"
    assert StudioInputMode.EXPORTAR_SRT.value == "exportar_srt"


def test_no_mode_label_has_an_arrow_or_a_double_space():
    for mode in StudioInputMode:
        assert "➜" not in mode.label
        assert "  " not in mode.label
