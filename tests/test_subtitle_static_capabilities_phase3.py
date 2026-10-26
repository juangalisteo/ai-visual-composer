import pytest

from app.modules.video.subtitles.subtitle_style_builder import (
    SubtitleStyleBuilder,
)
from app.shared.profile_identity import ProfileComponent
from app.shared.profile_resolver import ProfileResolver
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


OPTIONAL_FORCE_STYLE_FIELDS = (
    "Italic=",
    "Underline=",
    "StrikeOut=",
    "SecondaryColour=",
    "MarginL=",
    "MarginR=",
    "ScaleX=",
    "ScaleY=",
    "Spacing=",
)


@pytest.mark.parametrize("component", tuple(ProfileComponent))
@pytest.mark.parametrize("profile_format", ("horizontal", "vertical"))
def test_phase3_official_standard_baseline_uses_the_static_srt_engine(
    component,
    profile_format,
):
    resolver = SubtitleProfileResolver()

    for descriptor in resolver.discover_profiles_for_family(
        component, profile_format, "estandar",
    ):
        resolved = resolver.load(descriptor.key)
        force_style = SubtitleStyleBuilder().build(resolved.render_style)

        assert "FontName=" in force_style
        assert "FontSize=" in force_style
        assert "Bold=" in force_style
        assert "PrimaryColour=" in force_style
        assert "OutlineColour=" in force_style
        assert "BackColour=" in force_style
        assert "BorderStyle=" in force_style
        assert "Outline=" in force_style
        assert "Shadow=" in force_style
        assert "Alignment=" in force_style
        assert "MarginV=" in force_style
        assert "offset" not in force_style.lower()


@pytest.mark.parametrize("component", tuple(ProfileComponent))
def test_phase3_official_design_baseline_is_static_and_pure(component):
    subtitle_key = SubtitleProfileResolver().discover_profiles_for_family(
        component, "vertical", "design",
    )[0].key
    resolved = SubtitleProfileResolver().load(subtitle_key)
    raw = resolved.path.read_text(encoding="utf-8")
    force_style = SubtitleStyleBuilder().build(resolved.render_style)

    assert resolved.render_style["font"] == "oswald"
    assert "FontName=Oswald" in force_style
    assert f"FontSize={resolved.render_style['font_size']}" in force_style
    assert f"Bold={int(resolved.render_style['bold'])}" in force_style
    assert all(field not in force_style for field in OPTIONAL_FORCE_STYLE_FIELDS)
    assert '"cue_policy"' in raw
