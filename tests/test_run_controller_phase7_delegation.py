"""Delegación de selección de perfiles y subtítulos (Fase 7)."""

import ast
from pathlib import Path
from unittest.mock import Mock

from app.controllers.interaction import profile_selection, subtitle_selection
from app.controllers.interaction.contracts import (
    StudioOperationalSelection,
    StudioProfileSelection,
    StudioSubtitleSelection,
)
from app.controllers.interaction.profile_selection import ProfileSelection
from app.controllers.interaction.subtitle_selection import SubtitleSelection
from app.controllers.run_controller import RunController
from app.modules.studio import StudioInputMode, StudioProfileLoader
from app.shared.profile_identity import OperationalProfileKey
from app.shared.profile_resolver import ProfileResolver
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


def test_run_controller_delegates_phase_seven_selection_facades():
    profiles = Mock()
    subtitles = Mock()
    profile_key = OperationalProfileKey("studio", "vertical", "studio_vertical")
    studio_profile = Mock()
    subtitle_key = Mock()
    profiles.studio_operational_profiles_by_platform.return_value = {
        "vertical": (Mock(),),
    }
    profiles.select_studio_operational_platform.return_value = "vertical"
    profiles.select_studio_operational_profile.return_value = (
        profile_key,
        studio_profile,
    )
    subtitles.select_studio_subtitle_profile.return_value = (subtitle_key, True)
    subtitles.select_studio_video_audio_srt_subtitle_profile.return_value = subtitle_key
    controller = RunController(
        profile_selection=profiles,
        subtitle_selection=subtitles,
    )
    writer = Mock()
    selector = Mock()
    controller._print = writer
    controller._select_from_list = selector

    discovered = controller._studio_operational_profiles_by_platform()
    assert discovered == profiles.studio_operational_profiles_by_platform.return_value
    assert controller._select_studio_operational_platform(discovered) == "vertical"
    assert controller._select_studio_operational_profile(
        platform="vertical",
        profiles_by_platform=discovered,
    ) == (profile_key, studio_profile)
    assert controller._select_studio_subtitle_profile(
        StudioInputMode.SRT_VIDEO.value,
        platform="vertical",
    ) == (subtitle_key, True)
    assert controller._select_studio_video_audio_srt_subtitle_profile(profile_key) is subtitle_key

    profiles.select_studio_operational_platform.assert_called_once_with(
        discovered,
        writer=writer,
        selector=selector,
        label=controller._label,
    )
    profile_call = profiles.select_studio_operational_profile.call_args
    assert profile_call.kwargs["platform"] == "vertical"
    assert profile_call.kwargs["profiles_by_platform"] is discovered
    assert profile_call.kwargs["writer"] is writer
    assert profile_call.kwargs["selector"] is selector
    subtitles.select_studio_subtitle_profile.assert_called_once_with(
        StudioInputMode.SRT_VIDEO.value,
        platform="vertical",
        writer=writer,
        selector=selector,
        label=controller._label,
        family_label=controller._family_label,
        presentation_families=controller._presentation_families,
    )
    subtitles.select_studio_video_audio_srt_subtitle_profile.assert_called_once_with(
        profile_key,
        writer=writer,
        selector=selector,
        family_label=controller._family_label,
        presentation_families=controller._presentation_families,
    )


def test_studio_profile_coordinator_composes_explicit_selection_without_state():
    profile_key = OperationalProfileKey("studio", "vertical", "studio_vertical")
    studio_profile = Mock()
    subtitle_key = Mock()
    controller = RunController()
    controller._studio_operational_profiles_by_platform = Mock(
        return_value={"vertical": (Mock(),)}
    )
    controller._select_studio_operational_platform = Mock(return_value="vertical")
    controller._select_studio_operational_profile = Mock(
        return_value=(profile_key, studio_profile)
    )
    controller._select_studio_subtitle_profile = Mock(
        return_value=(subtitle_key, True)
    )

    selection = controller._select_studio_profile_selection(
        StudioInputMode.SRT_VIDEO.value
    )

    assert selection == StudioProfileSelection(
        operational=StudioOperationalSelection(profile_key, studio_profile),
        subtitle=StudioSubtitleSelection(subtitle_key, True),
    )
    assert not hasattr(controller, "_active_studio_subtitle_key")
    assert not hasattr(controller, "_active_studio_subtitle_original")


def test_extracted_selectors_preserve_operational_and_subtitle_identities():
    profile_selector = ProfileSelection(
        ProfileResolver(),
        StudioProfileLoader(),
        Mock(),
        Mock(),
    )
    subtitle_resolver = SubtitleProfileResolver()
    subtitle_selector = SubtitleSelection(subtitle_resolver, Mock(), Mock())
    profiles_by_platform = profile_selector.studio_operational_profiles_by_platform()
    profile_key, studio_profile = profile_selector.select_studio_operational_profile(
        platform="vertical",
        profiles_by_platform=profiles_by_platform,
    )
    descriptor = subtitle_resolver.discover_profiles_for_family(
        "studio",
        "vertical",
        "estandar",
    )[0]
    subtitle_key, original = subtitle_selector.select_studio_subtitle_profile(
        StudioInputMode.SRT_VIDEO.value,
        platform="vertical",
        selector=Mock(side_effect=("estandar", descriptor)),
    )

    assert isinstance(profile_key, OperationalProfileKey)
    assert studio_profile.profile_id == profile_key.profile_id
    assert subtitle_key.component is profile_key.component
    assert subtitle_key.platform == profile_key.platform
    assert subtitle_key.profile_id != profile_key.profile_id
    assert original is True


def test_extracted_selectors_have_no_forbidden_or_mutual_dependencies():
    modules = (profile_selection, subtitle_selection)
    for module in modules:
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        imported_modules = {
            node.module
            for node in tree.body
            if isinstance(node, ast.ImportFrom)
        }
        assert "app.controllers.run_controller" not in imported_modules
        assert "main" not in imported_modules

    profile_imports = {
        node.module
        for node in ast.parse(
            Path(profile_selection.__file__).read_text(encoding="utf-8")
        ).body
        if isinstance(node, ast.ImportFrom)
    }
    subtitle_imports = {
        node.module
        for node in ast.parse(
            Path(subtitle_selection.__file__).read_text(encoding="utf-8")
        ).body
        if isinstance(node, ast.ImportFrom)
    }
    assert "app.controllers.interaction.subtitle_selection" not in profile_imports
    assert "app.controllers.interaction.profile_selection" not in subtitle_imports
