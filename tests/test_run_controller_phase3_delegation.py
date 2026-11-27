from unittest.mock import Mock

from app.controllers.run_controller import RunController


def test_run_controller_delegates_all_phase_three_responsibilities():
    common_options = Mock()
    common_options.select_voice_config.return_value = "femenina"
    common_options.select_music_category.return_value = None
    common_options.select_overlays_mode.return_value = "off"
    common_options.ask_project_name.return_value = "demo"
    common_options.ask_existing_project.return_value = True
    resource_selection = Mock()
    resource_selection.select_studio_music.return_value = None
    controller = RunController(
        common_options=common_options,
        resource_selection=resource_selection,
    )
    writer = Mock()
    selector = Mock()
    controller._print = writer
    controller._select_from_list = selector

    assert controller.select_voice_config() == "femenina"
    assert controller.select_music_category() is None
    assert controller.select_overlays_mode() == "off"
    assert controller.ask_project_name() == "demo"
    assert controller.ask_existing_project("demo") is True
    assert controller.select_studio_music() is None

    common_options.select_voice_config.assert_called_once_with(
        writer=writer,
        selector=selector,
    )
    common_options.select_music_category.assert_called_once_with(
        writer=writer,
        selector=selector,
    )
    common_options.select_overlays_mode.assert_called_once_with(
        writer=writer,
        selector=selector,
    )
    common_options.ask_project_name.assert_called_once_with(writer=writer)
    common_options.ask_existing_project.assert_called_once_with(
        "demo",
        writer=writer,
    )
    resource_selection.select_studio_music.assert_called_once_with(
        writer=writer,
        selector=selector,
    )
