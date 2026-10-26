from pathlib import Path

from app.modules.video.config.loaders.subtitle_loader import SubtitleConfigLoader
from app.modules.video.subtitles.ass_visual_scale import (
    AssVisualScaleNormalizer,
)
from app.modules.video.subtitles.subtitle_render_preparation import (
    SubtitleRenderPreparation,
)
from app.shared.profile_identity import ProfileComponent
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


STYLE = {
    "font": "unisans",
    "font_size": 10,
    "bold": False,
    "primary_colour": "&H00FFFFFF",
    "outline_colour": "&H80000000",
    "back_colour": "&H00000000",
    "border_style": 1,
    "outline": 1,
    "shadow": 1,
    "alignment": 1,
    "margin_v": 55,
    "margin_l": 50,
    "margin_r": 50,
    "scale_x": 100.0,
    "scale_y": 100.0,
    "spacing": 2.0,
    "offset": 0.0,
    "dynamic": True,
    "cue_effect": "gravity_drop",
    "word_effect": "none",
    "drop_height_px": 100,
    "bounce_elasticity": 0.30,
}


def _source(path):
    path.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nHOLA MUNDO\n",
        encoding="utf-8",
    )
    return path


def test_dynamic_visual_units_are_normalized_from_target_playres():
    style = SubtitleConfigLoader().load_render_style(STYLE)

    normalized = AssVisualScaleNormalizer().normalize(style, 1080, 1920)

    assert normalized.font_size == 67
    assert normalized.margin_v == 367
    assert normalized.margin_l == 141
    assert normalized.margin_r == 141
    assert normalized.outline == 7
    assert normalized.shadow == 7
    assert normalized.spacing == 2.0 * (1920 / 288)
    assert normalized.scale_x == 100.0
    assert normalized.scale_y == 100.0
    assert normalized.cue_effect.parameters == {
        "drop_height_px": 667,
        "bounce_elasticity": 0.30,
    }


def test_dynamic_visual_normalization_is_resolution_driven_not_platform_named():
    style = SubtitleConfigLoader().load_render_style(STYLE)

    normalized = AssVisualScaleNormalizer().normalize(style, 1920, 1080)

    assert normalized.font_size == 38
    assert normalized.margin_v == 206
    assert normalized.margin_l == 250
    assert normalized.margin_r == 250
    assert normalized.cue_effect.parameters["drop_height_px"] == 375


def test_dynamic_preparation_writes_normalized_ass_and_static_stays_literal(tmp_path):
    source = _source(tmp_path / "source.srt")
    loader = SubtitleConfigLoader()

    static = SubtitleRenderPreparation().prepare(
        source,
        loader.load_render_style(STYLE | {"dynamic": False, "cue_effect": "none"}),
        1080,
        1920,
        STYLE | {"dynamic": False, "cue_effect": "none"},
    )
    assert static.force_style is not None
    assert "FontSize=10" in static.force_style
    assert "MarginV=55" in static.force_style

    dynamic = SubtitleRenderPreparation().prepare(
        source,
        loader.load_render_style(STYLE),
        1080,
        1920,
        STYLE,
    )
    try:
        content = Path(dynamic.path).read_text(encoding="utf-8")
        assert "PlayResX: 1080" in content
        assert "PlayResY: 1920" in content
        assert "Style: Default,UniSansHeavyCAPS,67," in content
        assert ",141,141,367,1" in content
    finally:
        dynamic.cleanup()


def test_active_pill_dimensions_follow_the_same_typographic_scale():
    style = SubtitleConfigLoader().load_render_style(
        STYLE
        | {
            "cue_effect": "none",
            "word_effect": "active_pill",
            "pill_colour": "&H0000FFFF",
            "pill_padding": 6,
            "pill_radius": 4,
        }
    )

    normalized = AssVisualScaleNormalizer().normalize(style, 1080, 1920)

    assert normalized.word_effect.parameters["pill_padding"] == 40
    assert normalized.word_effect.parameters["pill_radius"] == 27


def test_official_dynamic_profiles_normalize_without_family_specific_logic(tmp_path):
    resolver = SubtitleProfileResolver()
    source = _source(tmp_path / "official.srt")
    cases = (
        ("minimalista", "active_pill", 67),
        ("minimalista", "alpha_fade", 67),
        ("minimalista", "gravity_drop", 67),
        ("minimalista", "highlight_in_sentence", 67),
        ("minimalista", "pop_in_sentence", 67),
        ("minimalista", "typewriter", 67),
        ("karaoke", "roll_up", 67),
        ("karaoke", "continuous_karaoke", 67),
    )

    for family, technical_name, expected_font_size in cases:
        profile = resolver.load(
            SubtitleProfileKey(
                component=ProfileComponent.STUDIO,
                platform="vertical",
                family=family,
                profile_id=(
                    f"subtitulo_studio_vertical_{technical_name}"
                ),
            )
        )
        style = SubtitleConfigLoader().load_render_style(profile.render_style)
        prepared = SubtitleRenderPreparation().prepare(
            source,
            style,
            1080,
            1920,
            profile.render_style,
            cue_policy=profile.cue_policy,
        )
        try:
            content = Path(prepared.path).read_text(encoding="utf-8")
            assert prepared.backend.value == "DYNAMIC"
            assert (
                f"Style: Default," in content
                and f",{expected_font_size}," in content
            )
        finally:
            prepared.cleanup()


def test_official_static_profiles_remain_unscaled_srt(tmp_path):
    resolver = SubtitleProfileResolver()
    source = _source(tmp_path / "official.srt")
    cases = (
        ("minimalista", "acoustic_burst", 10),
        ("minimalista", "cumulative_line", 10),
        ("karaoke", "rolling_window", 10),
    )

    for family, technical_name, expected_font_size in cases:
        profile = resolver.load(
            SubtitleProfileKey(
                component=ProfileComponent.STUDIO,
                platform="vertical",
                family=family,
                profile_id=(
                    f"subtitulo_studio_vertical_{technical_name}"
                ),
            )
        )
        style = SubtitleConfigLoader().load_render_style(profile.render_style)
        prepared = SubtitleRenderPreparation().prepare(
            source,
            style,
            1080,
            1920,
            profile.render_style,
            cue_policy=profile.cue_policy,
        )

        assert prepared.backend.value == "STATIC"
        assert prepared.path == source
        assert f"FontSize={expected_font_size}" in prepared.force_style
