"""Reducción controlada de coordinadores de RunController (Fase 8)."""

import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from app.controllers.interaction.contracts import (
    StudioOperationalSelection,
    StudioProfileSelection,
    StudioSubtitleSelection,
)
from app.controllers.run_controller import RunController
from app.modules.studio import StudioInputMode
from app.shared.profile_identity import OperationalProfileKey, ProfileComponent
from app.shared.subtitle_profile_identity import SubtitleProfileKey


def _studio_selection():
    operational_key = OperationalProfileKey(
        "studio",
        "instagram",
        "studio_instagram",
    )
    subtitle_key = SubtitleProfileKey(
        "studio",
        "instagram",
        "subtitle_fixture",
        "estandar",
        parent_profile_id="studio_instagram",
    )
    studio_profile = Mock()
    return StudioProfileSelection(
        operational=StudioOperationalSelection(operational_key, studio_profile),
        subtitle=StudioSubtitleSelection(subtitle_key, True),
    )


def test_profile_coordinators_compose_extracted_operational_and_subtitle_selectors():
    profile_selection = Mock()
    subtitle_selection = Mock()
    operational_key = OperationalProfileKey(
        "imagen",
        "instagram",
        "imagen_instagram",
    )
    operational = {
        "path": Path("config/profiles/imagen/instagram/perfil.json"),
        "profile_key": operational_key,
    }
    subtitle_key = SubtitleProfileKey(
        "imagen",
        "instagram",
        "subtitle_fixture",
        "estandar",
        parent_profile_id="imagen_instagram",
    )
    profile_selection.select_profile_identity.return_value = operational
    subtitle_selection.select_profile_subtitle_profile.return_value = subtitle_key
    controller = RunController(
        profile_selection=profile_selection,
        subtitle_selection=subtitle_selection,
    )
    writer = Mock()
    selector = Mock()
    controller._print = writer
    controller._select_from_list = selector

    result = controller.select_profile("image")

    assert result is operational
    assert result["subtitle_profile_key"] is subtitle_key
    profile_selection.select_profile_identity.assert_called_once_with(
        ProfileComponent.IMAGEN,
        writer=writer,
        selector=selector,
        label=controller._label,
    )
    subtitle_selection.select_profile_subtitle_profile.assert_called_once_with(
        ProfileComponent.IMAGEN,
        "instagram",
        writer=writer,
        selector=selector,
        family_label=controller._family_label,
        presentation_families=controller._presentation_families,
    )


def test_studio_coordinator_transports_contract_to_final_options_without_state():
    selection = _studio_selection()
    controller = RunController()
    controller.select_visual_pipeline = Mock(return_value="studio")
    controller.select_studio_input_mode = Mock(
        return_value=StudioInputMode.SRT_VIDEO.value
    )
    controller._select_studio_profile_selection = Mock(return_value=selection)
    controller.select_studio_input_files = Mock(
        return_value=SimpleNamespace(
            video_path=Path("input/studio/srt_video/source.mp4"),
            subtitle_path=Path("input/studio/srt_video/source.srt"),
        )
    )
    controller.select_studio_music = Mock(return_value=None)
    controller.select_studio_intro_outro = Mock(return_value=None)
    controller.ask_project_name = Mock(return_value="studio")
    controller.ask_clear_output = Mock(return_value=False)

    options = controller.run()

    assert options["profile_component"] == "studio"
    assert options["profile_platform"] == "instagram"
    assert options["profile_id"] == "studio_instagram"
    assert options["subtitle_config"] == "subtitle_fixture"
    assert options["subtitle_profile_key"] is selection.subtitle.subtitle_key
    assert options["studio_subtitle_original"] is True
    assert options["studio_video_path"] == "input\\studio\\srt_video\\source.mp4"
    assert options["studio_subtitle_path"] == "input\\studio\\srt_video\\source.srt"
    assert not hasattr(controller, "_active_studio_subtitle_key")
    assert not hasattr(controller, "_active_studio_subtitle_original")


def test_studio_profile_options_are_explicit():
    selection = _studio_selection()
    controller = RunController()

    assert controller._studio_profile_options(
        selection.operational.operational_key,
        selection.subtitle.subtitle_key,
    ) == {
        "profile_component": "studio",
        "profile_platform": "instagram",
        "profile_id": "studio_instagram",
        "subtitle_profile_key": selection.subtitle.subtitle_key,
    }
    assert controller._studio_profile_options(
        selection.operational.operational_key
    ) == {
        "profile_component": "studio",
        "profile_platform": "instagram",
        "profile_id": "studio_instagram",
    }


def test_removed_state_has_no_runtime_readers():
    source = inspect.getsource(RunController)

    assert "_active_studio_subtitle_key" not in source
    assert "_active_studio_subtitle_original" not in source
    assert "_active_studio_design_subtitle_key" not in source
    assert "_studio_design_subtitle_key" not in source
