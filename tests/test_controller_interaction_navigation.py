import pytest
from unittest.mock import Mock, call

from app.controllers.interaction.navigation import Navigation
from app.controllers.interaction.terminal import Terminal
from app.controllers.run_controller import RunController
from app.modules.studio import (
    StudioInputMode,
    StudioSubtitleExportMode,
)
from tests.test_menu_helpers import MenuAnswers


def test_navigation_keeps_simple_pipeline_and_design_menu_contracts():
    terminal = MenuAnswers("Guion", "Diseño", "Video")
    navigation = Navigation(terminal, lambda: pytest.fail("No debe cancelar"))

    assert navigation.select_visual_pipeline() == "script"
    assert navigation.select_script_destination() == "design"
    assert navigation.select_design_target() == "video"
    assert terminal.messages == [
        "\nAI VISUAL COMPOSER\n",
        "1. Guion",
        "2. Imagen",
        "3. Video",
        "4. Studio",
        "\nDESTINO\n",
        "1. Imagen",
        "2. Video",
        "3. Diseño",
        "\nDISEÑO\n",
        "1. Imagen",
        "2. Video",
    ]


def test_navigation_keeps_pipeline_mode_condition_and_technical_values():
    terminal = MenuAnswers("Proyecto completo sin subtítulos")
    navigation = Navigation(terminal, lambda: pytest.fail("No debe cancelar"))

    assert navigation.select_pipeline_mode(
        include_full_without_subtitles=True,
    ) == "full_without_subtitles"
    assert terminal.messages == [
        "\nMODO\n",
        "1. Proyecto completo",
        "2. Solo audio",
        "3. Audio + subtítulos",
        "4. Audio + subtítulos + storyboard",
        "5. Proyecto completo sin subtítulos",
    ]


def test_navigation_keeps_studio_menu_order_and_return_types():
    terminal = MenuAnswers("EXPORTAR SRT ➜  VIDEO", "CONVERTIR", "Sí")
    navigation = Navigation(terminal, lambda: pytest.fail("No debe cancelar"))

    assert navigation.select_studio_input_mode() == (
        StudioInputMode.EXPORTAR_SRT.value
    )
    assert navigation.select_studio_subtitle_export_mode() is (
        StudioSubtitleExportMode.CONVERTIR
    )
    assert navigation.select_studio_montage_transitions() is True
    assert terminal.messages == [
        "\nENTRADA\n",
        "1. SOLO VIDEO",
        "2. SRT + VIDEO",
        "3. INTRO / OUTRO",
        "4. MONTAJE VÍDEOS",
        "5. VIDEO + AUDIO | SRT",
        "6. EXPORTAR SRT ➜  VIDEO",
        "\nMODO\n",
        "1. TRANSCRIBIR",
        "2. CONVERTIR",
        "\nTRANSICIONES\n",
        "1. Sí",
        "2. No",
    ]


def test_navigation_retries_unavailable_items_without_changing_the_menu():
    terminal = Mock()
    navigation = Navigation(terminal, lambda: pytest.fail("No debe cancelar"))
    terminal.select_from_list.side_effect = (
        {"name": "Imagen", "pipeline": "image", "available": False},
        {"name": "Video", "pipeline": "video"},
    )

    assert navigation.select_design_target() == "video"
    assert terminal.write.call_args_list == [
        call("\nDISEÑO\n"),
        call("1. Imagen"),
        call("2. Video"),
        call("\nNo disponible."),
        call("\nDISEÑO\n"),
        call("1. Imagen"),
        call("2. Video"),
    ]


def test_navigation_keeps_terminal_cancellation_callback():
    calls = []

    def cancel():
        calls.append("cancel")
        raise RuntimeError("cancelled")

    navigation = Navigation(
        Terminal(reader=lambda prompt: "0"),
        cancel,
    )

    with pytest.raises(RuntimeError, match="cancelled"):
        navigation.select_visual_pipeline()

    assert calls == ["cancel"]


def test_run_controller_delegates_all_navigation_selectors():
    navigation = Mock()
    navigation.select_visual_pipeline.return_value = "image"
    navigation.select_script_destination.return_value = "video"
    navigation.select_design_target.return_value = "image"
    navigation.select_pipeline_mode.return_value = "storyboard"
    navigation.select_studio_input_mode.return_value = "video"
    navigation.select_studio_subtitle_export_mode.return_value = (
        StudioSubtitleExportMode.TRANSCRIBIR
    )
    navigation.select_studio_montage_transitions.return_value = False
    controller = RunController(navigation=navigation)
    writer = Mock()
    selector = Mock()
    controller._print = writer
    controller._select_from_list = selector

    assert controller.select_visual_pipeline() == "image"
    assert controller.select_script_destination() == "video"
    assert controller.select_design_target() == "image"
    assert controller.select_pipeline_mode(True) == "storyboard"
    assert controller.select_studio_input_mode() == "video"
    assert controller.select_studio_subtitle_export_mode() is (
        StudioSubtitleExportMode.TRANSCRIBIR
    )
    assert controller.select_studio_montage_transitions() is False

    common = {"writer": writer, "selector": selector}
    navigation.select_visual_pipeline.assert_called_once_with(**common)
    navigation.select_script_destination.assert_called_once_with(**common)
    navigation.select_design_target.assert_called_once_with(**common)
    navigation.select_pipeline_mode.assert_called_once_with(
        include_full_without_subtitles=True,
        **common,
    )
    navigation.select_studio_input_mode.assert_called_once_with(**common)
    navigation.select_studio_subtitle_export_mode.assert_called_once_with(**common)
    navigation.select_studio_montage_transitions.assert_called_once_with(**common)
