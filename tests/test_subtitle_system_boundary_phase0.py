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
    OperationalProfileKey,
    ProfileComponent,
)
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


COMPONENTS = tuple(ProfileComponent)
PLATFORMS = ("instagram", "youtube")
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


OPERATIONAL_PROFILE_IDS = {
    (ProfileComponent.GUION, "instagram"): "guion_instagram",
    (ProfileComponent.GUION, "youtube"): "guion_youtube",
    (ProfileComponent.IMAGEN, "instagram"): "imagen_instagram",
    (ProfileComponent.IMAGEN, "youtube"): "imagen_youtube",
    (ProfileComponent.VIDEO, "instagram"): "video_instagram",
    (ProfileComponent.VIDEO, "youtube"): "video_youtube",
    (ProfileComponent.STUDIO, "instagram"): "studio_instagram",
    (ProfileComponent.STUDIO, "youtube"): "studio_youtube",
}


def _operational_key(component, platform):
    return OperationalProfileKey(
        component,
        platform,
        OPERATIONAL_PROFILE_IDS[(component, platform)],
    )


def _operational_projection(profile, component):
    if component is ProfileComponent.STUDIO:
        studio = profile["studio"]
        return {
            "format": profile["format"],
            "input": deepcopy(studio["input"]),
            "output": deepcopy(studio["output"]),
            "montage": deepcopy(studio["montage"]),
            "music": deepcopy(studio["music"]),
        }

    return {
        "format": profile["format"],
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
    component,
    platform,
):
    """A STANDARD selection may resolve subtitle data, never mutate SYSTEM data."""
    operational_key = _operational_key(component, platform)
    manager = ConfigManager(operational_profile_key=operational_key)
    resolver = SubtitleProfileResolver()
    descriptor = resolver.discover_profiles_for_family(
        component, platform, "estandar",
    )[0]

    before = _operational_projection(
        manager.get_profile_config(),
        component,
    )
    resolved = manager.get_subtitle_profile_by_key(descriptor.key)
    after = _operational_projection(
        manager.get_profile_config(),
        component,
    )

    assert resolved.key.family == "estandar"
    assert resolved.key.component is component
    assert resolved.key.platform == platform
    assert before == after


@pytest.mark.parametrize("component", COMPONENTS)
@pytest.mark.parametrize("platform", PLATFORMS)
def test_phase0_standard_profiles_are_subtitle_specialists(component, platform):
    resolver = SubtitleProfileResolver()

    descriptors = resolver.discover_profiles_for_family(
        component, platform, "estandar",
    )
    assert descriptors

    for descriptor in descriptors:
        resolved = resolver.load(descriptor.key)
        raw = json.loads(resolved.path.read_text(encoding="utf-8"))

        assert resolved.path.parts[-3:-1] == ("estandar", "subtitulos")
        assert raw.keys() == {
            "component",
            "platform",
            "family",
            "profile_id",
            "display_name",
            "cue_policy",
            "render_style",
        }
        assert not (set(raw) & GLOBAL_SUBTITLE_FORBIDDEN_KEYS)
        assert resolved.cue_policy["mode"] == descriptor.mode
        assert SubtitleConfigLoader().load_render_style(resolved.render_style)
        assert SubtitleStyleBuilder().build(resolved.render_style)


@pytest.mark.parametrize("component", COMPONENTS)
def test_phase0_design_instagram_identity_and_subtitle_payload_are_preserved(
    component,
):
    subtitle_resolver = SubtitleProfileResolver()
    descriptors = subtitle_resolver.discover_profiles_for_family(
        component, "instagram", "design",
    )
    assert descriptors

    for descriptor in descriptors:
        resolved = subtitle_resolver.load(descriptor.key)
        raw = json.loads(resolved.path.read_text(encoding="utf-8"))

        assert resolved.key == descriptor.key
        assert resolved.path.parts[-3:-1] == ("design", "subtitulos")
        assert raw.keys() == {
            "component",
            "platform",
            "family",
            "profile_id",
            "display_name",
            "cue_policy",
            "render_style",
        }
        assert not (set(raw) & GLOBAL_SUBTITLE_FORBIDDEN_KEYS)
        assert descriptor.mode == raw["cue_policy"]["mode"]
        assert resolved.cue_policy == raw["cue_policy"]
        assert resolved.render_style == raw["render_style"]
        assert SubtitleConfigLoader().load_render_style(resolved.render_style)


@pytest.mark.parametrize("component", COMPONENTS)
def test_phase1_design_selection_keeps_system_operational_projection(
    component,
):
    system_key = _operational_key(component, "instagram")
    subtitle_resolver = SubtitleProfileResolver()
    subtitle_key = subtitle_resolver.discover_profiles_for_family(
        component, "instagram", "design",
    )[0].key
    standard_key = subtitle_resolver.discover_profiles_for_family(
        component, "instagram", "estandar",
    )[0].key

    manager = ConfigManager(operational_profile_key=system_key)
    before = _operational_projection(
        manager.get_profile_config(), component,
    )
    standard = manager.get_subtitle_profile_by_key(standard_key)
    design = manager.get_subtitle_profile_by_key(subtitle_key)
    after = _operational_projection(
        manager.get_profile_config(), component,
    )

    assert standard.key.family == "estandar"
    assert design.key.family == "design"
    assert before == after


def test_phase3_studio_loads_design_subtitle_identity_without_composition():
    system_key = _operational_key(ProfileComponent.STUDIO, "instagram")
    resolver = SubtitleProfileResolver()
    design_subtitle_key = next(
        descriptor.key
        for descriptor in resolver.discover_profiles_for_family(
            "studio", "instagram", "design",
        )
        if descriptor.profile_id == "modo_conciencia_reels"
    )
    design = resolver.load(design_subtitle_key)

    manager = ConfigManager(operational_profile_key=system_key)
    rendered = manager.get_subtitle_profile_by_key(design_subtitle_key)
    assert manager.get_operational_profile_key().component is ProfileComponent.STUDIO
    assert manager.get_operational_profile_key().platform == "instagram"

    assert rendered.cue_policy == design.cue_policy
    assert rendered.render_style == design.render_style


def test_phase3_studio_loads_selected_design_profile_without_mode_coupling():
    system_key = _operational_key(ProfileComponent.STUDIO, "instagram")
    resolver = SubtitleProfileResolver()
    descriptors = resolver.discover_profiles_for_family(
        "studio", "instagram", "design",
    )
    assert descriptors

    manager = ConfigManager(operational_profile_key=system_key)
    for descriptor in descriptors:
        design = resolver.load(descriptor.key)
        selected = manager.get_subtitle_profile_by_key(descriptor.key)

        assert selected.key == descriptor.key
        assert selected.cue_policy["mode"] == descriptor.mode
        assert selected.cue_policy == design.cue_policy
        assert selected.render_style == design.render_style


def test_phase0_design_subtitle_choice_must_not_replace_system_profile_key():
    """DESIGN is transported as subtitle identity, never as runtime profile."""
    controller = RunController()
    controller._print = Mock()
    descriptor = SubtitleProfileResolver().discover_profiles_for_family(
        "guion", "instagram", "design",
    )[0]
    controller._select_from_list = Mock(side_effect=("instagram", "design", descriptor))

    selected = controller._select_profile_identity(ProfileComponent.GUION)
    expected = OperationalProfileKey("guion", "instagram", "guion_instagram")
    assert selected["profile_key"] == expected
    assert selected["subtitle_profile_key"] == descriptor.key


def test_phase0_static_srt_renderer_baseline_uses_force_style(tmp_path):
    subtitle_key = SubtitleProfileKey(
        "video",
        "instagram",
        "subtitulo_video_instagram_palabra_por_palabra",
        "estandar",
    )
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
