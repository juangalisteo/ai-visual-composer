from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.controllers.run_controller import RunController
from app.modules.video.config.loaders.subtitle_loader import SubtitleConfigLoader
from app.modules.video.ffmpeg.graphs.graph_context import GraphContext
from app.modules.video.ffmpeg.graphs.subtitle_graph_builder import (
    SubtitleGraphBuilder,
)
from app.modules.video.subtitles.subtitle_style_builder import (
    SubtitleStyleBuilder,
)
from app.shared.config_manager import ConfigManager
from app.shared.profile_identity import (
    ProfileComponent,
    ProfileFamily,
    ProfileKey,
    ProfilePlatform,
)
from app.shared.profile_resolver import ProfileResolver
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


COMPONENTS = tuple(ProfileComponent)
PLATFORMS = tuple(ProfilePlatform)
GLOBAL_SUBTITLE_FORBIDDEN_KEYS = frozenset(
    {
        "format",
        "resolution",
        "duration",
        "tone",
        "builders",
        "image_validation",
        "video_style",
        "validation",
        "video",
        "audio",
        "studio",
    }
)


def _environment(profile_key):
    return {
        "MC_PROFILE_COMPONENT": profile_key.component.value,
        "MC_PROFILE_PLATFORM": profile_key.platform.value,
        "MC_PROFILE_ID": profile_key.profile_id,
        "MC_PROFILE_FAMILY": profile_key.family.value,
    }


def _operational_projection(profile, component):
    if component is ProfileComponent.STUDIO:
        studio = profile["studio"]
        return {
            "format": profile["format"],
            "resolution": profile["resolution"],
            "input": deepcopy(studio["input"]),
            "output": deepcopy(studio["output"]),
            "montage": deepcopy(studio["montage"]),
            "music": deepcopy(studio["music"]),
        }

    return {
        "format": profile["format"],
        "resolution": profile["resolution"],
        "duration": profile["duration"],
        "tone": profile["tone"],
        "builders": deepcopy(profile["builders"]),
        "image_validation": deepcopy(profile["image_validation"]),
        "video_style": deepcopy(profile["video_style"]),
        "validation": deepcopy(profile["validation"]),
        "video": deepcopy(profile["video"]),
        "audio": deepcopy(profile["audio"]),
    }


@pytest.mark.parametrize("component", COMPONENTS)
@pytest.mark.parametrize("platform", PLATFORMS)
def test_phase0_standard_selection_preserves_system_operational_projection(
    monkeypatch,
    component,
    platform,
):
    """A STANDARD selection may resolve subtitle data, never mutate SYSTEM data."""
    profile_key = ProfileKey.for_component(component, platform)
    manager = ConfigManager()
    resolver = SubtitleProfileResolver()
    descriptor = resolver.discover_profiles(profile_key)[0]

    with monkeypatch.context() as context:
        for name, value in _environment(profile_key).items():
            context.setenv(name, value)

        before = _operational_projection(
            manager.get_profile_config(),
            component,
        )
        resolved = manager.get_subtitle_profile(descriptor.profile_id)
        after = _operational_projection(
            manager.get_profile_config(),
            component,
        )

    assert resolved.key.family is ProfileFamily.SYSTEM
    assert resolved.key.component is component
    assert resolved.key.platform is platform
    assert before == after


@pytest.mark.parametrize("component", COMPONENTS)
@pytest.mark.parametrize("platform", PLATFORMS)
def test_phase0_standard_profiles_are_subtitle_specialists(component, platform):
    profile_key = ProfileKey.for_component(component, platform)
    resolver = SubtitleProfileResolver()

    descriptors = resolver.discover_profiles(profile_key)
    assert {descriptor.style.value for descriptor in descriptors} == {
        "single_line",
        "word_by_word",
    }

    for descriptor in descriptors:
        resolved = resolver.load(descriptor.key)
        raw = json.loads(resolved.path.read_text(encoding="utf-8"))

        assert resolved.path.parts[-2] == "estandar"
        assert raw.keys() == {
            "component",
            "platform",
            "profile_id",
            "display_name",
            "style",
            "cue_policy",
            "render_style",
        }
        assert not (set(raw) & GLOBAL_SUBTITLE_FORBIDDEN_KEYS)
        assert resolved.cue_policy["mode"] == descriptor.style.value
        assert SubtitleConfigLoader().load_render_style(resolved.render_style)
        assert SubtitleStyleBuilder().build(resolved.render_style)


@pytest.mark.parametrize("component", COMPONENTS)
def test_phase0_design_instagram_identity_and_subtitle_payload_are_preserved(
    component,
):
    profile_resolver = ProfileResolver()
    subtitle_resolver = SubtitleProfileResolver()
    designs = profile_resolver.discover(
        component,
        ProfilePlatform.INSTAGRAM,
        ProfileFamily.DESIGN,
    )

    assert len(designs) == 1
    design_key, display_name = designs[0]
    descriptors = subtitle_resolver.discover_profiles(design_key)

    assert design_key.family is ProfileFamily.DESIGN
    assert design_key.component is component
    assert display_name == "Modo Conciencia | Reels"
    assert len(descriptors) == 1

    descriptor = descriptors[0]
    resolved = subtitle_resolver.load(descriptor.key)
    raw = json.loads(resolved.path.read_text(encoding="utf-8"))

    assert resolved.path.parts[-2] == "design"
    assert raw.keys() == {
        "component",
        "platform",
        "family",
        "profile_id",
        "display_name",
        "subtitle_config",
        "subtitle_profile",
    }
    assert not (set(raw) & GLOBAL_SUBTITLE_FORBIDDEN_KEYS)
    assert raw["subtitle_config"] == "word_by_word"
    assert raw["subtitle_profile"]["style"] == "word_by_word"
    assert resolved.cue_policy == raw["subtitle_profile"]["cue_policy"]
    assert resolved.render_style == raw["subtitle_profile"]["render_style"]
    assert SubtitleConfigLoader().load_render_style(resolved.render_style)


@pytest.mark.parametrize("component", COMPONENTS)
def test_phase1_design_selection_keeps_system_operational_projection(
    monkeypatch,
    component,
):
    system_key = ProfileKey.for_component(
        component,
        ProfilePlatform.INSTAGRAM,
    )
    profile_resolver = ProfileResolver()
    subtitle_resolver = SubtitleProfileResolver()
    design_key, _ = profile_resolver.discover(
        component,
        ProfilePlatform.INSTAGRAM,
        ProfileFamily.DESIGN,
    )[0]
    design_style = profile_resolver.declared_subtitle_style(design_key)
    subtitle_key = SubtitleProfileKey.for_design(
        component,
        ProfilePlatform.INSTAGRAM,
        design_key.profile_id,
        design_style,
    )
    standard_key = subtitle_resolver.discover_profiles(system_key)[0].key

    with monkeypatch.context() as context:
        for name, value in _environment(system_key).items():
            context.setenv(name, value)
        manager = ConfigManager()
        before = _operational_projection(
            manager.get_profile_config(), component,
        )
        standard = manager.get_subtitle_profile(standard_key)
        design = manager.get_subtitle_profile(subtitle_key)
        after = _operational_projection(
            manager.get_profile_config(), component,
        )

    assert standard.key.family is ProfileFamily.SYSTEM
    assert design.key.family is ProfileFamily.DESIGN
    assert before == after


def test_phase1_studio_system_uses_design_subtitle_identity_without_legacy_profile():
    system_key = ProfileKey.for_component("studio", "instagram")
    design_key, _ = ProfileResolver().discover(
        "studio",
        "instagram",
        ProfileFamily.DESIGN,
    )[0]
    style = ProfileResolver().declared_subtitle_style(design_key)
    design_subtitle_key = SubtitleProfileKey.for_design(
        "studio",
        "instagram",
        design_key.profile_id,
        style,
    )
    resolver = SubtitleProfileResolver()
    standard = resolver.load_selection(system_key, "single_line")
    design = resolver.load(design_subtitle_key)

    manager = ConfigManager()
    with pytest.MonkeyPatch.context() as context:
        for name, value in _environment(system_key).items():
            context.setenv(name, value)
        rendered = manager.get_subtitle_profile(
            "single_line",
            design_selection=design_subtitle_key,
        )
        original = manager.get_subtitle_profile(
            "single_line",
            original=True,
            design_selection=design_subtitle_key,
        )
        assert manager.get_profile_key() == system_key

    assert rendered.cue_policy == standard.cue_policy
    assert rendered.render_style == design.render_style
    assert original.cue_policy == design.cue_policy
    assert original.render_style == design.render_style


@pytest.mark.parametrize("style", ("single_line", "word_by_word"))
def test_phase2_studio_design_reuses_standard_functional_treatments(style):
    system_key = ProfileKey.for_component("studio", "instagram")
    design_key, _ = ProfileResolver().discover(
        "studio", "instagram", ProfileFamily.DESIGN,
    )[0]
    design_subtitle_key = SubtitleProfileKey.for_design(
        "studio",
        "instagram",
        design_key.profile_id,
        ProfileResolver().declared_subtitle_style(design_key),
    )
    resolver = SubtitleProfileResolver()
    standard = resolver.load_selection(system_key, style)
    design = resolver.load(design_subtitle_key)

    with pytest.MonkeyPatch.context() as context:
        for name, value in _environment(system_key).items():
            context.setenv(name, value)
        selected = ConfigManager().get_subtitle_profile(
            style,
            design_selection=design_subtitle_key,
        )

    assert selected.cue_policy == standard.cue_policy
    assert selected.render_style == design.render_style


def test_phase0_design_subtitle_choice_must_not_replace_system_profile_key():
    """DESIGN is transported as subtitle identity, never as runtime profile."""
    controller = RunController()
    controller._print = Mock()
    controller._select_from_list = Mock(
        side_effect=(
            ProfilePlatform.INSTAGRAM,
            "design",
            (
                ProfileKey.for_component(
                    "guion",
                    "instagram",
                    family="design",
                    profile_id="guion_instagram_design_modo_conciencia_reels",
                ),
                "Modo Conciencia | Reels",
            ),
        )
    )

    selected = controller._select_profile_identity(ProfileComponent.GUION)
    expected = ProfileKey.for_component("guion", "instagram")

    assert selected["profile_key"] == expected
    assert _operational_projection(
        ProfileResolver().load(selected["profile_key"]),
        ProfileComponent.GUION,
    ) == _operational_projection(
        ProfileResolver().load(expected),
        ProfileComponent.GUION,
    )


def test_phase0_static_srt_renderer_baseline_uses_force_style(tmp_path):
    profile_key = ProfileKey.for_component("video", "instagram")
    subtitle_key = SubtitleProfileKey.for_profile(profile_key, "word_by_word")
    subtitle_profile = SubtitleProfileResolver().load(subtitle_key)
    style = SubtitleStyleBuilder().build(subtitle_profile.render_style)
    subtitle_path = tmp_path / "source.srt"
    subtitle_path.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nTexto\n",
        encoding="utf-8",
    )
    fonts_dir = Path("assets/fonts")

    result = SubtitleGraphBuilder().build(
        GraphContext(
            context=SimpleNamespace(
                timeline=SimpleNamespace(subtitle_path=subtitle_path),
                fonts_dir=fonts_dir,
                subtitle_style=style,
            ),
            filter_parts=[],
            current_stream="[vin]",
        )
    )

    assert result.current_stream == "[vout]"
    assert len(result.parts) == 1
    filter_part = result.parts[0]
    assert "subtitles='" in filter_part
    assert "fontsdir='" in filter_part
    assert "force_style='" in filter_part
    assert "FontName=UniSansHeavyCAPS" in filter_part
    assert "FontSize=14" in filter_part
    assert "Alignment=2" in filter_part
    assert "offset" not in filter_part.lower()
